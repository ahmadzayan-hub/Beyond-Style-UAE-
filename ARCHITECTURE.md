# BSOS Architecture

```
┌─────────────────────────────────────────────┐
│  SHELL        React web UI, five workspaces  │
├─────────────────────────────────────────────┤
│  ORCHESTRATOR plan, dispatch, state machine  │
├─────────────────────────────────────────────┤
│  AGENTS       5 scoped agents, own grants    │
├─────────────────────────────────────────────┤
│  SKILLS       composable capability units    │
├─────────────────────────────────────────────┤
│  KERNEL       policy engine, ledger, bus     │
├─────────────────────────────────────────────┤
│  MEMORY       session, domain, vector, audit │
├─────────────────────────────────────────────┤
│  ADAPTERS     LLM, vision, imagegen, MCP     │
└─────────────────────────────────────────────┘
```

## The kernel call path

There is exactly one path from an agent to a skill or adapter:

```
Agent.act → Kernel.invoke
  1. resolve skill (unknown tool → rejected + ledgered)
  2. grant check (agent GrantSet must cover the tool AND the skill's
     declared required grant) → GrantViolation
  3. policy evaluation — every applicable policy by skill tag, every
     outcome (allow/deny/escalate) written to the ledger
  4. deny → PolicyDenied; escalate → persisted Escalation + decision card
  5. dispatch skill(ctx, **payload) with ToolContext.adapters injected
  6. outcome ledger entry (duration, side-effect profile)
```

Skills receive adapters only through `ToolContext.adapters`, which only the
guard populates. `tests/test_import_graph.py` walks the AST of
`agents/`, `skills/` and `orchestrator/` and fails the build if any module
imports `bsos.adapters` — the composition root (`api/bootstrap.py`) is the
single place adapters meet the kernel.

## Grant matrix (the security model, implemented literally)

| Agent | Owns | Tool grant | Explicitly denied |
|---|---|---|---|
| Custodian | asset custody | `graph.*`, `library.*`, `licence.*`, `vision.extract`, `vision.extract_video` | `generate.*`, `export.catalogue` |
| Analyst | trend synthesis | `corpus.*`, `vector.*`, `memory.domain.read`, `brain.search` | `library.ingest`, `generate.*` |
| Designer | concept origination | `generate.image` (text only), `concept.*`, `originality.gate`, `brain.search` | every image-bearing tool incl. `vision.extract`, `library.read_binary`, `library.*`, `graph.*` |
| Producer | workshop spec | `spec.*`, `pricing.*`, `memory.domain.*`, `brain.search` | `generate.*`, `export.*` |
| Publisher | export guard | `export.*`, `manifest.*`, `ledger.append` | `generate.*`, `library.ingest` |
| Calligrapher | design studio (deterministic typography → workshop files) | `design.*`, `brain.search` | `generate.image`, `vision.extract`, `library.*`, `graph.*`, `export.*`, `asset.*` |

`brain.search` is read-only access to the owner's Second Brain notes; no
agent holds a brain-write grant. Video extraction is Custodian-only and
licence-gated like every third-party ingest.

Grants are immutable after registration and bare `*` is rejected. The
Designer's denial of `vision.extract` is load-bearing: abstraction happens
in the Custodian, the Designer receives attribute JSON only, and P1 becomes
structural rather than aspirational.

## Why enforcement lives in the kernel, not the prompt

Prompts can be argued with, forgotten across a long session, or overridden
by a persuasive user turn at midnight. A capability grant cannot. An agent
that must never touch image bytes is not told not to — it is issued a grant
containing no image-carrying tool, and the kernel rejects any call outside
the grant before the tool is reached. Agent prompts (`agents/prompts/`)
describe role, output contract and tone only; deleting them entirely would
not weaken a single compliance guarantee.

## Memory

- **Session** — working state per run, discarded on completion.
- **Domain** — SQLite via SQLModel; an index over the folders, never the
  source of truth (`library.reconcile` rebuilds it from sidecars).
- **Vector** — float32 embeddings in SQLite, cosine search in-process;
  powers the originality gate and semantic corpus search.
- **Provenance** — append-only hash-chained JSONL per concept, PDF export.
- **Ledger** — append-only hash-chained JSONL for every kernel decision.

## Orchestrator

`state_machine.py` enforces the fixed pipeline (intake → … →
catalogue_ready) with one-step transitions, human decision gates
(brief→generation, spec→prototype, photograph→catalogue_ready), reroll
accounting on gate rejections, and an origin=workshop_photograph check on
the final transition — in the machine itself, not only the UI. The
dispatcher maps stages to owning agents; dispatching to the wrong agent
fails on grants.
