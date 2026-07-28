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

## Run it

```bash
make setup   # Python venv + npm install
cp .env.example .env
make dev     # API :8000, UI :5173  (Windows: scripts\dev.ps1)
make test    # 68 kernel/policy/pipeline tests
```

## Layout

```
bsos/kernel/        policy engine, guard, grants, ledger, bus
bsos/agents/        custodian, analyst, designer, producer, publisher (+prompts)
bsos/skills/        registered capability units (asset/corpus/concept/spec/export)
bsos/memory/        session, domain (SQLite), vector, provenance
bsos/adapters/      llm, vision, imagegen (Nano Banana), graph API, MCP
bsos/orchestrator/  planner, dispatcher, state machine
bsos/api/           FastAPI + composition root
ui/                 React 18 / Vite / TS / Tailwind — five workspaces
tests/              policy, grants, gate, pipeline, adapter tests
docs/               threshold tuning, sample provenance PDF
library/ corpus/ exports/   data folders (disk is the source of truth)
```

## Documentation

- `SETUP.md` — Meta app + token setup, imagegen keys, tuning procedure
- `COMPLIANCE.md` — the eight policies and what BSOS does not do
- `ARCHITECTURE.md` — layers, grant matrix, kernel call path
- `docs/threshold-tuning.md` — originality gate tuning (with honest status)
- `templates/supplier-permission-letter.md` — bilingual permission letter

## CLI

```bash
.venv/bin/python -m bsos.cli audit <concept_id>   # replay provenance chain
.venv/bin/python -m bsos.cli verify-ledger        # verify audit hash chain
```
