/**
 * EYDII Node for n8n
 * =========================
 * Verifies every AI agent action against EYDII policies before execution.
 *
 * Two outputs:
 *   Output 1 ("Allowed") — action passed verification, continue workflow
 *   Output 2 ("Denied")  — action blocked by policy or EYDII unreachable (fail-closed)
 *
 * Every output item includes proof_id, verdict, reason, and latency_ms
 * for full audit trail visibility.
 */

import type {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
} from "n8n-workflow";
import { NodeOperationError } from "n8n-workflow";
import { EydiiVerify } from "@veritera.ai/eydii";
import type { VerifyResponse } from "@veritera.ai/eydii";

export class EydiiVerifyNode implements INodeType {
  description: INodeTypeDescription = {
    displayName: "EYDII",
    name: "eydiiVerify",
    icon: "file:eydii.svg",
    group: ["transform"],
    version: 1,
    subtitle: '={{$parameter["action"]}}',
    description:
      "Verify AI agent actions against EYDII policies before execution. Allowed actions pass through; denied actions are routed separately.",
    defaults: {
      name: "EYDII",
    },
    inputs: ["main"],
    outputs: ["main", "main"],
    outputNames: ["Allowed", "Denied"],
    credentials: [
      {
        name: "eydiiApi",
        required: true,
      },
    ],
    properties: [
      {
        displayName: "Action",
        name: "action",
        type: "string",
        default: "",
        required: true,
        placeholder: "e.g. payment.create",
        description:
          "The action being attempted. Use dot-notation for namespacing (e.g. payment.create, email.send).",
      },
      {
        displayName: "Parameters (JSON)",
        name: "params",
        type: "json",
        default: "{}",
        description:
          "Action parameters as a JSON object. These are evaluated against policy constraints (e.g. amount limits, allowed recipients).",
      },
      {
        displayName: "Policy",
        name: "policy",
        type: "string",
        default: "",
        placeholder: "e.g. finance-controls",
        description:
          "Policy name to evaluate against. Leave empty to use the default policy for your API key.",
      },
      {
        displayName: "Agent ID",
        name: "agentId",
        type: "string",
        default: "n8n-workflow",
        required: true,
        description:
          "Unique identifier for the agent performing this action. Used for audit trails and per-agent policy scoping.",
      },
      {
        displayName: "Fail Closed",
        name: "failClosed",
        type: "boolean",
        default: true,
        description:
          "Whether to route to the Denied output when EYDII is unreachable. When enabled (recommended), network failures block the action rather than allowing it through unverified.",
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const allowed: INodeExecutionData[] = [];
    const denied: INodeExecutionData[] = [];

    // Retrieve credentials
    const credentials = await this.getCredentials("eydiiApi");
    if (!credentials?.apiKey) {
      throw new NodeOperationError(
        this.getNode(),
        "EYDII API key is missing. Add your credentials under Settings > Credentials > EYDII API.",
      );
    }

    const apiKey = credentials.apiKey as string;
    const baseUrl = (credentials.baseUrl as string) || "https://id.veritera.ai";

    // Read node parameters (same for all items in this execution)
    const action = this.getNodeParameter("action", 0, "") as string;
    const paramsRaw = this.getNodeParameter("params", 0, "{}") as string;
    const policy = this.getNodeParameter("policy", 0, "") as string;
    const agentId = this.getNodeParameter("agentId", 0, "n8n-workflow") as string;
    const failClosed = this.getNodeParameter("failClosed", 0, true) as boolean;

    if (!action) {
      throw new NodeOperationError(
        this.getNode(),
        'The "Action" field is required. Specify the action to verify (e.g. payment.create).',
      );
    }

    // Parse parameters JSON
    let params: Record<string, unknown>;
    try {
      params = JSON.parse(paramsRaw);
    } catch {
      throw new NodeOperationError(
        this.getNode(),
        `Invalid JSON in Parameters field: ${paramsRaw}`,
      );
    }

    // Initialize EYDII client
    const eydii = new EydiiVerify({
      apiKey,
      baseUrl,
      failClosed,
    });

    // Process each input item
    for (let i = 0; i < items.length; i++) {
      try {
        // Allow per-item expression overrides for action and params
        const itemAction = this.getNodeParameter("action", i, action) as string;
        const itemParamsRaw = this.getNodeParameter("params", i, paramsRaw) as string;
        const itemPolicy = this.getNodeParameter("policy", i, policy) as string;
        const itemAgentId = this.getNodeParameter("agentId", i, agentId) as string;

        let itemParams: Record<string, unknown>;
        try {
          itemParams = JSON.parse(itemParamsRaw);
        } catch {
          itemParams = params;
        }

        const result: VerifyResponse = await eydii.verifyDecision({
          agentId: itemAgentId,
          action: itemAction,
          params: itemParams,
          policy: itemPolicy || undefined,
        });

        // Build output item with verification metadata
        const outputItem: INodeExecutionData = {
          json: {
            ...items[i].json,
            eydii: {
              proof_id: result.proofId,
              verification_id: result.verificationId,
              verdict: result.verdict,
              verified: result.verified,
              action: result.action,
              agent_id: result.agentId,
              policy: result.policy,
              reason: result.reason,
              latency_ms: result.latencyMs,
              mode: result.mode,
              audit_id: result.auditId,
              timestamp: result.timestamp,
              evaluated_constraints: result.evaluatedConstraints,
            },
          },
          pairedItem: { item: i },
        };

        if (result.verified) {
          allowed.push(outputItem);
        } else {
          denied.push(outputItem);
        }
      } catch (err) {
        if (failClosed) {
          // Fail-closed: route to denied output with error context
          denied.push({
            json: {
              ...items[i].json,
              eydii: {
                proof_id: "",
                verification_id: "",
                verdict: "denied",
                verified: false,
                action,
                agent_id: agentId,
                policy: policy || null,
                reason: `EYDII verification error (fail-closed): ${err instanceof Error ? err.message : String(err)}`,
                latency_ms: 0,
                mode: "dpe",
                audit_id: "",
                timestamp: new Date().toISOString(),
                evaluated_constraints: [],
              },
            },
            pairedItem: { item: i },
          });
        } else {
          throw new NodeOperationError(
            this.getNode(),
            `EYDII verification failed for item ${i}: ${err instanceof Error ? err.message : String(err)}`,
            { itemIndex: i },
          );
        }
      }
    }

    return [allowed, denied];
  }
}
