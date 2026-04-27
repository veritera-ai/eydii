// ===============================================
// Forge Verify SDK
// ===============================================
// The verification layer for AI-driven decisions.
//
// Usage:
//   import { ForgeVerify } from '@veritera.ai/forge-verify';
//   const forge = new ForgeVerify({ apiKey: 'vt_live_...' });
//   const result = await forge.verifyDecision({ agentId: 'a1', action: 'pay', params: { amount: 100 } });

import { Veritera } from "./client.js";

// Primary export: ForgeVerify (V1 product name)
export const ForgeVerify = Veritera;
export default Veritera;

// Backward compatibility aliases
export const Forge = Veritera;
export { Veritera } from "./client.js";

export { verifyAttestationLocally } from "./crypto.js";
export type {
  VeriteraConfig,
  VerifyRequest,
  VerifyResponse,
  DenialProof,
  ProofResponse,
  LocalVerifyResult,
  DelegateRequest,
  DelegateResponse,
  UsageResponse,
  ConstraintResult,
} from "./types.js";
export { ForgeError, RateLimitError } from "./types.js";
