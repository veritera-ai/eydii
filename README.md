<h1 align="center">EYDII</h1>

<p align="center">
  <strong>Your AI agents are drifting right now. You just can't see it.</strong>
</p>

<p align="center">
  <a href="https://github.com/veritera-ai/eydii/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" /></a>
  <a href="https://www.npmjs.com/package/@veritera.ai/eydii"><img src="https://img.shields.io/npm/v/@veritera.ai/eydii.svg" alt="npm" /></a>
  <a href="https://pypi.org/project/veritera/"><img src="https://img.shields.io/pypi/v/veritera.svg" alt="PyPI" /></a>
  <a href="#framework-adapters"><img src="https://img.shields.io/badge/adapters-10%20frameworks-brightgreen.svg" alt="Adapters" /></a>
  <a href="https://id.veritera.ai"><img src="https://img.shields.io/badge/platform-id.veritera.ai-black.svg" alt="Platform" /></a>
</p>

<p align="center">
  Trustless infrastructure for autonomous systems.<br />
  Content-blind, mathematical behavioral intelligence for AI agents.
</p>

---

## The Problem

AI agents are not software. They are neural systems. They interpret, improvise, and drift.

Traditional security answers one question: **"Who has access?"** It checks credentials, rotates keys, scans payloads. It was built for software that executes the same instruction the same way every time.

Agents don't work that way. An agent that passed every test yesterday can silently expand its own scope today -- reading files it was never meant to touch, calling tools in sequences no one anticipated, escalating its own authority one action at a time. No credentials were stolen. No vulnerability was exploited. The agent simply **drifted**.

You will not see it in your logs. You will not see it in your access controls. You will see it when something breaks.

**EYDII is the trust layer that sees it.**

It monitors what agents **do** -- action types, timing, frequency, behavioral patterns -- without ever seeing what they say, produce, or read. Content-blind by architecture, not by policy. Trustless by design, not by promise. Mathematical proof that behavior matches intent, or proof that it doesn't.

## How It Works

EYDII operates as three independent layers. Compromising one cannot compromise another.

```
                         YOUR APPLICATION
                               |
              +----------------+----------------+
              |                                 |
         [ SIDECAR ]                     [ SIDECAR ]
         Runtime interception            Runtime interception
         Action classification           Action classification
         Content never leaves            Content never leaves
              |                                 |
              +----------------+----------------+
                               |
                          [ ENGINE ]
                          Behavioral analysis
                          Drift detection
                          Trust Score computation
                          Pattern recognition
                               |
                          [ PROOF ]
                          Mathematical attestation
                          Denial proofs
                          Immutable audit chain
                          Third-party verifiable
```

| Layer | What it does | What it never sees |
|-------|-------------|-------------------|
| **Sidecar** | Intercepts actions at runtime, classifies action type and metadata | Message content, tool outputs, model responses |
| **Engine** | Analyzes behavioral patterns, detects drift, computes Trust Score | Raw data, payloads, user inputs, generated content |
| **Proof** | Generates mathematical attestations and denial proofs | Anything about the content -- proofs are over behavior, not data |

## Content-Blind by Architecture

This is not a filter. EYDII never receives, processes, stores, or transmits the content of agent actions. The architecture makes inspection **impossible**, not just disabled.

**What EYDII sees:**
- Action type (`file_write`, `api_call`, `tool_use`)
- Timestamp and sequence
- Agent identity
- Action frequency and patterns
- Behavioral deviation from established baselines

**What EYDII never sees:**
- What the agent wrote to the file
- What the API returned
- What the user said
- What the model generated
- What the tool produced

This is the difference between a security camera that watches where people walk and one that reads their mail. EYDII is the former. By construction, not configuration.

## Quick Start

### JavaScript

```bash
npm install @veritera.ai/eydii
```

```typescript
import { EydiiClient } from "@veritera.ai/eydii";

const client = new EydiiClient({
  apiKey: process.env.EYDII_API_KEY,
});

const result = await client.verify({
  action: "file_write",
  agentId: "researcher-01",
  metadata: { target: "/reports/q2.pdf" },
});

if (!result.verified) {
  // Action violates established behavioral rules
  console.error(`Blocked: ${result.reason}`);
}
```

### Python

```bash
pip install veritera
```

```python
import os
from veritera import EydiiClient

client = EydiiClient(api_key=os.environ["EYDII_API_KEY"])

result = client.verify(
    action="file_write",
    agent_id="researcher-01",
    metadata={"target": "/reports/q2.pdf"},
)

if not result.verified:
    # Action violates established behavioral rules
    print(f"Blocked: {result.reason}")
```

Get your API key at **[id.veritera.ai](https://id.veritera.ai)**.

## Framework Adapters

Drop EYDII into any major agent framework with a single install.

| Framework | Install | Language |
|-----------|---------|----------|
| **LangChain / LangGraph** | `pip install langchain-eydii` | Python |
| **CrewAI** | `pip install crewai-eydii` | Python |
| **OpenAI Agents SDK** | `pip install eydii-openai` | Python |
| **LlamaIndex** | `pip install llama-index-tools-eydii` | Python |
| **Pydantic AI** | `pip install pydantic-ai-eydii` | Python |
| **Agno** | `pip install agno-eydii` | Python |
| **Google ADK** | `pip install google-adk-eydii` | Python |
| **Mastra** | `npm install @veritera.ai/eydii-mastra` | TypeScript |
| **n8n** | Community node | n8n |
| **OpenClaw** | `npm install @veritera.ai/eydii-openclaw` | TypeScript |

Each adapter wraps the native framework's tool/callback interface so EYDII operates transparently. No changes to your agent logic.

## MCP Support

EYDII ships as a Model Context Protocol (MCP) server for local development tools:

- **Claude Code** -- Verify actions from Claude's CLI agent
- **Claude Cowork** -- Verify actions across collaborative Claude sessions
- **Cursor** -- Verify actions from Cursor's AI assistant

See [`docs/mcp-setup.md`](docs/mcp-setup.md) for configuration.

## Repository Structure

```
eydii/
  sdks/
    javascript/          # @veritera.ai/eydii (npm)
    python/              # veritera (PyPI)
  adapters/
    langchain/           # LangChain + LangGraph
    crewai/              # CrewAI
    openai/              # OpenAI Agents SDK
    llamaindex/          # LlamaIndex
    pydantic-ai/         # Pydantic AI
    agno/                # Agno
    google-adk/          # Google ADK
    mastra/              # Mastra
    n8n/                 # n8n
    openclaw/            # OpenClaw
  docs/                  # Guides and API reference
  examples/              # Integration examples
```

## Architecture

EYDII is designed for environments where content inspection is **forbidden** -- healthcare, defense, multi-tenant SaaS, financial services, industrial systems. Where HIPAA, ITAR, or organizational policy makes reading agent outputs a compliance violation, EYDII operates without compromise because there is nothing to compromise. The architecture eliminates the attack surface that content-aware systems create.

Seven patent applications cover the trust layer architecture, behavioral drift detection, mathematical attestation, and content-blind trust methods.

## Links

| | |
|---|---|
| **EYDII Platform** | [id.veritera.ai](https://id.veritera.ai) |
| **ROAM** (Agent orchestration) | [github.com/veritera-ai/roam](https://github.com/veritera-ai/roam) |
| **Veritera Corporation** | [veritera.ai](https://veritera.ai) |
| **Documentation** | [docs/](docs/) |

## License

SDKs and framework adapters are released under the [MIT License](LICENSE).

The EYDII engine is proprietary software of Veritera Corporation.

---

<p align="center">
  <sub>Built by Veritera Engineering</sub>
</p>
