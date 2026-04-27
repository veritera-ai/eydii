// ===============================================
// Veritera Forge Verify SDK — Type Definitions
// ===============================================

/** SDK configuration */
export interface VeriteraConfig {
  /** API key (vt_live_... or vt_test_...) */
  apiKey: string;
  /** Base URL for Forge Verify API (default: https://forge.veritera.ai) */
  baseUrl?: string;
  /** Request timeout in milliseconds (default: 10000) */
  timeout?: number;
  /** Max retries on 5xx errors (default: 2) */
  maxRetries?: number;
  /** Enable debug logging (default: false) */
  debug?: boolean;
  /** Return denied instead of throwing on network/server errors (default: true) */
  failClosed?: boolean;
}

/** Constraint evaluation result from the policy engine */
export interface ConstraintResult {
  type: string;
  result: "pass" | "fail" | "skip";
  detail: string | null;
}

/** Verification request */
export interface VerifyRequest {
  /** Unique identifier for the agent */
  agentId: string;
  /** Action being attempted (e.g., "payment.create") */
  action: string;
  /** Action parameters (e.g., { amount: 100, currency: "USD" }) */
  params?: Record<string, unknown>;
  /** Policy name to evaluate against */
  policy?: string;
  /** Allowed actions scope (used when no policy specified) */
  allowedActions?: string[];
  /** Existing delegation ID to use */
  delegationId?: string;
  /** Request ZKP proof (async, enterprise only) */
  requireZkProof?: boolean;
  /** Idempotency key (prevents duplicate processing) */
  idempotencyKey?: string;
}

/** Denial proof (PRD 4.3.1 — first-class proof object for every DENY) */
export interface DenialProof {
  /** Unique ID: DNY-XXXX-XXXX format */
  denialId: string;
  /** Action the agent attempted */
  actionAttempted: string;
  /** ISO timestamp of the denial */
  timestamp: string;
  /** Content-blind: SHA-256 hash of the agent ID */
  agentIdHash: string;
  /** Policy that was evaluated */
  policyName: string;
  /** SHA-256 hash of the policy rules */
  policyHash: string;
  /** The constraint type that triggered the denial */
  constraintType: string;
  /** The constraint detail/reason */
  constraintDetail: string;
  /** Content-blind: SHA-256 hash of the request parameters */
  parameterHash: string;
  /** Source path: "dpe", "sidecar", or "health" */
  source: string;
  /** Cryptographic signature */
  signature: string;
  /** Hash of this denial proof (for chain verification) */
  denialHash: string;
  /** Hash of the previous denial proof in the chain */
  previousDenialHash: string | null;
  /** Position in the denial chain */
  chainIndex: number;
}

/** Verification response */
export interface VerifyResponse {
  /** Whether the action was approved */
  verified: boolean;
  /** Verdict: approved, denied */
  verdict: "approved" | "denied";
  /** Decision ID (VER-XXXX-XXXX format) — human-readable unique ID */
  decisionId: string;
  /** Proof ID for this verification */
  proofId: string;
  /** Agent ID */
  agentId: string;
  /** Action that was verified */
  action: string;
  /** Policy name used (if any) */
  policy: string | null;
  /** Reason for denial (null if approved) */
  reason: string | null;
  /** Verification ID (VER-XXXX-XXXX format) — use this to retrieve proof later */
  verificationId: string;
  /** Verification mode */
  mode: "dpe" | "zkp";
  /** Proof generation status */
  proofStatus: "not_requested" | "pending" | "available";
  /** Per-constraint evaluation results */
  evaluatedConstraints: ConstraintResult[];
  /** Verification details */
  verification: {
    mode: string;
    keyVersion: number;
    attestation: string;
    attestationHash: string;
    attestationPayload: Record<string, unknown>;
    publicKey: string;
    policyHash: string | null;
  };
  /** Denial proof — present on every DENY verdict (PRD 4.3.1) */
  denialProof: DenialProof | null;
  /** Audit trail ID */
  auditId: string;
  /** Verification latency in milliseconds */
  latencyMs: number;
  /** ISO 8601 timestamp */
  timestamp: string;
}

/** Proof retrieval response */
export interface ProofResponse {
  proofId: string;
  agentId: string;
  action: string;
  verified: boolean;
  reason: string | null;
  proof: unknown;
  latencyMs: number;
  auditId: string;
  timestamp: string;
}

/** Local proof verification result */
export interface LocalVerifyResult {
  valid: boolean;
  keyVersion: number | null;
  payloadHash: string;
  algorithm: string;
}

/** Delegation request */
export interface DelegateRequest {
  agentId: string;
  allowedActions: string[];
  constraints?: Record<string, unknown>;
  expiresIn?: string;
}

/** Delegation response */
export interface DelegateResponse {
  delegationId: string;
  agentId: string;
  scope: string[];
  expiresAt: string;
  status: string;
  timestamp: string;
}

/** Usage statistics */
export interface UsageResponse {
  tier: string;
  billingPeriod: string;
  usage: {
    totalCalls: number;
    verifications: number;
    delegations: number;
    anchors: number;
  };
  limits: {
    monthlyLimit: number;
    callsRemaining: number | string;
  };
  billing: {
    baseFee: number;
    includedCalls: number;
    overageCalls: number;
    overageRate: number;
    overageCost: number;
    totalEstimated: number;
    currency: string;
  };
}

/** SDK error with structured details */
export class ForgeError extends Error {
  public readonly code: string;
  public readonly status: number;
  public readonly details: unknown;

  constructor(message: string, code: string, status: number, details?: unknown) {
    super(message);
    this.name = "ForgeError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

/** Rate limit error */
export class RateLimitError extends ForgeError {
  public readonly retryAfterMs: number;

  constructor(message: string, retryAfterMs: number) {
    super(message, "rate_limited", 429);
    this.name = "RateLimitError";
    this.retryAfterMs = retryAfterMs;
  }
}
