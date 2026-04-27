/**
 * Forge OpenClaw Skill
 * ===================
 * Verification skill for OpenClaw agents.
 * Intercepts every tool call and verifies it through Forge before execution.
 *
 * Usage:
 *   import { ForgeSkill } from "@veritera.ai/forge-openclaw"
 *
 *   const skill = new ForgeSkill({ apiKey: "vt_live_..." })
 *   agent.addSkill(skill)
 *
 * Every action your agent takes is now verified before execution.
 * Blocked actions never reach your tools.
 */

import { Veritera as Forge } from "@veritera.ai/forge-verify";
import type { VerifyResponse } from "@veritera.ai/forge-verify";

// ── Types ──

export interface ForgeSkillConfig {
  /** Forge API key (vt_live_... or vt_test_...) */
  apiKey: string;
  /** Base URL for Forge API (default: https://forge.veritera.ai) */
  baseUrl?: string;
  /** Policy name to evaluate against (optional) */
  policy?: string;
  /** Agent ID override (default: auto-detected from OpenClaw context) */
  agentId?: string;
  /** Actions to skip verification for (e.g., ["read_file", "list_dir"]) */
  skipActions?: string[];
  /** Called when an action is blocked */
  onBlocked?: (action: string, reason: string | null, result: VerifyResponse) => void;
  /** Called when an action is verified */
  onVerified?: (action: string, result: VerifyResponse) => void;
  /** Enable debug logging */
  debug?: boolean;
}

export interface ToolCall {
  name: string;
  arguments?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface SkillResult {
  verified: boolean;
  action: string;
  verificationId?: string;
  latencyMs?: number;
  reason?: string | null;
}

// ── Forge OpenClaw Skill ──

export class ForgeSkill {
  private forge: InstanceType<typeof Forge>;
  private policy: string | undefined;
  private agentId: string;
  private skipActions: Set<string>;
  private onBlocked?: ForgeSkillConfig["onBlocked"];
  private onVerified?: ForgeSkillConfig["onVerified"];
  private debug: boolean;

  /** Skill metadata for OpenClaw registration */
  static readonly skillName = "forge-verify";
  static readonly version = "1.1.2";
  static readonly description = "Forge verification — verifies every action before execution";

  constructor(config: ForgeSkillConfig) {
    if (!config.apiKey) {
      throw new Error("Forge OpenClaw Skill: apiKey is required");
    }

    this.forge = new Forge({
      apiKey: config.apiKey,
      baseUrl: config.baseUrl,
    });
    this.policy = config.policy;
    this.agentId = config.agentId ?? "openclaw-agent";
    this.skipActions = new Set(config.skipActions ?? []);
    this.onBlocked = config.onBlocked;
    this.onVerified = config.onVerified;
    this.debug = config.debug ?? false;
  }

  /**
   * Verify a tool call before execution.
   * Returns the verification result. If not verified, the action should be blocked.
   *
   * @param toolCall - The OpenClaw tool call to verify
   * @returns SkillResult with verification status
   */
  async verify(toolCall: ToolCall): Promise<SkillResult> {
    const action = toolCall.name;

    // Skip verification for whitelisted actions
    if (this.skipActions.has(action)) {
      if (this.debug) console.log(`[Forge] Skipping verification for: ${action}`);
      return { verified: true, action };
    }

    try {
      const result = await this.forge.verifyDecision({
        agentId: this.agentId,
        action,
        params: (toolCall.arguments ?? {}) as Record<string, unknown>,
        policy: this.policy,
      });

      if (this.debug) {
        console.log(`[Forge] ${result.verified ? "✔ VERIFIED" : "✗ BLOCKED"}: ${action} (${result.latencyMs}ms)`);
      }

      if (result.verified) {
        this.onVerified?.(action, result);
      } else {
        this.onBlocked?.(action, result.reason, result);
      }

      return {
        verified: result.verified,
        action,
        verificationId: result.verificationId,
        latencyMs: result.latencyMs,
        reason: result.reason,
      };
    } catch (err) {
      // Fail-closed: if verification service is unreachable, block the action
      if (this.debug) {
        console.error(`[Forge] Verification failed for ${action}:`, err);
      }
      return {
        verified: false,
        action,
        reason: "Verification service unreachable — action blocked (fail-closed)",
      };
    }
  }

  /**
   * Pre-execution interceptor for OpenClaw.
   * Register this as a skill hook to verify every action automatically.
   *
   * @param toolCall - The tool call from OpenClaw
   * @returns The tool call if verified, null if blocked
   */
  async intercept(toolCall: ToolCall): Promise<ToolCall | null> {
    const result = await this.verify(toolCall);
    if (!result.verified) {
      return null; // Blocked — OpenClaw will not execute this tool call
    }
    return toolCall; // Verified — proceed with execution
  }

  /**
   * Express/Connect-style middleware for custom integrations.
   * Verifies the action in req.body and blocks if denied.
   */
  middleware() {
    return async (req: any, res: any, next: any) => {
      const toolCall: ToolCall = {
        name: req.body?.action ?? req.body?.name ?? "unknown",
        arguments: req.body?.params ?? req.body?.arguments ?? {},
      };

      const result = await this.verify(toolCall);

      if (!result.verified) {
        return res.status(403).json({
          blocked: true,
          action: toolCall.name,
          reason: result.reason,
          verificationId: result.verificationId,
        });
      }

      // Attach verification result to request for downstream use
      req.forgeVerification = result;
      next();
    };
  }

  /**
   * Get the Forge client instance for direct API access.
   */
  getClient(): InstanceType<typeof Forge> {
    return this.forge;
  }
}

// Default export for convenience
export default ForgeSkill;
