/**
 * Forge Mastra Adapter
 * ====================
 * Verification integration for Mastra agents.
 * Intercepts tool calls, wraps tools, and provides middleware
 * to verify every agent action through Forge before execution.
 *
 * Usage:
 *   import { ForgeIntegration, forgeMiddleware, forgeVerifyTool, forgeWrapTool }
 *     from "@veritera.ai/forge-mastra";
 *
 * Every action your agent takes is verified before execution.
 * Blocked actions never reach your tools.
 */

import { Veritera as ForgeClient } from "@veritera.ai/forge-verify";
import type { VerifyResponse } from "@veritera.ai/forge-verify";

// ── Re-exports ──

export type { VerifyResponse } from "@veritera.ai/forge-verify";

// ── Types ──

/** Configuration shared across all Forge Mastra exports. */
export interface ForgeConfig {
  /** Forge API key (vt_live_... or vt_test_...). Falls back to VERITERA_API_KEY env var. */
  apiKey?: string;
  /** Base URL for Forge API (default: https://forge.veritera.ai) */
  baseUrl?: string;
  /** Agent identifier (default: "mastra-agent") */
  agentId?: string;
  /** Policy name to evaluate against */
  policy?: string;
  /** Block action when verification service errors (default: true) */
  failClosed?: boolean;
  /** Request timeout in milliseconds (default: 10000) */
  timeout?: number;
  /** Actions to skip verification for (e.g., ["read_file", "list_dir"]) */
  skipActions?: string[];
  /** Called when an action is verified and allowed */
  onVerified?: (action: string, result: VerifyResponse) => void;
  /** Called when an action is blocked */
  onBlocked?: (action: string, reason: string | null, result: VerifyResponse) => void;
}

/** Result returned from verification checks. */
export interface ForgeVerifyResult {
  verified: boolean;
  action: string;
  verificationId?: string;
  latencyMs?: number;
  reason?: string | null;
  raw?: VerifyResponse;
}

// ── Internal helpers ──

const PREFIX = "[forge-mastra]";

function resolveApiKey(config: ForgeConfig): string {
  const key = config.apiKey || process.env.VERITERA_API_KEY;
  if (!key) {
    throw new Error(
      `${PREFIX} apiKey is required. Pass it in config or set the VERITERA_API_KEY environment variable.`,
    );
  }
  return key;
}

function createClient(config: ForgeConfig): InstanceType<typeof ForgeClient> {
  return new ForgeClient({
    apiKey: resolveApiKey(config),
    baseUrl: config.baseUrl,
    timeout: config.timeout,
    failClosed: config.failClosed ?? true,
  });
}

async function verifyAction(
  client: InstanceType<typeof ForgeClient>,
  config: ForgeConfig,
  action: string,
  params: Record<string, unknown>,
): Promise<ForgeVerifyResult> {
  const skipActions = new Set(config.skipActions ?? []);

  if (skipActions.has(action)) {
    console.debug(`${PREFIX} Skipping verification for: ${action}`);
    return { verified: true, action };
  }

  const agentId = config.agentId ?? "mastra-agent";

  try {
    const result = await client.verifyDecision({
      agentId,
      action,
      params,
      policy: config.policy,
    });

    console.debug(
      `${PREFIX} ${result.verified ? "VERIFIED" : "BLOCKED"}: ${action} (${result.latencyMs}ms)`,
    );

    if (result.verified) {
      config.onVerified?.(action, result);
    } else {
      config.onBlocked?.(action, result.reason, result);
    }

    return {
      verified: result.verified,
      action,
      verificationId: result.verificationId,
      latencyMs: result.latencyMs,
      reason: result.reason,
      raw: result,
    };
  } catch (err) {
    const failClosed = config.failClosed ?? true;
    const message = err instanceof Error ? err.message : String(err);
    console.debug(`${PREFIX} Verification error for ${action}: ${message}`);

    if (failClosed) {
      const reason = `Verification service error — action blocked (fail-closed): ${message}`;
      return { verified: false, action, reason };
    }

    // fail-open: allow on error
    console.debug(`${PREFIX} Fail-open: allowing ${action} despite error`);
    return { verified: true, action };
  }
}

