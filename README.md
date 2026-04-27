# EYDII — The Trust Layer for Autonomous Systems

**Content-blind. Trustless. Mathematical.**

EYDII is behavioral intelligence infrastructure for AI agents. It monitors what agents *do* — not what they say, produce, or see — and mathematically verifies that their behavior matches their assigned role.

See EYDII in action: **[ROAM — Republic of Autonomous Machines](https://github.com/veritera-ai/roam)**

---

## The Problem

AI agents are neural systems, not software. They don't fail like software fails. They drift — slowly, silently, cumulatively. An agent that was reliable yesterday may behave differently today. Traditional security tools (firewalls, access control, permission gating) were built for software. They verify access. They cannot verify behavior.

**EYDII verifies behavior.**

## How It Works

EYDII operates in three layers:

```
┌─────────────────────────────────────┐
│  Layer 3: Mathematical Proof        │  ← Attestation, denial proofs, audit chain
├─────────────────────────────────────┤
│  Layer 2: Behavioral Engine         │  ← Drift detection, pattern analysis, health scoring
├─────────────────────────────────────┤
│  Layer 1: Runtime Interception      │  ← Sidecar captures action metadata (never content)
└─────────────────────────────────────┘
```

1. **Sidecar** — Sits alongside the agent runtime. Captures action metadata — *what type of action*, *when*, *how often*. Never inspects the content of inputs, outputs, or instructions.

2. **Behavioral Engine** — Baselines each agent from its job description. Monitors behavioral patterns over time. Detects drift — the gap between what an agent is supposed to do and what it is actually doing.

3. **Mathematical Proof** — Every action is mathematically signed. Every denial is recorded with a proof. The audit chain is tamper-evident and complete.

## Content-Blind by Architecture

EYDII never sees:
- What the agent was asked to do
- What the agent produced
- What data the agent accessed
- What the agent said to the user

EYDII only sees:
- The *type* of action (web search, file write, API call)
- The *timing* and *frequency* of actions
- The *pattern* relative to the baseline

This is not a policy choice — it's an architectural constraint. The engine is structurally incapable of content inspection. This makes EYDII the only trust layer that works in environments where content inspection is forbidden: HIPAA, defense, multi-tenant SaaS, industrial autonomous systems.

## Where EYDII Runs

- **Embedded in [ROAM](https://github.com/veritera-ai/roam)** — Agent orchestration OS with EYDII built in
- **Standalone via SDK** — Add EYDII to any agent in 3 lines of code
- **Enterprise** — Self-hosted, dedicated infrastructure

## SDKs

### JavaScript / TypeScript

```bash
npm install @veritera.ai/eydii
```

```typescript
import { EydiiClient } from "@veritera.ai/eydii";

const client = new EydiiClient({ apiKey: process.env.EYDII_API_KEY });

// Verify an action before execution
const result = await client.verify({
  action: "file_write",
  agentId: "researcher-01",
  metadata: { target: "/reports/q2.pdf" },
});

if (result.verified) {
  // Action is consistent with behavioral baseline
  // result.receipt contains the mathematical proof
}
```

### Python

```bash
pip install veritera
```

```python
from veritera import EydiiClient

client = EydiiClient(api_key=os.environ["EYDII_API_KEY"])

# Verify an action before execution
result = client.verify(
    action="file_write",
    agent_id="researcher-01",
    metadata={"target": "/reports/q2.pdf"},
)

if result.verified:
    # Action is consistent with behavioral baseline
    # result.receipt contains the mathematical proof
    pass
```

## Framework Adapters

EYDII integrates with every major agent framework:

| Framework | Language | Install |
|-----------|----------|---------|
| [LangChain / LangGraph](./adapters/langchain) | Python | `pip install langchain-eydii` |
| [CrewAI](./adapters/crewai) | Python | `pip install crewai-eydii` |
| [OpenAI Agents SDK](./adapters/openai) | Python | `pip install eydii-openai` |
| [LlamaIndex](./adapters/llamaindex) | Python | `pip install llama-index-tools-eydii` |
| [Pydantic AI](./adapters/pydantic-ai) | Python | `pip install pydantic-ai-eydii` |
| [Agno](./adapters/agno) | Python | `pip install agno-eydii` |
| [Google ADK](./adapters/google-adk) | Python | `pip install google-adk-eydii` |
| [Mastra](./adapters/mastra) | TypeScript | `npm install @veritera.ai/eydii-mastra` |
| [n8n](./adapters/n8n) | TypeScript | Community node |
| [OpenClaw](./adapters/openclaw) | TypeScript | `npm install @veritera.ai/eydii-openclaw` |
| Claude Code | MCP | [Configuration guide](https://id.veritera.ai/mcp) |
| Claude Cowork | MCP | [Configuration guide](https://id.veritera.ai/mcp) |
| Cursor | MCP | [Configuration guide](https://id.veritera.ai/mcp) |

## Repository Structure

```
eydii/
├── sdks/
│   ├── javascript/     # @veritera.ai/eydii — TypeScript SDK
│   └── python/         # veritera — Python SDK
├── adapters/
│   ├── langchain/      # LangChain + LangGraph
│   ├── crewai/         # CrewAI
│   ├── openai/         # OpenAI Agents SDK
│   ├── llamaindex/     # LlamaIndex
│   ├── pydantic-ai/    # Pydantic AI
│   ├── agno/           # Agno
│   ├── google-adk/     # Google Agent Development Kit
│   ├── mastra/         # Mastra
│   ├── n8n/            # n8n community node
│   └── openclaw/       # OpenClaw
├── docs/               # Documentation
└── examples/           # Integration examples
```

## Links

- **[ROAM — Agent Operating System](https://github.com/veritera-ai/roam)** — See EYDII in action, embedded in a multi-agent orchestration system
- **[Veritera Corporation](https://veritera.ai)** — The company behind EYDII and ROAM
- **[id.veritera.ai](https://id.veritera.ai)** — EYDII platform

## Patents

EYDII's architecture is protected by 7 patent applications covering content-blind behavioral verification, trustless attestation, and the three-layer trust architecture for autonomous systems.

## License

Copyright 2026 Veritera Corporation. All rights reserved.

The SDKs and framework adapters in this repository are available under the [MIT License](./LICENSE). The EYDII behavioral engine, verification infrastructure, and mathematical proof system are proprietary.
