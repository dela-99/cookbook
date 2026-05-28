# Agent Harness — The Deterministic Layer Around Your LLM

## The Interview Question

> "Explain Agent Harness."

Most candidates start with *"well, it uses an LLM that calls tools…"* — and they're already wrong.

Then the follow-up:

> "Your AI agent worked perfectly in the demo. It fails 40% of the time in production. Why?"

The instinct: "We need a smarter model." Or: "We need better prompts." Or: "More context."

All wrong. The model is not the problem. The model is doing its job — generating the next token. The thing that's missing is everything *around* the model: the guardrails that stop it from looping forever, the verifier that runs the tests, the credential injector that handles a login screen the model has never seen, the recovery path when a tool call times out.

That stuff has a name. It's called the **agent harness**, and in 2026 it's quietly become the most important layer in AI engineering — and the one most teams haven't built.

---

## The Mountain Climber Analogy

Think of agent harnessing like mountain climbing.

The AI model is the **climber** — skilled, capable, but probabilistic. On any given step it might lose footing.

The **harness** is the safety rope — anchored firmly into the stable rock of the execution environment. The climber moves freely, takes risks, makes decisions — but the rope stops them from going off the rails.

The harness is **not part of the climber**. It's a separate piece of equipment, wrapped around them, anchored to ground you control. When the model panics, hallucinates, or quietly gives up — the harness is what catches it.

---

## The Three Layers — Prompt, Context, Harness

The field has converged on a clean three-layer model:

| Layer | What it shapes | What it controls |
|---|---|---|
| **Prompt engineering** | The model's **behavior** | What you *say* to the model in a single turn |
| **Context engineering** | The model's **reasoning** | What goes *inside* the context window — RAG retrievals, MCP tool results, conversation history, system prompts |
| **Harness engineering** | The model's **execution** | What happens *around* the agent loop — guardrails, verification, recovery, intervention |

Most engineers stop at context engineering and wonder why their agents are flaky in production. **Reliability is a harness problem, not a model problem.**

Anthropic's framing has become canonical: *"Every component in a harness encodes an assumption about what the model can't do on its own."*

---

## The Anatomy of a Harness

A production-grade harness has four building blocks. Take any one of them away and your agent is a demo, not a product.

### 1. Deterministic Guardrails

Hard limits the harness enforces **independently of the model**:

- **Step throttling** — `max_iterations=40`. After 40 steps, the loop stops. No "but the model said it was almost done."
- **Loop detection** — the harness watches for the same tool call repeating. Three identical actions in a row → break out, escalate.
- **Token budget enforcement** — cap input + output per turn. If the model tries to dump a 200KB file into context, the harness truncates.
- **Context compression** — when the conversation hits a threshold, the harness summarizes older turns into bullet points and drops the raw history.

These run *above* the loop, on every iteration. The model never sees them. They're not instructions — they're walls.

### 2. State & Trace Management

The harness captures execution history **independently of what the model writes**. Every tool call, every input, every output, every error — written to a trace the harness owns. That trace becomes:

- The replay log when something fails in production
- The training data when you fine-tune the next model
- The audit log when compliance asks "what did the agent actually do here?"

The model doesn't summarize what happened. The harness records it.

### 3. External Intervention Layer

This is where the login-screen example lives. A web-browsing agent hits a sudden auth wall. A naive agent panics, hallucinates a success, or loops trying to "figure out" the form.

A harness with an intervention layer detects the login URL **deterministically** — string-match, DOM-match, response-code-match — not by asking the model. It injects credentials from a secret store, fills the form, and passes control back to the agent with a clean state.

The model never handled login. It never had to. The harness handled it the way deterministic software always has — and only the *interesting* decisions land in the model's lap.

### 4. The Verification Loop

The model writes a function. Does the harness believe it? **No.** The harness runs:

- The linter
- The type checker
- The test suite
- Custom assertions ("did this PR touch any file in `infra/`? If yes, require human approval")

If verification fails, the harness feeds the failure back into the next iteration. The model doesn't get to declare victory. The harness does — and only when the deterministic gates say so.

---