// ── Error ──

/** Thrown when Forge blocks an action. */
export class ForgeBlockedError extends Error {
  public readonly action: string;
  public readonly reason: string | null;
  public readonly verificationId?: string;

  constructor(result: ForgeVerifyResult) {
    const msg = result.reason ?? "Action blocked by Forge verification";
    super(msg);
    this.name = "ForgeBlockedError";
    this.action = result.action;
    this.reason = result.reason ?? null;
    this.verificationId = result.verificationId;
  }
}

// ═══════════════════════════════════════════════════════
// 1. ForgeIntegration — Mastra Integration class
// ═══════════════════════════════════════════════════════

/**
 * Forge integration for Mastra.
 * Provides a shared verification client for use across agents, tools, and middleware.
 *
 * @example
 * ```ts
 * import { ForgeIntegration } from "@veritera.ai/forge-mastra";
 *
 * const forge = new ForgeIntegration({
 *   apiKey: "vt_live_...",
 *   policy: "production-safety",
 * });
 *
 * // Verify an action directly
 * const result = await forge.verify("payment.create", { amount: 500 });
 * if (!result.verified) console.log("Blocked:", result.reason);
 *
 * // Access the underlying Forge client
 * const client = forge.getClient();
 * ```
 */
export class ForgeIntegration {
  /** Integration name for Mastra registration */
  readonly name = "forge";
  /** Human-readable label */
  readonly label = "Forge Verify";

  private readonly client: InstanceType<typeof ForgeClient>;
  private readonly config: ForgeConfig;

  constructor(config: ForgeConfig) {
    this.config = { ...config };
    this.client = createClient(this.config);
  }

  /**
   * Verify an action against Forge policies.
   *
   * @param action - The action name (e.g., "payment.create", "file.write")
   * @param params - Action parameters
   * @returns Verification result
   */
  async verify(
    action: string,
    params: Record<string, unknown> = {},
  ): Promise<ForgeVerifyResult> {
    return verifyAction(this.client, this.config, action, params);
  }

  /**
   * Verify and throw if blocked.
   * Convenience method for inline guard clauses.
   *
   * @param action - Action name
   * @param params - Action parameters
   * @throws ForgeBlockedError if the action is denied
   */
  async verifyOrThrow(
    action: string,
    params: Record<string, unknown> = {},
  ): Promise<ForgeVerifyResult> {
    const result = await this.verify(action, params);
    if (!result.verified) {
      throw new ForgeBlockedError(result);
    }
    return result;
  }

  /**
   * Get the underlying Forge SDK client for direct API access.
   */
  getClient(): InstanceType<typeof ForgeClient> {
    return this.client;
  }
}

// ═══════════════════════════════════════════════════════
// 2. forgeVerifyTool — Mastra Tool for explicit verification
// ═══════════════════════════════════════════════════════

/**
 * A Mastra-compatible tool definition that agents can call to explicitly
 * verify an action before taking it.
 *
 * @example
 * ```ts
 * import { Agent } from "@mastra/core";
 * import { forgeVerifyTool } from "@veritera.ai/forge-mastra";
 *
 * const agent = new Agent({
 *   tools: {
 *     forge_verify: forgeVerifyTool({ policy: "finance-controls" }),
 *   },
 * });
 * ```
 */
export function forgeVerifyTool(config: ForgeConfig = {}): ForgeVerifyToolDef {
  const client = createClient(config);

  return {
    name: "forge_verify",
    description:
      "Verify an action against Forge safety policies before executing it. " +
      "Returns whether the action is allowed or blocked, with a reason if blocked.",
    inputSchema: {
      type: "object" as const,
      properties: {
        action: {
          type: "string" as const,
          description: "The action to verify (e.g., 'payment.create', 'file.delete')",
        },
        params: {
          type: "object" as const,
          description: "Parameters for the action (e.g., { amount: 500, currency: 'USD' })",
        },
      },
      required: ["action"] as const,
    },
    execute: async (input: { action: string; params?: Record<string, unknown> }) => {
      const result = await verifyAction(client, config, input.action, input.params ?? {});
      return {
        verified: result.verified,
        action: result.action,
        reason: result.reason ?? null,
        verificationId: result.verificationId ?? null,
        latencyMs: result.latencyMs ?? null,
      };
    },
  };
}

