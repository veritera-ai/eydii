"""
Veritera Forge Verify SDK — Python Client
Enterprise-grade AI agent decision verification.

Usage:
    from veritera import Veritera

    forge = Veritera(api_key="vt_live_...")
    result = await forge.verify_decision(
        agent_id="agent-1",
        action="payment.create",
        params={"amount": 100, "currency": "USD"},
        policy="finance-controls",
    )
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from . import __version__

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_der_public_key
import base64


class ForgeError(Exception):
    """Structured error from the Forge API."""

    def __init__(self, message: str, code: str = "unknown", status: int = 0, details: Any = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details


class RateLimitError(ForgeError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after_ms: int = 60000):
        super().__init__(message, code="rate_limited", status=429)
        self.retry_after_ms = retry_after_ms


@dataclass
class ConstraintResult:
    type: str
    result: str  # "pass" | "fail" | "skip"
    detail: Optional[str] = None


@dataclass
class DenialProof:
    """First-class denial proof (PRD 4.3.1). Present on every DENY verdict."""
    denial_id: str
    action_attempted: str
    timestamp: str
    agent_id_hash: str
    policy_name: str
    policy_hash: str
    constraint_type: str
    constraint_detail: str
    parameter_hash: str
    source: str
    signature: str
    denial_hash: str
    previous_denial_hash: Optional[str]
    chain_index: int


@dataclass
class VerifyResponse:
    verified: bool
    verdict: str
    decision_id: str
    proof_id: str
    agent_id: str
    action: str
    policy: Optional[str]
    reason: Optional[str]
    mode: str
    proof_status: str
    evaluated_constraints: list[ConstraintResult]
    verification: dict[str, Any]
    denial_proof: Optional[DenialProof]
    audit_id: str
    latency_ms: float
    timestamp: str


@dataclass
class LocalVerifyResult:
    valid: bool
    key_version: Optional[int]
    payload_hash: str
    algorithm: str = "Ed25519"


@dataclass
class PolicyRule:
    """A single constraint rule within a policy."""
    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Policy:
    """A Forge policy definition."""
    id: int
    name: str
    description: Optional[str]
    rules: list[PolicyRule]
    version: int
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class PolicyTestResult:
    """Result of testing a policy against a simulated action."""
    policy_id: int
    policy_name: str
    policy_version: int
    action: str
    verified: bool
    verdict: str
    reason: Optional[str]
    evaluated_constraints: list[ConstraintResult]


@dataclass
class ReceiptResponse:
    """Response from submitting an Execute receipt."""
    receipt_id: str
    receipt_hash: str
    chain_index: int
    received_at: str


class ReceiptSigner:
    """Signs Execute receipts using Ed25519 or HMAC-SHA256.

    Auto-detects signing mode based on key format:
    - 64-char hex string (32 bytes) -> Ed25519 private key
    - Anything else -> HMAC-SHA256 key

    Usage:
        signer = ReceiptSigner(signing_key=os.environ["FORGE_AGENT_PRIVATE_KEY"])
        receipt_data = signer.sign_and_build("file_write", "agent-1", "task_abc")
        result = forge.execute_receipt_sync(**receipt_data)
    """

    def __init__(self, signing_key: str):
        self._key = signing_key
        # 64 hex chars = 32 bytes = Ed25519 private key
        try:
            if len(signing_key) == 64:
                bytes.fromhex(signing_key)
                self._use_ed25519 = True
            else:
                self._use_ed25519 = False
        except ValueError:
            self._use_ed25519 = False

    def sign_and_build(self, action_type: str, agent_id: str, task_id: str) -> dict:
        """Sign a receipt and return the full payload for execute_receipt_sync.

        Returns dict with: task_id, action_type, agent_id, nonce, timestamp, signature
        """
        nonce = os.urandom(16).hex()
        timestamp = int(time.time() * 1000)

        message = f"forge-receipt:v1:{action_type}:{timestamp}:{nonce}"
        msg_bytes = message.encode("utf-8")

        if self._use_ed25519:
            private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self._key))
            signature = private_key.sign(msg_bytes).hex()
        else:
            import hmac as hmac_mod
            signature = hmac_mod.new(
                self._key.encode("utf-8"), msg_bytes, hashlib.sha256
            ).hexdigest()

        return {
            "task_id": task_id,
            "action_type": action_type,
            "agent_id": agent_id,
            "nonce": nonce,
            "timestamp": timestamp,
            "signature": signature,
        }


class Veritera:
    """Veritera Forge Verify SDK Client."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://forge.veritera.ai",
        timeout: float = 10.0,
        max_retries: int = 2,
        fail_closed: bool = True,
        debug: bool = False,
    ):
        if not api_key:
            raise ValueError("Forge SDK: api_key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._fail_closed = fail_closed
        self._debug = debug
        import os
        _env = os.environ.get("PYTHON_ENV", os.environ.get("ENV", "production"))
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"forge-verify-python/{__version__}",
                "X-Forge-SDK-Version": __version__,
                "X-Forge-Environment": _env,
            },
        )

        # Circuit breaker state (per-instance)
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_reset_s = 30.0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        await self._client.aclose()

    def _is_circuit_open(self) -> bool:
        if self._consecutive_failures < self._circuit_breaker_threshold:
            return False
        if time.time() > self._circuit_open_until:
            # Half-open: allow one request through
            self._consecutive_failures = self._circuit_breaker_threshold - 1
            return False
        return True

    def _record_success(self) -> None:
        self._consecutive_failures = 0

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_breaker_threshold:
            self._circuit_open_until = time.time() + self._circuit_breaker_reset_s

    async def _request(self, method: str, path: str, body: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
        """HTTP request with retry, backoff, jitter, and circuit breaker."""
        if self._is_circuit_open():
            raise ForgeError(
                "Forge API circuit breaker is open — too many consecutive failures. Will retry automatically.",
                code="circuit_open",
                status=503,
            )

        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                base_delay = min(1.0 * (2 ** (attempt - 1)), 10.0)
                jitter = random.random() * base_delay * 0.3
                delay = base_delay + jitter
                if self._debug:
                    print(f"[Forge Verify] Retry {attempt}/{self._max_retries} after {delay:.1f}s")
                await _async_sleep(delay)

            try:
                response = await self._client.request(
                    method, path,
                    json=body if body else None,
                    headers=headers or {},
                )

                if response.status_code == 429:
                    self._record_failure()
                    retry_after = int(response.headers.get("Retry-After", "60")) * 1000
                    raise RateLimitError("Rate limit exceeded", retry_after)

                if 400 <= response.status_code < 500:
                    self._record_success()
                    data = response.json() if response.content else {}
                    raise ForgeError(
                        data.get("message", f"Request failed: {response.status_code}"),
                        code=data.get("error", "client_error"),
                        status=response.status_code,
                        details=data,
                    )

                if response.status_code >= 500:
                    self._record_failure()
                    last_error = ForgeError(f"Server error: {response.status_code}", status=response.status_code)
                    continue

                self._record_success()
                return response.json()

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                self._record_failure()
                last_error = ForgeError(str(e), code="network_error", status=0)
                continue

        raise last_error or ForgeError("Request failed after retries")

    # ── Core: Verify a Decision ──

    async def verify_decision(
        self,
        agent_id: str,
        action: str,
        params: Optional[dict[str, Any]] = None,
        policy: Optional[str] = None,
        allowed_actions: Optional[list[str]] = None,
        delegation_id: Optional[str] = None,
        require_zk_proof: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> VerifyResponse:
        """Verify an AI agent decision against policy constraints."""
        body: dict[str, Any] = {"agent_id": agent_id, "action": action}
        if params:
            body["params"] = params
        if policy:
            body["policy"] = policy
        if allowed_actions:
            body["allowed_actions"] = allowed_actions
        if delegation_id:
            body["delegation_id"] = delegation_id
        if require_zk_proof:
            body["require_zk_proof"] = True

        headers: Optional[dict] = None
        if idempotency_key:
            headers = {"Idempotency-Key": idempotency_key}

        try:
            raw = await self._request("POST", "/v1/verify", body, headers=headers)
            return self._map_verify_response(raw)
        except (ForgeError, Exception) as e:
            if self._fail_closed:
                # Fail-closed: return denied instead of throwing
                return VerifyResponse(
                    verified=False,
                    verdict="denied",
                    decision_id="",
                    proof_id="",
                    agent_id=agent_id,
                    action=action,
                    policy=policy,
                    reason=f"Forge unavailable — action denied (fail-closed): {e}",
                    mode="fail-closed",
                    proof_status="not_requested",
                    evaluated_constraints=[],
                    verification={},
                    denial_proof=None,
                    audit_id="",
                    latency_ms=0,
                    timestamp="",
                )
            raise

    # ── Proof Retrieval ──

    async def get_proof(self, proof_id: str) -> dict:
        """Retrieve a verification proof by ID."""
        return await self._request("GET", f"/v1/proofs/{proof_id}")

    # ── Local Proof Verification ──

    def verify_proof_locally(
        self,
        attestation: str,
        attestation_payload: dict[str, Any],
        public_key: str,
        key_version: Optional[int] = None,
    ) -> LocalVerifyResult:
        """Verify a DPE attestation locally without any backend call."""
        payload_bytes = json.dumps(attestation_payload).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        try:
            sig_bytes = base64.b64decode(attestation)
            pub_key_der = base64.b64decode(public_key)
            pub_key = load_der_public_key(pub_key_der)

            if not isinstance(pub_key, Ed25519PublicKey):
                return LocalVerifyResult(valid=False, key_version=key_version, payload_hash=payload_hash)

            pub_key.verify(sig_bytes, payload_bytes)
            return LocalVerifyResult(valid=True, key_version=key_version, payload_hash=payload_hash)

        except Exception:
            return LocalVerifyResult(valid=False, key_version=key_version, payload_hash=payload_hash)

    # ── Policies ──

    async def create_policy(
        self,
        name: str,
        rules: list[dict[str, Any]],
        description: Optional[str] = None,
    ) -> Policy:
        """Create a policy. Rules are constraint definitions.

        Example:
            policy = await forge.create_policy(
                name="finance-controls",
                description="Block high-value transactions",
                rules=[
                    {"type": "action_whitelist", "params": {"allowed": ["payment.read", "payment.create"]}},
                    {"type": "amount_limit", "params": {"max": 10000, "currency": "USD"}},
                ],
            )
        """
        body: dict[str, Any] = {"name": name, "rules": rules}
        if description is not None:
            body["description"] = description
        raw = await self._request("POST", "/v1/policies", body)
        return self._map_policy(raw)

    async def list_policies(self) -> list[Policy]:
        """List all active policies for this API key."""
        raw = await self._request("GET", "/v1/policies")
        return [self._map_policy(p) for p in raw.get("policies", [])]

    async def get_policy(self, policy_id: int) -> Policy:
        """Get a policy by ID."""
        raw = await self._request("GET", f"/v1/policies/{policy_id}")
        return self._map_policy(raw)

    async def update_policy(
        self,
        policy_id: int,
        name: Optional[str] = None,
        rules: Optional[list[dict[str, Any]]] = None,
        description: Optional[str] = None,
    ) -> Policy:
        """Update an existing policy. Only pass fields you want to change."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if rules is not None:
            body["rules"] = rules
        if description is not None:
            body["description"] = description
        raw = await self._request("PUT", f"/v1/policies/{policy_id}", body)
        return self._map_policy(raw)

    async def delete_policy(self, policy_id: int) -> bool:
        """Deactivate a policy (soft delete)."""
        raw = await self._request("DELETE", f"/v1/policies/{policy_id}")
        return raw.get("success", False)

    async def test_policy(
        self,
        policy_id: int,
        action: str,
        params: Optional[dict[str, Any]] = None,
    ) -> PolicyTestResult:
        """Test a policy against a simulated action without persisting anything."""
        body: dict[str, Any] = {"action": action}
        if params:
            body["params"] = params
        raw = await self._request("POST", f"/v1/policies/{policy_id}/test", body)
        return PolicyTestResult(
            policy_id=raw.get("policy_id", policy_id),
            policy_name=raw.get("policy_name", ""),
            policy_version=raw.get("policy_version", 0),
            action=raw.get("action", action),
            verified=bool(raw.get("verified")),
            verdict=raw.get("verdict", ""),
            reason=raw.get("reason"),
            evaluated_constraints=[
                ConstraintResult(type=c.get("type", ""), result=c.get("result", "skip"), detail=c.get("detail"))
                for c in raw.get("evaluated_constraints", [])
            ],
        )

    async def generate_policy(
        self,
        prompt: str,
        save: bool = False,
    ) -> dict:
        """Generate a policy from natural language description.

        Example:
            result = await forge.generate_policy(
                "Only allow my agent to read files and send emails. Block all deletions.",
                save=True,
            )
        """
        return await self._request("POST", "/v1/policies/generate", {"prompt": prompt, "save": save})

    async def get_policy_templates(self) -> list[dict]:
        """Get all available policy templates (no auth required)."""
        return await self._request("GET", "/v1/policy-templates")

    def _map_policy(self, raw: dict) -> Policy:
        rules_raw = raw.get("rules", [])
        rules = [
            PolicyRule(type=r.get("type", ""), params=r.get("params", {}))
            for r in (rules_raw if isinstance(rules_raw, list) else [])
        ]
        return Policy(
            id=int(raw.get("id", 0)),
            name=str(raw.get("name", "")),
            description=raw.get("description"),
            rules=rules,
            version=int(raw.get("version", 1)),
            is_active=bool(raw.get("is_active", True)),
            created_at=raw.get("created_at") or raw.get("timestamp"),
            updated_at=raw.get("updated_at"),
        )

    # ── Delegation ──

    async def create_delegation(
        self,
        agent_id: str,
        allowed_actions: list[str],
        constraints: Optional[dict] = None,
        expires_in: Optional[str] = None,
    ) -> dict:
        """Create a scoped delegation for an agent."""
        body: dict[str, Any] = {"agent_id": agent_id, "allowed_actions": allowed_actions}
        if constraints:
            body["constraints"] = constraints
        if expires_in:
            body["expires_in"] = expires_in
        return await self._request("POST", "/v1/delegate", body)

    # ── Usage ──

    async def get_usage(self, period: Optional[str] = None) -> dict:
        """Get usage statistics for the current billing period."""
        path = f"/v1/usage?period={period}" if period else "/v1/usage"
        return await self._request("GET", path)

    # ── Health ──

    async def health(self) -> dict:
        """Check Forge Verify API health."""
        return await self._request("GET", "/v1/health")

    # ── Execute: Receipt Submission ──

    async def execute_receipt(
        self,
        task_id: str,
        action_type: str,
        agent_id: str,
        signature: str,
        nonce: str,
        timestamp: int,
    ) -> ReceiptResponse:
        """Submit a signed receipt to Forge Execute.

        Typically called with the output of ReceiptSigner.sign_and_build():
            data = signer.sign_and_build("tool_call", agent_id, task_id)
            result = await forge.execute_receipt(**data)
        """
        raw = await self._request("POST", "/v1/execute/receipt", {
            "task_id": task_id,
            "action_type": action_type,
            "agent_id": agent_id,
            "signature": signature,
            "nonce": nonce,
            "timestamp": timestamp,
        })
        return ReceiptResponse(
            receipt_id=raw.get("receipt_id", ""),
            receipt_hash=raw.get("receipt_hash", ""),
            chain_index=int(raw.get("chain_index", 0)),
            received_at=raw.get("received_at", ""),
        )

    # ── Response Mapping ──

    def _map_verify_response(self, raw: dict) -> VerifyResponse:
        verification = raw.get("verification", {})
        constraints = raw.get("evaluated_constraints", [])

        # Map denial proof if present (PRD 4.3.1)
        raw_dp = raw.get("denial_proof")
        denial_proof = None
        if raw_dp and isinstance(raw_dp, dict):
            denial_proof = DenialProof(
                denial_id=str(raw_dp.get("denial_id", "")),
                action_attempted=str(raw_dp.get("action_attempted", "")),
                timestamp=str(raw_dp.get("timestamp", "")),
                agent_id_hash=str(raw_dp.get("agent_id_hash", "")),
                policy_name=str(raw_dp.get("policy_name", "")),
                policy_hash=str(raw_dp.get("policy_hash", "")),
                constraint_type=str(raw_dp.get("constraint_type", "")),
                constraint_detail=str(raw_dp.get("constraint_detail", "")),
                parameter_hash=str(raw_dp.get("parameter_hash", "")),
                source=str(raw_dp.get("source", "dpe")),
                signature=str(raw_dp.get("signature", "")),
                denial_hash=str(raw_dp.get("denial_hash", "")),
                previous_denial_hash=raw_dp.get("previous_denial_hash"),
                chain_index=int(raw_dp.get("chain_index", 0)),
            )

        return VerifyResponse(
            verified=bool(raw.get("verified")),
            verdict=raw.get("verdict", "approved" if raw.get("verified") else "denied"),
            decision_id=str(raw.get("decision_id", "")),
            proof_id=str(raw.get("proof_id", "")),
            agent_id=str(raw.get("agent_id", "")),
            action=str(raw.get("action", "")),
            policy=raw.get("policy"),
            reason=raw.get("reason"),
            mode=raw.get("mode", "dpe"),
            proof_status=raw.get("proof_status", "not_requested"),
            evaluated_constraints=[
                ConstraintResult(type=c.get("type", ""), result=c.get("result", "skip"), detail=c.get("detail"))
                for c in constraints
            ],
            verification=verification,
            denial_proof=denial_proof,
            audit_id=str(raw.get("audit_id", "")),
            latency_ms=float(raw.get("latency_ms", 0)),
            timestamp=str(raw.get("timestamp", "")),
        )


class Forge(Veritera):
    """Forge SDK client with synchronous convenience methods.

    Usage:
        forge = Forge(api_key="vt_live_...")

        # Create a policy
        policy = forge.create_policy_sync("finance-controls", rules=[...])

        # Verify an action
        result = forge.verify_sync("send_payment", params={"amount": 500}, policy="finance-controls")
    """

    def _run_sync(self, coro):
        """Run an async coroutine synchronously, handling nested event loops."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, coro).result(timeout=self._timeout + 5)
            else:
                return asyncio.run(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def verify_sync(
        self,
        action: str,
        agent_id: str = "default",
        params: Optional[dict] = None,
        policy: Optional[str] = None,
    ) -> VerifyResponse:
        """Synchronous verify — blocks until result. Fail-closed on error."""
        try:
            return self._run_sync(
                self.verify_decision(agent_id=agent_id, action=action, params=params, policy=policy)
            )
        except Exception as e:
            if self._fail_closed:
                return VerifyResponse(
                    verified=False, verdict="denied", decision_id="", proof_id="",
                    agent_id=agent_id, action=action, policy=policy,
                    reason=f"Forge unavailable (fail-closed): {e}",
                    mode="fail-closed", proof_status="not_requested", evaluated_constraints=[],
                    verification={}, denial_proof=None, audit_id="", latency_ms=0, timestamp="",
                )
            raise

    # ── Policy sync wrappers ──

    def create_policy_sync(
        self,
        name: str,
        rules: list[dict[str, Any]],
        description: Optional[str] = None,
    ) -> "Policy":
        """Create a policy (synchronous)."""
        return self._run_sync(self.create_policy(name, rules, description))

    def list_policies_sync(self) -> "list[Policy]":
        """List all active policies (synchronous)."""
        return self._run_sync(self.list_policies())

    def get_policy_sync(self, policy_id: int) -> "Policy":
        """Get a policy by ID (synchronous)."""
        return self._run_sync(self.get_policy(policy_id))

    def update_policy_sync(
        self,
        policy_id: int,
        name: Optional[str] = None,
        rules: Optional[list[dict[str, Any]]] = None,
        description: Optional[str] = None,
    ) -> "Policy":
        """Update a policy (synchronous)."""
        return self._run_sync(self.update_policy(policy_id, name, rules, description))

    def delete_policy_sync(self, policy_id: int) -> bool:
        """Deactivate a policy (synchronous)."""
        return self._run_sync(self.delete_policy(policy_id))

    def test_policy_sync(
        self,
        policy_id: int,
        action: str,
        params: Optional[dict[str, Any]] = None,
    ) -> "PolicyTestResult":
        """Test a policy against a simulated action (synchronous)."""
        return self._run_sync(self.test_policy(policy_id, action, params))

    def generate_policy_sync(self, prompt: str, save: bool = False) -> dict:
        """Generate a policy from natural language (synchronous)."""
        return self._run_sync(self.generate_policy(prompt, save))

    # ── Execute sync wrapper ──

    def execute_receipt_sync(self, **kwargs) -> "ReceiptResponse":
        """Submit a signed receipt (synchronous).

        Usage:
            data = signer.sign_and_build("tool_call", agent_id, task_id)
            result = forge.execute_receipt_sync(**data)
        """
        return self._run_sync(self.execute_receipt(**kwargs))


async def _async_sleep(seconds: float):
    """Async sleep helper."""
    import asyncio
    await asyncio.sleep(seconds)