## The Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                            USER                                  │
└──────────────────────────────┬───────────────────────────────────┘
                               │  task / request
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                       HARNESS LAYER                              │
│                                                                  │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐     │
│   │  Guardrails  │  │   Hooks &    │  │   Intervention     │     │
│   │ max_iter, …  │  │  Middleware  │  │   (auth, forms)    │     │
│   └──────┬───────┘  └──────┬───────┘  └─────────┬──────────┘     │
│          │                 │                    │                │
│          └─────────────────┼────────────────────┘                │
│                            ▼                                     │
│           ┌────────────────────────────────────┐                 │
│           │            AGENT LOOP              │                 │
│           │   ┌─────────────────────────────┐  │                 │
│           │   │   LLM  ◄── prompt           │  │                 │
│           │   │    │                        │  │                 │
│           │   │    ▼ tool call              │  │                 │
│           │   │   Tool Registry ──► result  │  │                 │
│           │   │    │                        │  │                 │
│           │   │    └── feeds next turn      │  │                 │
│           │   └─────────────────────────────┘  │                 │
│           └────────────────┬───────────────────┘                 │
│                            │ output                              │
│                            ▼                                     │
│   ┌──────────────────────────────────────────────────────┐       │
│   │  VERIFICATION GATE                                   │       │
│   │  lint • tests • assertions • policy checks           │       │
│   └────────────────────────┬─────────────────────────────┘       │
│                            │ pass / retry / fail                 │
└────────────────────────────┼─────────────────────────────────────┘
                             ▼
                          RESULT
                  (state, traces, artifacts)
