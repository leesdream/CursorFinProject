# Project Explanation — AI Transformation Interview Reference

This document captures key talking points about the CursorFinProject for use in job interviews,
particularly for AI transformation roles in government.

---

## 1. How Agentic AI Is Used in This Project

### What "Agentic AI" Means

A regular LLM call is: *question in → answer out*.
An **agent** is different: *question in → AI decides what actions to take → takes them → observes results → decides next action → … → answer out*.
The AI drives its own workflow rather than passively responding.

This project implements **five distinct agentic patterns**:

---

### Pattern 1 — Autonomous Tool-Use Loop (`main.py`)

```python
while True:
    response = Claude(messages, tools=yahoo_finance_tools)

    if no tool calls:
        return final_analysis          # Agent decided it has enough data

    for each tool_call in response:
        result = mcp_server.call(tool_call)   # Execute against live API
        messages.append(result)                # Feed result back to agent

    # Loop: Claude decides whether to call more tools or write its conclusion
```

Claude **autonomously decides**:
- Which Yahoo Finance tools to call (quotes, financials, options, recommendations)
- In what order
- When it has gathered enough data to stop

This is the hallmark of an agentic system — **the AI drives the control flow**, not a hardcoded script.

---

### Pattern 2 — Multi-Agent Pipeline with Specialised Roles

Four independent agents, each with a different expertise, analyse the same portfolio:

| Agent | Role | Tools |
|---|---|---|
| **Yahoo Finance Analyst** | Live market data, analyst consensus | Yahoo Finance MCP (10 tools) |
| **Peter Lynch Agent** | GARP scorecard, PEG ratios, 10-bagger hunting | Yahoo Finance MCP |
| **Howard Marks Agent** | Risk-first, second-level thinking | Reasoning only (no tools) |
| **Taleb Agent** | Antifragility, Black Swan exposure | Reasoning only (no tools) |
| **Synthesis Agent** | Cross-agent reconciliation → action plan | Reads all 4 outputs |

Each agent has its own **system prompt, role, and output structure**. The Synthesis Agent then
reconciles disagreements between them — e.g., Lynch may love a fast-grower that Taleb flags as fragile.

---

### Pattern 3 — MCP (Model Context Protocol) for Tool Integration

Rather than hardcoding API calls, agents discover and call external tools via **MCP** — an open
standard (created by Anthropic, now industry-wide) for connecting AI models to data sources.

```python
tools = await session.list_tools()           # Agent discovers what's available
result = await session.call_tool(name, args) # Agent executes against live API
```

**Why this matters for government:** MCP means AI agents can be connected to any data source —
financial databases, legislative systems, public records — **without rewriting the agent**. The
data connection is plugged in; the reasoning stays the same.

---

### Pattern 4 — Prompt-Caching for Cost Efficiency

```python
system=[{
    "type": "text",
    "text": system_prompt,
    "cache_control": {"type": "ephemeral"},  # Anthropic prompt cache
}]
```

System prompts are cached across the multi-turn tool loop, reducing token costs by ~80% on
repeated agent turns. In a government setting processing thousands of documents, this matters
for budget governance.

---

### Pattern 5 — Extensible Agent Registry (`mcp_config.py`)

New analytical capabilities are added by dropping a config block into a list — no code changes:

```python
MCP_SERVERS = [
    { "name": "yahoo_finance", "analysis_prompt": "..." },
    { "name": "peter_lynch",   "analysis_prompt": "..." },
    # Add a new government data source here — zero code change needed
]
```

This is the **"plug in a new expert"** pattern: the orchestrator loop runs every agent in the
registry automatically.

---

### Why This Architecture Transfers to Government AI Transformation

| Concept in this project | Government equivalent |
|---|---|
| Portfolio CSV → agent pipeline | Citizen form / procurement doc → analysis pipeline |
| MCP tools (Yahoo Finance) | MCP tools (GovTech APIs, OneMap, data.gov.sg) |
| Multi-agent specialist roles | Legal analyst, risk analyst, policy analyst agents |
| Synthesis agent reconciling views | Committee recommendation generation |
| Pluggable `mcp_config.py` registry | New ministry data source onboarded without changing core AI logic |
| Prompt caching for cost control | Budget governance for AI API spend at scale |

The core skill demonstrated is **designing AI systems that can act autonomously, use real data,
and be extended without rewriting** — exactly the architecture pattern needed for government
digital transformation at scale.

---

## 2. Using Domain Knowledge to Write Accurate Prompts for Government

### The Problem

The `analysis_prompt` strings in this project were written by Claude (the AI model), which
produces generic financial advice. For government, prompts must encode **specific laws, rules,
and official frameworks** — things only a domain expert knows.

The key insight: **the prompt is the policy encoding**. Writing and maintaining prompts is a
domain-expert job, not an AI job. Engineers build the pipeline; subject matter experts own the
prompts.

---

### Pattern 1 — Expert Co-Authoring (the baseline)

