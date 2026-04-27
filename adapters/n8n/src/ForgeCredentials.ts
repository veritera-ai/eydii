/**
 * Forge API Credentials
 * =====================
 * n8n credential type for authenticating with the Forge Verify API.
 *
 * Users configure their API key and (optionally) a custom base URL
 * through the n8n credentials UI. These values are consumed by the
 * ForgeVerifyNode at execution time.
 */

import type { ICredentialType, INodeProperties } from "n8n-workflow";

export class ForgeCredentials implements ICredentialType {
  name = "forgeApi";
  displayName = "Forge API";
  documentationUrl = "https://docs.veritera.ai";

  properties: INodeProperties[] = [
    {
      displayName: "API Key",
      name: "apiKey",
      type: "string",
      typeOptions: { password: true },
      default: "",
      required: true,
      description: "Forge API key (starts with vt_live_ or vt_test_)",
    },
    {
      displayName: "Base URL",
      name: "baseUrl",
      type: "string",
      default: "https://forge.veritera.ai",
      description: "Forge Verify API base URL. Change only for self-hosted deployments.",
    },
  ];
}