```

The model is one small box. Everything else is the harness.

---

## Pillar A — Coding Agents (Claude Code, Cursor, Codex)

Modern coding agents are the most mature harness implementations in production. The inner loop is the **Gather → Act → Verify** cycle (Anthropic's framing, used in Claude Code):

1. **Gather** — read files, search the codebase, look up docs
2. **Act** — edit files, run commands, create branches
3. **Verify** — run tests, lint, type-check, evaluate the diff

What the harness adds around that loop:

| Mechanism | What it does |
|---|---|
| **Sandboxed workspaces** | One isolated git worktree per task — the model can't accidentally touch other branches or `infra/` files |
| **Tool curation** | Open SWE caps the agent at ~15 tools enforced at harness design time. More tools = more confusion, not more power |
| **AGENTS.md / project memory** | Repo-wide conventions injected at every loop start so the model doesn't relearn "we use pnpm not npm" every session |
| **Context compaction** | When the conversation pushes 80% of the window, the harness compresses older turns into a summary and keeps the loop running |
| **PR validation gate** | The agent doesn't merge. It opens a PR. CI runs. A human (or another agent) reviews. Verification is structural, not vibes-based |
| **Multi-hour resilience** | If the model hits a rate limit or the API hiccups, the harness pauses, retries with backoff, and resumes from the last checkpoint |

This is why Live-SWE-agent hit **77.4% on SWE-bench Verified** — not because the model got 77.4% smarter, but because the harness around it got 77.4% better at catching the model's mistakes.

---

## Pillar B — Browser Agents & Enterprise RAG

The browser is the *worst* environment to deploy a probabilistic model into. CAPTCHAs, A/B tests, login walls, cookie banners, and a thousand "Accept All" modals that look nothing like the training distribution. Without a harness, browser agents fail in characteristic ways: they hallucinate a click that didn't happen, they spin on a modal forever, or they confidently log in as the wrong user.

Harness mechanisms for browser and enterprise agents:

| Mechanism | What it solves |
|---|---|
| **Deterministic detectors** | "If URL contains `/login`, *don't* ask the model — call the credential injector." No model in the critical path. |
| **Credential injection from env / secret store** | The model never sees the password. The harness pulls it from a vault and types it into the field via deterministic browser automation. |
| **Form state machines** | Multi-step flows (`cart → shipping → payment → review → confirm`) are encoded as state machines. The model picks the next state; the harness enforces that the transition is legal. |
| **Tenant isolation** | Enterprise RAG must never let one user's agent query another tenant's data. The harness scopes every retrieval call to the user's row-level security context — the model is *incapable* of asking for the wrong tenant because the query is rewritten before it hits the index. |
| **Silo boundaries** | "This agent can read from S3 bucket X and Salesforce instance Y — nothing else." Enforced at the network/IAM layer, not by trusting the model not to call other APIs. |
| **Replay & audit traces** | Every action the agent took — with screenshots and DOM snapshots — written to durable storage for compliance review. |

The pattern across both pillars is the same: **deterministic problems get deterministic solutions, and the model only handles the genuinely ambiguous decisions in between.**

---

## Production Considerations

| Decision | What to think about |
|---|---|
| **Don't harness too early** | A prototype doing one-shot tasks doesn't need a verification loop. Add harness mechanisms *as you observe failure modes* (Mitchell Hashimoto's rule: anytime an agent makes a mistake, engineer a solution so it never makes that mistake again). |
| **Every component encodes a past failure** | Every guardrail should trace back to a specific bug you saw in production. If you can't explain *why* a guardrail exists, delete it. |
| **The harness is the moat** | The model is a commodity. Swap GPT-5 for Claude Opus 4.7 — the harness should work unchanged. The harness is what your team actually owns. |
| **Trace everything** | You can't improve the harness without knowing where it failed. Capture every tool call, every retry, every recovery — even when nothing went wrong. |
| **Verification must be cheap and fast** | If running tests takes 20 minutes, the loop stalls. Invest in fast unit tests, partial linting, incremental type-checking. |
| **Plan for human-in-the-loop** | The harness should know when to **stop and ask** rather than retry. Destructive operations, low-confidence states, repeated failures — escalate to a human. |

---

## The Key Insight

The model is the climber. The harness is the rope.

Or, in the framing that's become canonical in 2026 (credit to Rick Hightower):

> **The model is the CPU. The context window is the RAM. The harness is the operating system.**

You don't ship a CPU. You don't even ship RAM. You ship an operating system — and the OS is what makes a chip useful to a human.

Most engineers spend 100% of their effort on the chip (the model) and the memory (the context). They wonder why their agents are flaky in production. The teams shipping reliable agents — Claude Code, Cursor, Codex, Browserbase, Open SWE — have spent the last year building the OS.

---

## TL;DR

- An **agent harness** is the deterministic execution environment wrapped around an LLM agent loop. It's separate from the model and from the context window.
- **Three layers, in order of impact:** prompt engineering (behavior) → context engineering (reasoning) → **harness engineering (execution)**. Most teams stop at layer two.
- **Four building blocks:** deterministic guardrails, state/trace management, external intervention (auth, credential injection, form handling), and a verification loop (lint, test, policy checks).
- **Coding agents** (Claude Code, Cursor, Codex) use harnesses for sandboxing, tool curation, context compaction, and PR-level verification gates.
- **Browser & enterprise agents** use harnesses for credential injection, deterministic flow detection, tenant isolation, and silo boundaries.
- **The model is the CPU. The harness is the OS.** You don't ship a chip — you ship the operating system around it.

If your agent works in the demo but breaks in production, the model isn't the problem. The harness is the missing layer.

---

## Related

- [Pre-Deployment Checklist](../pre-deployment-checklist/) — the production-reliability mindset, applied at the deployment boundary
- [Favourite Claude Code Commands](../../claude-tricks/favourite-claude-commands/) — Claude Code in practice, where the harness is doing the heavy lifting
- [RAG Chunking Strategy](../rag-chunking-strategy/) — the context-engineering layer that sits just below the harness

---

## Resources

### Articles
- [Anthropic — Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [LangChain — The Anatomy of an Agent Harness](https://www.langchain.com/blog/the-anatomy-of-an-agent-harness)
- [Martin Fowler — Harness Engineering for Coding Agent Users](https://martinfowler.com/articles/harness-engineering.html)
- [Augment Code — Harness Engineering for AI Coding Agents](https://www.augmentcode.com/guides/harness-engineering-ai-coding-agents)
- [Rick Hightower — Harness Engineering vs Context Engineering: The Model is the CPU, the Harness is the OS](https://medium.com/@richardhightower/harness-engineering-vs-context-engineering-the-model-is-the-cpu-the-harness-is-the-os-51b28c5bddbb)

### Repos
- [awesome-harness-engineering — curated reading list of harness patterns, evals, MCP, permissions, observability](https://github.com/ai-boost/awesome-harness-engineering)
