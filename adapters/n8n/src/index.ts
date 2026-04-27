/**
 * n8n-nodes-eydii
 * ===============
 * EYDII community nodes for n8n.
 * Verify every AI agent action before execution.
 *
 * Exports:
 *   - EydiiVerifyNode: Main verification node (2 outputs: Allowed / Denied)
 *   - EydiiCredentials: API key credential type
 */

export { EydiiVerifyNode } from "./EydiiVerifyNode";
export { EydiiCredentials } from "./EydiiCredentials";