A domain expert (e.g., AGO auditor) writes the prompt instead of letting the AI guess:

```python
# Generic AI-authored prompt (bad for government):
"Analyze this portfolio through Howard Marks' risk control framework..."

# Government domain expert-authored prompt (grounded in actual law):
"You are reviewing a procurement file against Singapore's Government
Procurement Act (Cap 120) and GeBIZ standing rules. Flag:

1. Non-compliance with Rule 4 — open tender threshold ($90,000 for goods/services)
2. Waivers of competition — check if justification meets the 5 permitted grounds
   under GeBIZ Standing Rule 7.2 (sole source, urgency, security, etc.)
3. Abnormally low bids — flag if winning bid is >15% below next lowest
4. Recurring vendors — flag if same vendor wins >3 awards in 12 months
   from same agency without explanation

Cite the specific rule number for every finding."
```

The AI still does the work — but now it's grounded in **actual law and rules**.

---

### Pattern 2 — Embed Reference Documents in Context

Load the **actual circular / act / framework** into the prompt at runtime so the AI reasons
from the real text, not its (potentially outdated) training data:

```python
from pathlib import Path

def _load_reference(filename: str) -> str:
    path = Path(__file__).parent / "reference" / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""

PHILOSOPHY_ANALYSES = [
    {
        "name": "procurement_audit",
        "section_title": "Procurement Compliance Audit",
        "system_prompt": "You are a government auditor. Cite specific rule numbers.",
        "analysis_prompt": (
            "Reference rules in effect:\n\n"
            f"{_load_reference('gebiz_standing_rules.txt')}\n\n"
            "---\n"
            "Audit the procurement records above against these rules.\n"
            "For each finding state: Rule number | Observation | Severity (High/Med/Low)"
        ),
    },
]
```

When regulations change → update `reference/` documents. The AI pipeline is unchanged.

---

### Pattern 3 — Structured Output Tied to Official Frameworks

Encode the **exact table/section structure** of existing government forms into the prompt so
AI output slots directly into official reports without translation:

```python
"analysis_prompt": (
    "Assess this proposal using the WOG IM8 ICT&SS Policy compliance checklist.\n\n"
    "For each control domain, output exactly:\n"
    "| Domain | Control Ref | Status (Compliant/Gap/N/A) | Finding | Recommendation |\n\n"
    "Domains to cover:\n"
    "- Data Classification (IM8 Section 4.1–4.3)\n"
    "- Access Control (IM8 Section 5.1–5.6)\n"
    "- Incident Management (IM8 Section 8.1–8.4)\n"
    "- Third-Party Risk (IM8 Section 10.1–10.5)\n\n"
    "End with an overall risk rating: Critical / High / Medium / Low "
    "using the same definitions as GovTech AIBOM standard v2.1."
)
```

---

### Pattern 4 — Few-Shot Examples from Real Cases

Show the AI a **real example** of a correct expert analysis, then ask it to do the same:

```python
"analysis_prompt": (
    "Here is an example of a correctly-structured finding from a past AGO audit:\n\n"
    "EXAMPLE:\n"
    "Agency XYZ awarded Contract #2023-ICT-0042 ($2.1M) via limited tender "
    "citing urgency (GeBIZ SR 7.2(c)). However, the award date was 6 months "
    "after the project start date, undermining the urgency justification. "
    "Risk: HIGH. Recommendation: Agencies should initiate procurement at "
    "project approval, not after commencement.\n\n"
    "---\n"
    "Now apply the same analytical approach to the procurement records provided."
)
```

---

### The Practical Workflow: Building Prompts with Domain Experts

```
Phase 1 — Expert Interview
    SME (auditor / legal officer / policy analyst) describes:
    - What do you look for?
    - What are the top 5 most common errors?
    - What rule/framework governs each check?
    - What does a good finding look like?

Phase 2 — Draft Prompt
    Engineer translates the interview into a structured analysis_prompt.
    Reference documents go into reference/ folder.

Phase 3 — Expert Review of AI Output
    Run the agent on 10 real cases where the correct answer is known.
    SME grades each AI finding: Correct / Missed / Hallucinated.

Phase 4 — Prompt Iteration
    Fix every missed or hallucinated finding by tightening the prompt:
    - Add the missed rule explicitly
    - Add a "do not assume X if Y is not present" guard
    - Add a real example of the missed case (few-shot)

Phase 5 — Ongoing Maintenance
    When regulations change → update reference/ documents.
    The AI logic doesn't change — only the source documents do.
```

---

### Summary Table

| Problem | Solution |
|---|---|
| AI writes generic analysis | SME writes the `analysis_prompt` |
| AI training data may be outdated | Load real policy docs from `reference/` folder at runtime |
| Output doesn't match official forms | Encode the exact table/section structure in the prompt |
| Hard to know if AI is right | Test against known past cases, iterate prompt until it matches |
| Regulations change | Update `reference/` files — prompt logic unchanged |
