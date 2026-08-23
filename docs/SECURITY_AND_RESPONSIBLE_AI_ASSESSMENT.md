# Security and Responsible AI Assessment — BSOS

## Threat model summary

Two deployment surfaces: (a) the local kernel deployment (full workflows,
token-gated API) and (b) the public Vercel preview (static UI + stateless
serverless pipeline, no auth by design).

## Security controls in place

- **AuthN/AuthZ (local):** API token generated on first boot
  (`var/api-token.txt` or `BSOS_API_TOKEN`); UI token gate. Agents hold
  capability grants; the kernel guard is the single call path, and grant
  violations are rejected and ledgered.
- **Audit:** hash-chained provenance ledger; every policy evaluation
  (allow/deny/escalate) is written to the ledger. `make backup`
  externalizes the ledger head hash.
- **Supply chain:** `npm audit` = **0 vulnerabilities** (was 3 high:
  nanoid, react-router — fixed in this pass). Python deps pinned in
  `requirements.lock`. Fonts vendored (no runtime downloads).
- **Input handling (public endpoints):** inscription length capped
  (MAX_LEN 40), NFC normalization, empty input → 422, mixed script forces
  a choice, exports recomputed deterministically from the inscription —
  no user-supplied files or paths reach the serverless function.
- **Secrets:** no secrets in the repository; `.env.example` only. The
  hosted preview needs no secrets at runtime.
- **No `.AI`-format claims:** vector deliverables are SVG/PDF/DXF;
  licensing honesty is part of the product surface.

## Open risks (recorded, prioritized)

| # | Risk | Severity | Mitigation status |
|---|---|---|---|
| 1 | Public preview endpoints (`/api/studio/*`) have no app-level rate limiting | Medium | Platform-level limits only (Vercel). Compute is bounded (40-char input, no storage). Recommend: per-IP limiter or Vercel WAF rule before marketing push |
| 2 | No CSP header on the hosted preview | Low | App is self-contained (self-hosted fonts, no third-party scripts); add CSP via `vercel.json` headers as follow-up |
| 3 | E2E/security checks not in CI | Low | Scripted locally; wire into CI (see TEST_STRATEGY) |

## Responsible AI assessment

- **Provenance and honesty:** every AI-generated concept is labeled
  `CONCEPT_ONLY`; nothing AI-drawn can become a manufacturing file. The
  hosted preview watermarks all exports `PREVIEW - PENDING WORKSHOP
  APPROVAL`. Approval requires a named human decision, recorded in a
  hash-chained ledger.
- **Cultural/linguistic integrity:** Arabic script is never delegated to
  image models (which routinely corrupt letterforms). Shaping is
  deterministic HarfBuzz with a licensed calligraphic font; diacritics
  handling and mixed-script prompts are explicit, bilingual, and
  fail-closed.
- **Licensing:** fonts are SIL OFL from an approved registry; asset
  custody (P-policies) governs corpus material; no scraping pipelines.
- **Data protection:** the hosted preview stores nothing — inscriptions
  are processed in-memory per request. The local deployment stores
  project data in SQLite under `var/` on the operator's machine. No
  customer PII leaves the WhatsApp conversation the customer initiates.
- **Human oversight:** escalation queue with approve/reject decision
  cards; fail-closed defaults mean silence never equals consent.

## Verification commands

```bash
cd ui && npm audit                 # 0 vulnerabilities
pytest tests/ -q                   # grant isolation + ladder tests included
grep -r "PREVIEW" deploy/vercel/   # watermark path
```
