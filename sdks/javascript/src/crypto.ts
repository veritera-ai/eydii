// ===============================================
// Veritera Forge Verify SDK — Cryptographic Verification
// ===============================================
// Ed25519 attestation verification for client-side proof checking.
// Works in Node.js 18+ (crypto module) and browsers (Web Crypto API).

import type { LocalVerifyResult } from "./types.js";

/**
 * Verify a DPE attestation locally without any network call.
 * Uses Ed25519 signature verification.
 *
 * @param attestation - Base64 encoded Ed25519 signature
 * @param attestationPayload - The signed payload object
 * @param publicKey - Base64 DER SPKI public key
 * @param keyVersion - Key version (for tracking)
 * @returns Verification result with validity status
 */
export async function verifyAttestationLocally(
  attestation: string,
  attestationPayload: Record<string, unknown>,
  publicKey: string,
  keyVersion?: number,
): Promise<LocalVerifyResult> {
  const payloadBytes = new TextEncoder().encode(JSON.stringify(attestationPayload));
  const payloadHash = await sha256Hex(payloadBytes);

  try {
    // Try Node.js crypto first (faster, available in Node 18+)
    if (typeof globalThis.process !== "undefined" && globalThis.process.versions?.node) {
      const valid = await verifyWithNodeCrypto(attestation, attestationPayload, publicKey);
      return { valid, keyVersion: keyVersion ?? null, payloadHash, algorithm: "Ed25519" };
    }

    // Fall back to Web Crypto API (browsers)
    const valid = await verifyWithWebCrypto(attestation, payloadBytes, publicKey);
    return { valid, keyVersion: keyVersion ?? null, payloadHash, algorithm: "Ed25519" };

  } catch {
    return { valid: false, keyVersion: keyVersion ?? null, payloadHash, algorithm: "Ed25519" };
  }
}

/** Node.js crypto verification */
async function verifyWithNodeCrypto(
  signatureBase64: string,
  payload: Record<string, unknown>,
  publicKeyBase64: string,
): Promise<boolean> {
  const crypto = await import("crypto");
  const data = JSON.stringify(payload);
  const signature = Buffer.from(signatureBase64, "base64");
  const pubKeyDer = Buffer.from(publicKeyBase64, "base64");
  const pubKey = crypto.createPublicKey({ key: pubKeyDer, format: "der", type: "spki" });
  return crypto.verify(null, Buffer.from(data), pubKey, signature);
}

/** Web Crypto API verification (browsers) */
async function verifyWithWebCrypto(
  signatureBase64: string,
  payloadBytes: Uint8Array,
  publicKeyBase64: string,
): Promise<boolean> {
  const signatureBytes = base64ToArrayBuffer(signatureBase64);
  const publicKeyBytes = base64ToArrayBuffer(publicKeyBase64);

  const key = await crypto.subtle.importKey(
    "spki",
    publicKeyBytes,
    { name: "Ed25519" },
    false,
    ["verify"],
  );

  return crypto.subtle.verify("Ed25519", key, signatureBytes, payloadBytes);
}

/** SHA-256 hex digest */
async function sha256Hex(data: Uint8Array): Promise<string> {
  if (typeof globalThis.process !== "undefined" && globalThis.process.versions?.node) {
    const crypto = await import("crypto");
    return crypto.createHash("sha256").update(data).digest("hex");
  }
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, "0")).join("");
}

/** Convert base64 string to ArrayBuffer */
function base64ToArrayBuffer(base64: string): ArrayBuffer {
  if (typeof Buffer !== "undefined") {
    const buf = Buffer.from(base64, "base64");
    return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  }
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}
