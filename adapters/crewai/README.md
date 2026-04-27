# crewai-eydii

[![PyPI version](https://img.shields.io/pypi/v/crewai-eydii.svg)](https://pypi.org/project/crewai-eydii/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/veritera-ai/eydii-crewai/actions/workflows/ci.yml/badge.svg)](https://github.com/veritera-ai/eydii-crewai/actions/workflows/ci.yml)

**EYDII tools and guardrails for CrewAI — verify every agent action before execution.**

---

## Why EYDII?

AI agents are taking real-world actions — sending emails, moving money, accessing databases, calling APIs. But there's no independent system verifying what they do.

The agent frameworks (LangChain, CrewAI, OpenAI Agents SDK) provide no enforcement beyond prompt engineering. When an agent goes rogue, you find out from your customers, not from your monitoring. This is like letting employees process transactions with no audit department, no compliance checks, no separation of duties.

EYDII is the independent verification layer for AI agents. It checks every action before execution (**Verify**) and tracks every execution with cryptographic receipts (**Execute**). One SDK. Sub-15ms latency. Works with every major agent framework.

## How EYDII Is Different

### Content-Blind

EYDII never sees your agent's instructions, prompts, code, data, or outputs. It verifies the action type and behavioral pattern only. Your intellectual property stays yours.

Every other tool in this space — Guardrails AI, NeMo Guardrails, LlamaGuard — requires reading your prompts and outputs to make decisions. EYDII doesn't. That's not a feature difference — it's a fundamentally different architecture.

### Trustless Verification

Ed25519 asymmetric cryptography. The agent signs receipts with a private key only it holds. Anyone with the public key can verify independently. You don't trust Veritera. You trust math. No shared secrets. No phone-home. The proof stands on its own.

### Independent Enforcement

Policies are enforced outside the agent. The agent cannot override, bypass, or modify its own guardrails. This is separation of duties — the same principle that prevents an accountant from approving their own expenses.

> EYDII works like a home security system. Your security company doesn't know what's inside your house. They don't inventory your jewelry or read your mail. They monitor doors opening, windows breaking, motion where there shouldn't be motion. They protect the pattern — not the contents. EYDII does the same for your AI agents.

Not just what we verify — but how we verify it. Patent pending.

## What EYDII Stops

These aren't hypothetical. Each is a documented attack pattern against production AI agents.

| Threat | What Happens Without EYDII | How EYDII Stops It |
|--------|---------------------------|-------------------|
| **Prompt Injection** | Injected instructions cause agent to exfiltrate data | Action blocked pre-execution — the unauthorized API call never fires |
| **Agent Drift** | 5 benign steps cascade into a data breach | Cumulative risk scoring detects the escalation pattern |
| **Trust Poisoning** | Compromised agent poisons every agent that trusts it | Agent-to-agent attestation — no agent inherits trust without proof |
| **Tool Shadowing** | Shadow tool mimics your allowlist, steals credentials | Identity-based tool verification at the MCP layer |
| **Hallucinated Completion** | Agent claims it finished work it never started | Receipt chain is empty — no cryptographic proof, no credit |
| **Specification Drift** | Agent builds the wrong features convincingly | ZKP probes verify alignment to the actual specification |
| **Circular Execution** | Agent loops for hours, looks productive, accomplishes nothing | Execution graph analysis detects the cycle |
| **Behavioral Drift** | Agent quietly stops running tests over weeks | Cross-task behavioral baselines catch the regression |

> **[See the interactive demos](https://id.veritera.ai/demos)**

---

## Install

```bash
pip install crewai-eydii
```

This installs `eydii_crewai` and its dependencies (`veritera` SDK and `crewai`).

---

## Prerequisites: Create a Policy

Before using EYDII with CrewAI, create a policy that defines what your agents are allowed to do. You only need to do this once:

```python
from veritera import EydiiVerify

eydii = EydiiVerify(api_key="vt_live_...")  # Get your key at id.veritera.ai

# Create a policy from code
eydii.create_policy_sync(
    name="finance-controls",
    description="Controls for multi-agent financial operations",
    rules=[
        {"type": "action_whitelist", "params": {"allowed": ["trade.execute", "refund.process", "report.generate"]}},
        {"type": "amount_limit", "params": {"max": 10000, "currency": "USD"}},
    ],
)

# Or generate one from plain English
eydii.generate_policy_sync(
    "Allow trades under $10,000, refund processing, and report generation. Block all account deletions and unauthorized data exports.",
    save=True,
)
```

A `default` policy is created automatically when you sign up — it blocks dangerous actions like database drops and admin overrides. You can use it immediately with `policy="default"`.

> **Tip:** `pip install veritera` to get the policy management SDK. See the [full policy docs](https://github.com/veritera-ai/eydii-python#policies).

---

## Quick Start

```python
import os
from crewai import Agent, Task, Crew
from eydii_crewai import EydiiVerifyTool, eydii_task_guardrail

os.environ["VERITERA_API_KEY"] = "vt_live_..."

# 1. Create a EYDII verification tool
verify = EydiiVerifyTool(policy="finance-controls")  # create this policy first (see above) -- or use "default"

# 2. Give it to your agent
analyst = Agent(
    role="Financial Analyst",
    goal="Process financial transactions safely",
    tools=[verify],
)

# 3. Add a task guardrail for output validation
task = Task(
    description="Process the refund for order #12345",
    agent=analyst,
    guardrail=eydii_task_guardrail(policy="finance-controls"),
    guardrail_max_retries=3,
)

# 4. Run the crew — every action is verified, every output is validated
crew = Crew(agents=[analyst], tasks=[task])
result = crew.kickoff()
```

The agent calls `eydii_verify` before executing sensitive actions. If an action is denied, the agent receives a `DENIED` response and adjusts its plan. If the task output violates policy, CrewAI automatically retries the task up to `guardrail_max_retries` times.

---

## Tutorial: Building a Verified Multi-Agent Research Crew

This walkthrough builds a three-agent crew where one agent gathers data, another analyzes it, and a third takes action — with EYDII protecting the entire pipeline.

### The Problem with Multi-Agent Delegation

CrewAI's power is multi-agent collaboration. Agent A delegates to Agent B, which calls Agent C. But this is exactly where policies break down:

- **System prompts drift** — when Agent B receives a delegated task, the original guardrails from Agent A's system prompt no longer apply.
- **Inline rules are invisible** — Agent C has no idea what rules Agent A was supposed to follow.
- **Chained actions compound risk** — a data lookup (harmless) feeds an analysis (maybe harmless) that triggers a payment (definitely not harmless).

EYDII solves this by moving verification **outside** the agents. Every action, from every agent, hits the same external policy engine. No matter how deep the delegation chain goes, EYDII catches violations.

### Step 1 — Set Up Your Environment

```python
import os
from crewai import Agent, Task, Crew, Process
from eydii_crewai import (
    EydiiVerifyTool,
    eydii_task_guardrail,
    eydii_before_llm,
    eydii_after_llm,
)

os.environ["VERITERA_API_KEY"] = "vt_live_..."
os.environ["OPENAI_API_KEY"] = "sk-..."
```

### Step 2 — Create the EYDII Verification Tool

Create a single verification tool that all agents will share. Every call goes through the same policy engine with the same rules.

```python
verify = EydiiVerifyTool(
    policy="research-ops",    # your policy set in EYDII
    agent_id="research-crew", # appears in your EYDII audit log
    fail_closed=True,         # deny if EYDII is unreachable
)
```

### Step 3 — Define Three Agents

```python
researcher = Agent(
    role="Research Analyst",
    goal="Gather comprehensive data on the target company",
    backstory=(
        "You are a senior research analyst. You search public sources, "
        "financial databases, and news feeds to compile company profiles."
    ),
    tools=[verify],
    verbose=True,
)

strategist = Agent(
    role="Strategy Analyst",
    goal="Analyze research data and produce an investment recommendation",
    backstory=(
        "You are a strategy analyst who evaluates company data, identifies "
        "risks, and produces clear buy/hold/sell recommendations with reasoning."
    ),
    tools=[verify],
    verbose=True,
)

executor = Agent(
    role="Trade Executor",
    goal="Execute approved trades within risk limits",
    backstory=(
        "You execute trades based on analyst recommendations. You MUST verify "
        "every trade through EYDII before execution. No exceptions."
    ),
    tools=[verify],
    verbose=True,
)
```

All three agents receive the same `EydiiVerifyTool`. When the executor tries to place a trade, it calls `eydii_verify(action="trade.execute", params='{"ticker": "AAPL", "amount": 50000}')` — EYDII checks this against your `research-ops` policy and returns `APPROVED` or `DENIED`.

### Step 4 — Define Tasks with Guardrails

```python
research_task = Task(
    description=(
        "Research the company 'Acme Corp'. Gather recent financials, "
        "news sentiment, and competitive positioning. Verify your data "
        "sources through EYDII before including them."
    ),
    expected_output="A structured company profile with verified data sources.",
    agent=researcher,
    guardrail=eydii_task_guardrail(policy="research-ops"),
    guardrail_max_retries=2,
)

analysis_task = Task(
    description=(
        "Analyze the research profile and produce a recommendation. "
        "Include risk assessment. Verify your recommendation parameters "
        "through EYDII before finalizing."
    ),
    expected_output="An investment recommendation with risk score and reasoning.",
    agent=strategist,
    guardrail=eydii_task_guardrail(policy="research-ops"),
    guardrail_max_retries=2,
)

execution_task = Task(
    description=(
        "Based on the strategy recommendation, prepare and verify a trade. "
        "You MUST call eydii_verify with action='trade.execute' before "
        "executing any trade. Include ticker, amount, and direction."
    ),
    expected_output="Trade execution confirmation with EYDII proof_id.",
    agent=executor,
    guardrail=eydii_task_guardrail(policy="research-ops"),
    guardrail_max_retries=3,
)
```

Each task has its own guardrail. Even if an agent produces output that *looks* correct, EYDII validates the content against your policies. If the strategist recommends a position that exceeds your risk limits, the guardrail rejects the output and CrewAI retries the task.

### Step 5 — Register LLM Hooks (Optional)

For maximum coverage, add LLM-level hooks. These intercept every model call across all agents — before the model runs and after it responds.

```python
# Block any LLM call that violates policy (e.g., iteration limits, forbidden topics)
eydii_before_llm(policy="safety-controls", max_iterations=15)

# Audit every LLM response to the EYDII trail
eydii_after_llm(policy="audit-trail")
```

### Step 6 — Assemble and Run the Crew

```python
crew = Crew(
    agents=[researcher, strategist, executor],
    tasks=[research_task, analysis_task, execution_task],
    process=Process.sequential,
    verbose=True,
)

result = crew.kickoff()
print(result)
```

### What Happens at Runtime

Here is the verification flow for this crew:

1. **Researcher** gathers data. Each data source is verified through `EydiiVerifyTool` before inclusion. The task guardrail validates the final profile output.
2. **Strategist** receives the research profile. Its recommendation is checked — if the position exceeds risk limits, the guardrail rejects the output and CrewAI retries.
3. **Executor** receives the approved recommendation. It calls `eydii_verify(action="trade.execute", ...)` before executing. EYDII checks amount limits, allowed tickers, and trading hours. If denied, the agent does not proceed.
4. **LLM hooks** run on every model call across all three agents — catching runaway iteration loops and logging every response to the audit trail.

Every verification produces a `proof_id` that links to a tamper-proof audit record in your EYDII dashboard.

---

## Three Integration Points

### 1. EydiiVerifyTool — Agent Tool for Explicit Verification

The most direct integration. Give agents a tool they can call to check whether an action is allowed.

```python
from eydii_crewai import EydiiVerifyTool

tool = EydiiVerifyTool(
    policy="finance-controls",
    agent_id="analyst-bot",
    fail_closed=True,
)

agent = Agent(
    role="Financial Analyst",
    goal="Process transactions within policy limits",
    tools=[tool],
)
```

**How the agent uses it:**

The agent calls `eydii_verify(action="payment.create", params='{"amount": 500, "currency": "USD"}')` and receives:

- `APPROVED: Allowed | proof_id: fp_abc123 | latency: 42ms` — proceed with the action.
- `DENIED: Amount exceeds $200 limit | proof_id: fp_def456 | Do NOT proceed with this action.` — the agent adjusts its plan.

**Constructor parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `VERITERA_API_KEY` env var | Your EYDII API key |
| `base_url` | `str` | `https://id.veritera.ai` | EYDII API endpoint |
| `agent_id` | `str` | `"crewai-agent"` | Identifier in audit logs |
| `policy` | `str` | `None` | Policy set to evaluate against |
| `fail_closed` | `bool` | `True` | Deny when API is unreachable |
| `timeout` | `float` | `10.0` | Request timeout in seconds |

### 2. eydii_task_guardrail() — Task Output Validation

Wraps CrewAI's native guardrail system. After a task completes, EYDII validates the output. If the output violates policy, CrewAI automatically retries the task.

```python
from eydii_crewai import eydii_task_guardrail

task = Task(
    description="Draft a customer response about their refund request",
    agent=support_agent,
    guardrail=eydii_task_guardrail(
        policy="communication-policy",
        agent_id="support-bot",
    ),
    guardrail_max_retries=3,
)
```

**How it works:**

1. The agent completes the task and produces output.
2. The guardrail sends the output (first 3,000 characters) and task description (first 500 characters) to EYDII.
3. EYDII evaluates the content against your policy.
4. If approved, the output passes through unchanged.
5. If denied, CrewAI receives feedback (e.g., "EYDII policy violation: Response contains unauthorized discount offer. Please revise your output to comply with the policy.") and retries the task.

**Factory parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `VERITERA_API_KEY` env var | Your EYDII API key |
| `base_url` | `str` | `https://id.veritera.ai` | EYDII API endpoint |
| `agent_id` | `str` | `"crewai-agent"` | Identifier in audit logs |
| `policy` | `str` | `None` | Policy set to evaluate against |
| `fail_closed` | `bool` | `True` | Reject output when API is unreachable |

### 3. eydii_before_llm() / eydii_after_llm() — LLM Call Hooks

Intercept at the lowest level. These hooks run on every LLM call across all agents in the crew.

```python
from eydii_crewai import eydii_before_llm, eydii_after_llm

# Pre-call: block LLM calls that violate policy or exceed iteration limits
eydii_before_llm(
    policy="safety-controls",
    max_iterations=10,        # hard stop after 10 iterations per task
    agent_id="crew-monitor",
)

# Post-call: audit every LLM response (non-blocking)
eydii_after_llm(
    policy="audit-trail",
    agent_id="crew-monitor",
)
```

**eydii_before_llm** can block execution by returning `False`. Use it for:
- Iteration limits (stop runaway agent loops)
- Pre-call policy checks (block certain agents from certain tasks)
- Budget controls (stop after N calls)

**eydii_after_llm** is non-blocking. Use it for:
- Audit logging (every response hits the EYDII trail)
- Post-response policy evaluation
- Compliance recording

**Parameters (both functions):**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `VERITERA_API_KEY` env var | Your EYDII API key |
| `base_url` | `str` | `https://id.veritera.ai` | EYDII API endpoint |
| `agent_id` | `str` | `"crewai-agent"` | Identifier in audit logs |
| `policy` | `str` | `None` | Policy set to evaluate against |
| `fail_closed` | `bool` | `True` | Block when API is unreachable (before_llm only) |
| `max_iterations` | `int` | `None` | Hard iteration limit (before_llm only) |

> **Note:** LLM hooks require `crewai>=0.80`. On older versions, a warning is logged and the hooks are skipped.

---

## Configuration Reference

| Config | Source | Required | Example |
|--------|--------|----------|---------|
| API key | `VERITERA_API_KEY` env var or `api_key=` parameter | Yes | `vt_live_abc123` |
| Base URL | `base_url=` parameter | No | `https://id.veritera.ai` |
| Policy | `policy=` parameter | No (but recommended) | `"finance-controls"` |
| Agent ID | `agent_id=` parameter | No | `"my-crewai-agent"` |
| Fail closed | `fail_closed=` parameter | No (default: `True`) | `True` or `False` |
| Timeout | `timeout=` parameter (EydiiVerifyTool only) | No (default: `10.0`) | `30.0` |

---

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    Your CrewAI Crew                      │
│                                                         │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐        │
│  │ Agent A   │──▶│ Agent B   │──▶│ Agent C   │        │
│  │ Research  │   │ Analysis  │   │ Execution │        │
│  └─────┬─────┘   └─────┬─────┘   └─────┬─────┘        │
│        │               │               │               │
│   ┌────▼────┐     ┌────▼────┐     ┌────▼────┐         │
│   │  Tool   │     │Guardrail│     │  Tool   │         │
│   │  Call   │     │  Check  │     │  Call   │         │
│   └────┬────┘     └────┬────┘     └────┬────┘         │
│        │               │               │               │
└────────┼───────────────┼───────────────┼───────────────┘
         │               │               │
         ▼               ▼               ▼
    ┌─────────────────────────────────────────┐
    │            EYDII Verify API             │
    │                                         │
    │  Policy Engine  │  Audit Trail  │ Proof │
    └─────────────────────────────────────────┘
```

1. **Agent calls tool** — `EydiiVerifyTool.run(action, params)` sends a verification request to the EYDII API.
2. **EYDII evaluates** — The policy engine checks the action and parameters against your defined policies.
3. **Result returned** — `APPROVED` (with proof ID) or `DENIED` (with reason and proof ID).
4. **Agent decides** — On approval, the agent proceeds. On denial, the agent adjusts its plan.
5. **Guardrail validates** — After the task completes, `eydii_task_guardrail` checks the output. If denied, CrewAI retries.
6. **LLM hooks monitor** — Every model call is optionally checked (before) and logged (after).
7. **Audit trail recorded** — Every verification produces a `proof_id` linking to a permanent, tamper-proof record.

---

## Multi-Agent Security

Single-agent guardrails are straightforward — one agent, one set of rules. Multi-agent crews break this model:

**The Delegation Problem**

```
Agent A (has policy: "no trades over $10k")
  └──▶ delegates to Agent B (has policy: ???)
         └──▶ delegates to Agent C (has policy: ???)
                └──▶ executes trade for $50k  ← policy lost
```

When Agent A delegates to Agent B, the system prompt that contained Agent A's policy does not transfer. Agent B operates under its own system prompt. By the time Agent C executes, the original constraints are gone.

**EYDII Fixes This**

```
Agent A ──▶ eydii_verify("research.query")     ✓ APPROVED
Agent B ──▶ eydii_verify("analysis.recommend")  ✓ APPROVED
Agent C ──▶ eydii_verify("trade.execute", $50k) ✗ DENIED — exceeds $10k limit
```

EYDII policies are external to all agents. The same rules apply whether the action is initiated by the first agent or the fifth in a delegation chain. The policy lives in EYDII, not in any agent's system prompt.

**Why This Matters for CrewAI Specifically**

CrewAI supports `Process.hierarchical` where a manager agent delegates freely to workers. It supports `allow_delegation=True` where any agent can hand off to any other. These are powerful features — but they multiply the surface area for policy violations. EYDII gives you a single control plane across all of them.

---

## Error Handling

The package handles three failure modes:

### 1. EYDII API Unreachable

Controlled by `fail_closed`:

```python
# fail_closed=True (default) — deny when EYDII is down
tool = EydiiVerifyTool(policy="controls", fail_closed=True)
# Agent receives: "ERROR: Verification unavailable — ConnectionError(...)"

# fail_closed=False — allow when EYDII is down (use for non-critical paths)
tool = EydiiVerifyTool(policy="controls", fail_closed=False)
```

### 2. Invalid Parameters

If the agent passes malformed JSON as `params`, the tool wraps it safely:

```python
# Agent calls: eydii_verify(action="test", params="not valid json")
# Tool parses it as: {"raw": "not valid json"} and proceeds with verification
```

### 3. Task Guardrail Failures

When the guardrail denies output, CrewAI receives structured feedback:

```python
# Guardrail returns:
# (False, "EYDII policy violation: Response contains PII. Please revise your output to comply with the policy.")
# CrewAI retries the task with this feedback appended to the prompt
```

All errors are logged via Python's `logging` module under the `eydii_crewai` logger:

```python
import logging
logging.getLogger("eydii_crewai").setLevel(logging.DEBUG)
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VERITERA_API_KEY` | Yes (unless passed via `api_key=`) | Your EYDII API key. Get one at [veritera.ai/dashboard](https://id.veritera.ai/dashboard). |
| `OPENAI_API_KEY` | Yes (for CrewAI's default LLM) | Your OpenAI key for the underlying language model. |

You can also pass the API key directly to avoid environment variables:

```python
tool = EydiiVerifyTool(api_key="vt_live_...", policy="my-policy")
```

---

## V2: EYDII Execute -- Cryptographic Execution Receipts

While V1 (Verify) checks individual actions before they happen, V2 (Execute) monitors entire task executions and provides cryptographic proof that the work was done correctly -- without ever seeing the actual code or output.

Execute works by generating signed receipts at each step of an agent's task. These receipts form a tamper-proof audit trail that proves *what* happened and *in what order*, using mathematical proof. The receipts are submitted to EYDII Execute, which verifies the behavioral pattern matches expectations -- without needing access to the actual instructions, code, or data.

### How Receipts Work

Each tool call triggers a signed receipt containing the action type, timestamp, and a unique nonce — signed with your agent's Ed25519 private key. The receipt proves what action happened and in what order — without containing any code, data, or output. The server verifies the behavioral pattern, not the content. The receipt is submitted to EYDII Execute, which verifies the signature and adds it to the task's receipt chain.

### What Happens on Failure

Receipt emission is non-blocking. If EYDII Execute is unreachable, the error is logged and your agent continues working. A receipt failure should never stop your agent. This is by design — Verify is fail-closed (blocks on error), Execute is fire-and-forget (logs on error).

### Independent Verification

Anyone with your agent's public key can verify the receipt chain independently — no need to contact Veritera, no API call required. The Ed25519 signatures are self-contained mathematical proofs.

### Quick Start -- Task Wrapper

The simplest way to add Execute to a CrewAI task. A receipt is emitted when the task completes:

```python
import os
from crewai import Agent, Task, Crew
from eydii_crewai import eydii_execute_task_wrapper

os.environ["VERITERA_API_KEY"] = "vt_live_..."

analyst = Agent(
    role="Financial Analyst",
    goal="Process monthly reconciliation",
)

task = Task(
    description="Run the monthly reconciliation for Q1 accounts",
    agent=analyst,
    guardrail=eydii_execute_task_wrapper(
        task_id="task_monthly_recon",
        agent_id="finance-analyst",
    ),
)

crew = Crew(agents=[analyst], tasks=[task])
result = crew.kickoff()
```

When the task completes, a signed `task.complete` receipt is emitted and submitted to EYDII Execute.

### Fine-Grained Receipts with EydiiExecuteHook

For tracking individual tool invocations within a task, use the lower-level hook:

```python
from eydii_crewai import EydiiExecuteHook

hook = EydiiExecuteHook(
    task_id="task_data_pipeline",
    agent_id="etl-agent",
)

# Emit receipts at each step of a multi-step process
hook.on_tool_use("data_extraction")    # {"receipt_id": "...", "chain_index": 0}
hook.on_tool_use("data_transform")     # {"receipt_id": "...", "chain_index": 1}
hook.on_tool_use("data_load")          # {"receipt_id": "...", "chain_index": 2}
```

Each receipt is signed and chained. EYDII Execute verifies the sequence matches the expected behavioral pattern for this task type.

### Using V1 + V2 Together

V1 (Verify) and V2 (Execute) are complementary. V1 checks *permission* before each action. V2 tracks *execution* across the entire task. Use both for complete coverage:

```python
from eydii_crewai import EydiiVerifyTool, eydii_task_guardrail, eydii_execute_task_wrapper

# V1: Verification tool for real-time policy checks
verify = EydiiVerifyTool(policy="finance-controls")

analyst = Agent(
    role="Financial Analyst",
    goal="Process transactions within policy limits",
    tools=[verify],  # V1: agent checks actions before executing
)

# V2: Execute receipt on task completion
task = Task(
    description="Process the quarterly close",
    agent=analyst,
    guardrail=eydii_execute_task_wrapper(
        task_id="task_quarterly_close",
        agent_id="finance-analyst",
    ),
)
```

### EydiiExecuteHook Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `task_id` | `str` | Required | Identifier for the task being executed. Links all receipts in the chain. |
| `agent_id` | `str` | Required | Identifier for the agent performing the task. |
| `api_key` | `str` | `VERITERA_API_KEY` env var | Your EYDII API key. |
| `signing_key` | `str` | Same as `api_key` | Key used to sign receipts. Defaults to the API key. |
| `base_url` | `str` | `"https://id.veritera.ai"` | EYDII API endpoint. |

**Methods:**

| Method | Description |
|--------|-------------|
| `on_tool_use(action_type)` | Emit a signed receipt for a tool invocation. Returns `{"receipt_id": ..., "chain_index": ...}`. |

### eydii_execute_task_wrapper Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `task_id` | `str` | Required | Identifier for the task being executed. |
| `agent_id` | `str` | Required | Identifier for the agent performing the task. |
| `api_key` | `str` | `VERITERA_API_KEY` env var | Your EYDII API key. |
| `signing_key` | `str` | Same as `api_key` | Key used to sign receipts. |
| `base_url` | `str` | `"https://id.veritera.ai"` | EYDII API endpoint. |

Returns a function compatible with CrewAI's `Task(guardrail=...)` parameter. Emits a `task.complete` receipt when the task finishes.

---

## EYDII Ecosystem

| Package | Framework | What It Does | Install |
|---------|-----------|-------------|---------|
| [veritera](https://github.com/veritera-ai/eydii-python) | Any Python | Core SDK. Verify actions, manage policies, sign and submit receipts. | `pip install veritera` |
| [eydii-openai](https://github.com/veritera-ai/eydii-openai) | OpenAI Agents SDK | `eydii_protect()` wrapper + `EydiiExecuteGuardrail`. Drop-in verification for OpenAI agents. | `pip install eydii-openai` |
| [langchain-eydii](https://github.com/veritera-ai/eydii-langchain) | LangChain / LangGraph | `EydiiVerifyMiddleware` + `EydiiExecuteMiddleware`. Wraps LangGraph tool nodes. | `pip install langchain-eydii` |
| **crewai-eydii** (this package) | CrewAI | `EydiiVerifyTool` + guardrails + LLM hooks + `EydiiExecuteHook`. Multi-agent crew support. | `pip install crewai-eydii` |
| [llama-index-tools-eydii](https://github.com/veritera-ai/eydii-llamaindex) | LlamaIndex | `EydiiVerifyToolSpec` + event handlers + `EydiiExecuteHandler`. Document agent support. | `pip install llama-index-tools-eydii` |
| [eydii-blog](https://github.com/veritera-ai/eydii-blog) | — | Technical articles on AI agent security and trust verification. | — |

---

## Resources

- [EYDII Documentation](https://id.veritera.ai/docs)
- [EYDII Dashboard](https://id.veritera.ai/dashboard)
- [Policy Configuration Guide](https://id.veritera.ai/docs/policies)
- [CrewAI Documentation](https://docs.crewai.com)

---

## License

MIT -- EYDII by [Veritera AI](https://id.veritera.ai)
