# BSOS — Beyond Style Agentic OS

An agentic operating system for Beyond Style UAE (Dubai, personalised
jewellery and gifts, in-house workshop). BSOS runs the loop from market
signal to shippable product:

```
licensed asset custody → market abstraction → trend synthesis
→ original concept origination → originality verification
→ workshop specification → prototype → real photography → catalogue
```

**Architectural principle: the kernel enforces, the prompt does not.**
Every compliance rule (P1–P8) is kernel middleware on the tool-call path
plus capability scoping on the agent registry — see `ARCHITECTURE.md` and
`COMPLIANCE.md`.

## Agentic OS component map

| Component | Where it lives |
|---|---|
| Orchestrator | `bsos/orchestrator/` — planner, dispatcher, state machine |
| Agents | `bsos/agents/` — custodian, analyst, designer, producer, publisher, calligrapher |
| Skills | `bsos/skills/` — 51 registered units behind the kernel guard |
| MCP (agentic tools) | `bsos/adapters/mcp.py` — per-tool grants, same guard |
| Memory — project progress & sessions log | `Milestone` / `SessionLogEntry` tables, `/api/progress`, `/api/sessions-log` |
| Brain (Second Brain) | `bsos/memory/brain.py` — SQLite FTS5 notes, `/api/brain/notes`, read-only `brain.search` grant |
| LLMs — local / API | `bsos/adapters/llm.py` — Ollama (local) or Anthropic (API); subscription chat plans have no API (see SETUP.md) |
| Photo recognition | `vision.extract` — vision LLM → attribute JSON only |
| Video recognition | `vision.extract_video` — frame sampling + per-frame extraction (`bsos[video]`) |
| Jewellery image generation | `generate.image` — Nano Banana family, text-only in, `CONCEPT_ONLY` out |
| Jewellery design engineering expert | `spec.engineering_review` + `bsos/knowledge/jewellery_engineering.md` |
| AI Custom Design Studio | `bsos/design_studio/` — deterministic Arabic typography (HarfBuzz), Diwani-inspired variants, geometry validation, workshop exports (see `docs/design-studio.md`) |

## Run it

```bash
make setup   # Python venv + npm install
cp .env.example .env
make dev     # API :8000, UI :5173  (Windows: scripts\dev.ps1)
make test    # kernel/policy/pipeline test suite
```

On first boot an API token is generated into `var/api-token.txt` (or set
`BSOS_API_TOKEN`); the UI prompts for it once. The **Command** workspace is
the animated executive view — core pulse, live metrics, the specialist agents
with owner-uploaded photos, and the live intelligence stream — all backed by
real kernel telemetry. `make backup` archives `var/` and externalizes the
ledger head hash; `make migrate` applies Alembic migrations;
`/api/metrics` serves Prometheus counters.

## Layout

```
bsos/kernel/        policy engine, guard, grants, ledger, bus
bsos/agents/        custodian, analyst, designer, producer, publisher, calligrapher (+prompts)
bsos/skills/        registered capability units (asset/corpus/concept/spec/export/design)
bsos/design_studio/ typography engine, composition, validation, exports, approved fonts
bsos/memory/        session, domain (SQLite), vector, provenance
bsos/adapters/      llm, vision, imagegen (Nano Banana), graph API, MCP
bsos/orchestrator/  planner, dispatcher, state machine
bsos/api/           FastAPI + composition root
ui/                 React 18 / Vite / TS / Tailwind — seven workspaces
tests/              policy, grants, gate, pipeline, adapter tests
docs/               threshold tuning, sample provenance PDF
library/ corpus/ exports/   data folders (disk is the source of truth)
```

## Documentation

- `SETUP.md` — Meta app + token setup, imagegen keys, tuning procedure
- `COMPLIANCE.md` — the eight policies and what BSOS does not do
- `ARCHITECTURE.md` — layers, grant matrix, kernel call path
- `docs/threshold-tuning.md` — originality gate tuning (with honest status)
- `docs/design-studio.md` — Design Studio: deterministic spelling, trust ladder, workshop files
- `templates/supplier-permission-letter.md` — bilingual permission letter

### Audit & release documentation (2026-08 pass)

- `docs/PROJECT_AUDIT_BASELINE.md` — baseline measurements, findings #1–11
- `docs/PRODUCT_REQUIREMENTS_AND_USER_JOURNEYS.md` — personas, FRs, verified journeys
- `docs/UX_UI_DESIGN_SYSTEM.md` — tokens, components, a11y and contrast standards
- `docs/AI_SYSTEM_AND_PROMPT_ARCHITECTURE.md` — where AI is and is not used
- `docs/AI_EVALUATION_PLAN.md` — golden tests, batteries, eval cadence
- `docs/SECURITY_AND_RESPONSIBLE_AI_ASSESSMENT.md` — controls, open risks, RAI posture
- `docs/PERFORMANCE_REPORT.md` — Lighthouse before/after, what changed
- `docs/REQUIREMENTS_TRACEABILITY_MATRIX.md` — requirement → code → test
- `docs/TEST_STRATEGY.md` — layers, commands, CI gap plan
- `docs/DEPLOYMENT_AND_ROLLBACK.md` — local + Vercel procedures, rollback
- `docs/RELEASE_READINESS_REPORT.md` — gate results, verdict, reproduction commands
- `CHANGELOG.md` — release notes

## CLI

```bash
.venv/bin/python -m bsos.cli audit <concept_id>   # replay provenance chain
.venv/bin/python -m bsos.cli verify-ledger        # verify audit hash chain
```
