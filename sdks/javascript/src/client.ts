// ===============================================
// Veritera Forge Verify SDK — Client
// ===============================================
// Enterprise-grade SDK for AI agent decision verification.
// Zero external dependencies. Designed for millions of agents.

import { httpRequest, type HttpConfig } from "./http.js";
import { verifyAttestationLocally } from "./crypto.js";
import type {
  VeriteraConfig,
  VerifyRequest,
  VerifyResponse,
  DenialProof,
  ProofResponse,
  LocalVerifyResult,
  DelegateRequest,
  DelegateResponse,
  UsageResponse,
  ForgeError,
} from "./types.js";

const DEFAULT_BASE_URL = "https://forge.veritera.ai";
const DEFAULT_TIMEOUT = 10_000;
const DEFAULT_MAX_RETRIES = 2;
const DEFAULT_FAIL_CLOSED = true;

/**
 * Veritera Forge Verify SDK Client.
 *
 * @example
 * ```typescript
 * const forge = new Veritera({ apiKey: "vt_live_..." });
 *
 * const result = await forge.verifyDecision({
 *   agentId: "agent-1",
 *   action: "payment.create",
 *   params: { amount: 100, currency: "USD" },
 *   policy: "finance-controls",
 * });
 *
 * if (result.verified) {
 *   // Action is approved — execute it
 *   await executePayment(result);
 * } else {
 *   // Blocked — result.reason explains why
 *   console.log("Blocked:", result.reason);
 * }
 * ```
 */
export class Veritera {
  private readonly config: HttpConfig;
  private readonly failClosed: boolean;

  constructor(options: VeriteraConfig) {
    if (!options.apiKey) {
      throw new Error("Forge SDK: apiKey is required");
    }
    this.config = {
      baseUrl: (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, ""),
      apiKey: options.apiKey,
      timeout: options.timeout ?? DEFAULT_TIMEOUT,
      maxRetries: options.maxRetries ?? DEFAULT_MAX_RETRIES,
      debug: options.debug ?? false,
    };
    this.failClosed = options.failClosed ?? DEFAULT_FAIL_CLOSED;
  }

  // ── Core: Verify a Decision ──

  /**
   * Verify an AI agent decision against policy constraints.
   * Returns in <50ms for DPE mode (default).
   *
   * @param request - Verification parameters
   * @returns Verification result with verdict, constraints, and attestation
   */
  async verifyDecision(request: VerifyRequest): Promise<VerifyResponse> {
    const body: Record<string, unknown> = {
      agent_id: request.agentId,
      action: request.action,
    };

    if (request.params) body.params = request.params;
    if (request.policy) body.policy = request.policy;
    if (request.allowedActions) body.allowed_actions = request.allowedActions;
    if (request.delegationId) body.delegation_id = request.delegationId;
    if (request.requireZkProof) body.require_zk_proof = true;

    try {
      const raw = await httpRequest<Record<string, unknown>>(this.config, {
        method: "POST",
        path: "/v1/verify",
        body,
        idempotencyKey: request.idempotencyKey,
      });

      return this.mapVerifyResponse(raw);
    } catch (err) {
      if (this.failClosed) {
        return {
          verified: false,
          verdict: "denied",
          decisionId: "",
          proofId: "",
          verificationId: "",
          agentId: request.agentId,
          action: request.action,
          policy: request.policy ?? null,
          reason: `Forge unavailable — action denied (fail-closed): ${err instanceof Error ? err.message : String(err)}`,
          mode: "dpe",
          proofStatus: "not_requested",
          evaluatedConstraints: [],
          verification: {
            mode: "fail-closed",
            keyVersion: 0,
            attestation: "",
            attestationHash: "",
            attestationPayload: {},
            publicKey: "",
            policyHash: null,
          },
          denialProof: null,
          auditId: "",
          latencyMs: 0,
          timestamp: "",
        };
      }
      throw err;
    }
  }

  // ── Proof Retrieval ──

  /**
   * Retrieve a verification proof by ID.
   * Use this to fetch ZKP proofs that were generated asynchronously.
   *
   * @param proofId - The proof ID from verifyDecision()
   * @returns Proof details when available
   */
  async getProof(proofId: string): Promise<ProofResponse> {
    const raw = await httpRequest<Record<string, unknown>>(this.config, {
      method: "GET",
      path: `/v1/proofs/${encodeURIComponent(proofId)}`,
    });

    return {
      proofId: String(raw.proof_id ?? ""),
      agentId: String(raw.agent_id ?? ""),
      action: String(raw.action ?? ""),
      verified: Boolean(raw.verified),
      reason: raw.reason as string | null,
      proof: raw.proof,
      latencyMs: Number(raw.latency_ms ?? 0),
      auditId: String(raw.audit_id ?? ""),
      timestamp: String(raw.timestamp ?? ""),
    };
  }

  // ── Local Proof Verification ──

