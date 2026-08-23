# Deployment and Rollback — BSOS

## Surfaces

1. **Local kernel deployment (full product).** `make setup && make dev` —
   FastAPI :8000 + UI :5173. All workflows (custody, approvals, ledger,
   escalations) live here. `make backup` archives `var/` and
   externalizes the ledger head hash; `make migrate` applies Alembic
   migrations. Rollback = restore `var/` backup + check out the previous
   tag; SQLite means state rollback is a file copy.

2. **Hosted preview (Vercel).** Project `beyond-style-ops`:
   - Static UI: built by cloning the deploy branch and running
     `vite build` (`VITE_DEMO=1`) — build command lives in the project
     settings and starts with `rm -rf repo dist` to defeat build cache.
   - Serverless pipeline: `api/studio.py` (source of truth:
     `deploy/vercel/studio.py`), Python function, 1024 MB / 60 s,
     `requirements.txt` installs `bsos` from the deploy branch.
   - `vercel.json`: SPA rewrites (`/((?!api/).*) → /index.html`),
     `/api/studio/(.*) → /api/studio`, daily health cron
     (`0 3 * * *`).

## Deploy procedure (hosted preview)

1. Push the deploy branch.
2. Trigger a Vercel deployment of the shell files (package.json,
   requirements.txt, vercel.json, api/studio.py).
3. Smoke test on the deployment URL: `/api/studio/health`, a
   `/api/studio/preview?text=…` request, one ZIP export, `/design` and
   `/reveal/1` deep links.
4. Only then rely on the production alias.

**Deployment authorization rule:** production deploys happen only on
explicit owner authorization — never automatically from a merge.

## Rollback (hosted preview)

Vercel keeps immutable deployments: promote the previous deployment to
the production alias (instant, no rebuild). Because the function is
stateless, rollback has no data migration concerns.

## Known operational limits

- Vercel free tier: **100 deployments/day** — exhausting it returns 402;
  wait for the daily reset (this occurred once during development).
- Function cold start ≈ 1–2 s (Python + font load); daily health cron
  keeps it warm-ish.
- The sandbox/agent environment cannot fetch `*.vercel.app` directly;
  verification goes through the Vercel tooling.

## Environments and secrets

No runtime secrets on the hosted preview. Local deployment reads `.env`
(never committed); the API token is generated into `var/api-token.txt`.