/** Shape of the tool definition returned by forgeVerifyTool. */
export interface ForgeVerifyToolDef {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<string, unknown>;
    required: readonly string[];
  };
  execute: (input: {
    action: string;
    params?: Record<string, unknown>;
  }) => Promise<{
    verified: boolean;
    action: string;
    reason: string | null;
    verificationId: string | null;
    latencyMs: number | null;
  }>;
}

// ═══════════════════════════════════════════════════════
// 3. forgeMiddleware — Wraps tool execution with verification
// ═══════════════════════════════════════════════════════

/** Context passed to middleware functions. */
export interface MiddlewareContext {
  toolName: string;
  toolArgs: Record<string, unknown>;
  [key: string]: unknown;
}

/** Middleware function signature compatible with Mastra's middleware system. */
export type ForgeMiddlewareFn = (
  context: MiddlewareContext,
  next: () => Promise<unknown>,
) => Promise<unknown>;

/**
 * Create middleware that verifies every tool call through Forge before execution.
 *
 * @example
 * ```ts
 * import { forgeMiddleware } from "@veritera.ai/forge-mastra";
 *
 * const middleware = forgeMiddleware({
 *   policy: "production-safety",
 *   failClosed: true,
 * });
 *
 * // Register with Mastra agent
 * const agent = new Agent({
 *   middleware: [middleware],
 * });
 * ```
 */
export function forgeMiddleware(config: ForgeConfig = {}): ForgeMiddlewareFn {
  const client = createClient(config);

  return async (context: MiddlewareContext, next: () => Promise<unknown>) => {
    const action = context.toolName;
    const params = context.toolArgs ?? {};

    const result = await verifyAction(client, config, action, params);

    if (!result.verified) {
      throw new ForgeBlockedError(result);
    }

    // Attach verification metadata to context for downstream use
    (context as Record<string, unknown>).forgeVerification = result;

    return next();
  };
}

// ═══════════════════════════════════════════════════════
// 4. forgeWrapTool — Wrap any Mastra tool with verification
// ═══════════════════════════════════════════════════════

/** Minimal shape of a Mastra tool that can be wrapped. */
export interface MastraTool<TInput = any, TOutput = any> {
  name: string;
  description?: string;
  inputSchema?: unknown;
  execute: (input: TInput) => Promise<TOutput>;
  [key: string]: unknown;
}

/** Options for wrapping a tool, extends ForgeConfig with per-tool overrides. */
export interface WrapToolOptions extends ForgeConfig {
  /** Override the action name sent to Forge (default: tool.name) */
  actionName?: string;
}

/**
 * Wrap any Mastra tool with Forge verification.
 * The wrapped tool verifies the action before executing the original.
 * If verification fails, a ForgeBlockedError is thrown and the tool never runs.
 *
 * @example
 * ```ts
 * import { forgeWrapTool } from "@veritera.ai/forge-mastra";
 *
 * const protectedTool = forgeWrapTool(myPaymentTool, {
 *   policy: "finance-controls",
 *   failClosed: true,
 * });
 *
 * const agent = new Agent({
 *   tools: { payment: protectedTool },
 * });
 * ```
 */
export function forgeWrapTool<TInput extends Record<string, unknown>, TOutput>(
  tool: MastraTool<TInput, TOutput>,
  options: WrapToolOptions = {},
): MastraTool<TInput, TOutput> {
  const client = createClient(options);
  const actionName = options.actionName ?? tool.name;

  return {
    ...tool,
    execute: async (input: TInput): Promise<TOutput> => {
      const result = await verifyAction(client, options, actionName, input);

      if (!result.verified) {
        throw new ForgeBlockedError(result);
      }

      console.debug(
        `${PREFIX} Tool "${tool.name}" verified (${result.latencyMs}ms), executing...`,
      );

      return tool.execute(input);
    },
  };
}

// ── Default export ──

export default ForgeIntegration;