  /**
   * Verify a DPE attestation locally without any backend call.
   * Useful for independent verification and offline validation.
   *
   * @param verification - The verification object from verifyDecision()
   * @returns Whether the attestation signature is valid
   */
  async verifyProofLocally(verification: {
    attestation: string;
    attestationPayload: Record<string, unknown>;
    publicKey: string;
    keyVersion?: number;
  }): Promise<LocalVerifyResult> {
    return verifyAttestationLocally(
      verification.attestation,
      verification.attestationPayload,
      verification.publicKey,
      verification.keyVersion,
    );
  }

  // ── Delegation ──

  /**
   * Create a scoped delegation for an agent.
   * Defines what actions the agent is allowed to take.
   *
   * @param request - Delegation parameters
   * @returns Delegation details with ID and scope
   */
  async createDelegation(request: DelegateRequest): Promise<DelegateResponse> {
    const raw = await httpRequest<Record<string, unknown>>(this.config, {
      method: "POST",
      path: "/v1/delegate",
      body: {
        agent_id: request.agentId,
        allowed_actions: request.allowedActions,
        constraints: request.constraints,
        expires_in: request.expiresIn,
      },
    });

    return {
      delegationId: String(raw.delegation_id ?? ""),
      agentId: String(raw.agent_id ?? ""),
      scope: (raw.scope as string[]) ?? [],
      expiresAt: String(raw.expires_at ?? ""),
      status: String(raw.status ?? "active"),
      timestamp: String(raw.timestamp ?? ""),
    };
  }

  // ── Usage ──

  /**
   * Get usage statistics for the current billing period.
   *
   * @param period - Billing period in YYYY-MM format (default: current month)
   */
  async getUsage(period?: string): Promise<UsageResponse> {
    const path = period ? `/v1/usage?period=${encodeURIComponent(period)}` : "/v1/usage";
    return httpRequest<UsageResponse>(this.config, {
      method: "GET",
      path,
    });
  }

  // ── Health Check ──

  /**
   * Check Forge Verify API health status.
   */
  async health(): Promise<{ status: string; latency: { p50: number; p99: number } }> {
    return httpRequest(this.config, {
      method: "GET",
      path: "/v1/health",
    });
  }

  // ── Response Mapping ──

  private mapVerifyResponse(raw: Record<string, unknown>): VerifyResponse {
    const verification = raw.verification as Record<string, unknown> | undefined;
    const evaluatedConstraints = (raw.evaluated_constraints as Array<Record<string, unknown>>) ?? [];

    // Map denial proof if present (PRD 4.3.1)
    const rawDenialProof = raw.denial_proof as Record<string, unknown> | undefined;
    const denialProof: DenialProof | null = rawDenialProof ? {
      denialId: String(rawDenialProof.denial_id ?? ""),
      actionAttempted: String(rawDenialProof.action_attempted ?? ""),
      timestamp: String(rawDenialProof.timestamp ?? ""),
      agentIdHash: String(rawDenialProof.agent_id_hash ?? ""),
      policyName: String(rawDenialProof.policy_name ?? ""),
      policyHash: String(rawDenialProof.policy_hash ?? ""),
      constraintType: String(rawDenialProof.constraint_type ?? ""),
      constraintDetail: String(rawDenialProof.constraint_detail ?? ""),
      parameterHash: String(rawDenialProof.parameter_hash ?? ""),
      source: String(rawDenialProof.source ?? "dpe"),
      signature: String(rawDenialProof.signature ?? ""),
      denialHash: String(rawDenialProof.denial_hash ?? ""),
      previousDenialHash: (rawDenialProof.previous_denial_hash as string) ?? null,
      chainIndex: Number(rawDenialProof.chain_index ?? 0),
    } : null;

    return {
      verified: Boolean(raw.verified),
      verdict: (raw.verdict as "approved" | "denied") ?? (raw.verified ? "approved" : "denied"),
      decisionId: String(raw.decision_id ?? ""),
      proofId: String(raw.proof_id ?? ""),
      verificationId: String(raw.verification_id ?? raw.decision_id ?? ""),
      agentId: String(raw.agent_id ?? ""),
      action: String(raw.action ?? ""),
      policy: (raw.policy as string) ?? null,
      reason: (raw.reason as string) ?? null,
      mode: (raw.mode as "dpe" | "zkp") ?? "dpe",
      proofStatus: (raw.proof_status as "not_requested" | "pending" | "available") ?? "not_requested",
      evaluatedConstraints: evaluatedConstraints.map(c => ({
        type: String(c.type ?? ""),
        result: (c.result as "pass" | "fail" | "skip") ?? "skip",
        detail: (c.detail as string) ?? null,
      })),
      verification: {
        mode: String(verification?.mode ?? "dpe"),
        keyVersion: Number(verification?.key_version ?? 1),
        attestation: String(verification?.attestation ?? ""),
        attestationHash: String(verification?.attestation_hash ?? ""),
        attestationPayload: (verification?.attestation_payload as Record<string, unknown>) ?? {},
        publicKey: String(verification?.public_key ?? ""),
        policyHash: (verification?.policy_hash as string) ?? null,
      },
      denialProof,
      auditId: String(raw.audit_id ?? ""),
      latencyMs: Number(raw.latency_ms ?? 0),
      timestamp: String(raw.timestamp ?? ""),
    };
  }
}
