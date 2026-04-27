<h1 align="center">EYDII</h1>

<p align="center">
  <strong>The trust layer for autonomous systems.</strong>
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
  Content-blind, mathematical behavioral intelligence — from AI agents to robots to power plants.
</p>

---

## The Problem

Autonomous systems are not software. They are neural, adaptive, and unpredictable. An AI agent writing code, a robot picking orders in a warehouse, a controller managing coolant flow in a nuclear facility — they all share the same failure mode: **silent drift**. They don't crash. They don't throw errors. They gradually deviate from what they were supposed to do, and nobody sees it until something breaks.

Traditional security answers one question: **"Who has access?"** It checks credentials, rotates keys, scans payloads. It was built for deterministic software — programs that execute the same instruction the same way every time.

Autonomous systems don't work that way. An AI agent silently expands its scope. A warehouse robot subtly changes its path optimization. An industrial controller drifts its operating parameters by fractions of a degree per hour. No credentials were stolen. No vulnerability was exploited. The system simply **drifted**.

You will not see it in your access controls. You will not see it in your firewall logs. In healthcare, defense, pharmaceuticals, and industrial infrastructure — the environments where autonomous systems carry the highest stakes — you cannot even inspect the content to look for problems. Privacy law, classification, and regulatory compliance make content inspection illegal.

**EYDII is the trust layer built for exactly this.**

It monitors what autonomous systems **do** — action types, timing, frequency, behavioral patterns — without ever seeing what they say, produce, or access. Content-blind by architecture, not by configuration. Trustless by design, not by promise. Mathematical proof that behavior matches intent, or proof that it doesn't.

## Where It Matters

- **AI Agents** — Coding agents, research agents, multi-agent organizations across 30+ frameworks
- **Physical AI / Robotics** — Warehouse robots, surgical systems, autonomous vehicles, manufacturing floors
- **Industrial Autonomous Systems** — Power plants, railway control, water treatment, pharmaceutical manufacturing
- **Regulated Environments** — HIPAA, ITAR, defense, financial services — where content inspection is forbidden by law

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

EYDII was built for environments where content inspection is **forbidden** — healthcare, defense, pharmaceuticals, industrial control, multi-tenant SaaS, financial services. Where HIPAA, ITAR, classification rules, or regulatory compliance makes reading system outputs a legal violation, EYDII operates without compromise because there is nothing to compromise. The same architecture that monitors an AI agent writing code monitors a robot picking orders in a warehouse and a controller managing coolant in a power plant. Only the sidecar connector changes.

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
