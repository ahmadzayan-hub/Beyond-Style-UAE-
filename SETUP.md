# BSOS Setup

## Prerequisites

- Python 3.11+
- Node 18+ (Node 22 tested)
- macOS, Linux, or Windows. On Windows without `make`, use `scripts\dev.ps1`.

## Quick start

```bash
make setup     # venv + pip install + npm install
cp .env.example .env   # fill in keys as below
make dev       # API on http://localhost:8000, UI on http://localhost:5173
make test      # full policy/kernel/pipeline test suite
```

`bsos audit <concept_id>` (or `make audit CONCEPT=<id>`) replays a concept's
full provenance chain to stdout. `make verify-ledger` recomputes the audit
ledger hash chain.

## API authentication (always on)

Every `/api/*` route except `/api/health` requires a bearer token. Set
`BSOS_API_TOKEN` in `.env`, or let BSOS generate one at first boot — it is
written to `var/api-token.txt` (0600, never included in backups) and the
generation is ledgered. The UI asks for the token once and keeps it in the
browser; images and the SSE feed pass it as a `?token=` query parameter
because those contexts cannot set headers.

## Backups and the ledger anchor

The audit ledger is a legal asset stored in `var/`. Run `make backup`
(or `bsos backup --dest <dir>`) to zip `var/` and write the current ledger
head hash to a companion file — store that head file **off the machine**; it
is the tamper anchor that proves the chain was not rewritten. The command
refuses to archive a ledger that fails verification. Schedule it:

- macOS/Linux cron: `0 8 * * * cd /path/to/bsos && make backup`
- Windows Task Scheduler: run `scripts\dev.ps1`'s venv python with
  `-m bsos.cli backup` daily.

## Database migrations

Schema changes ship as Alembic migrations (`migrations/`). On upgrade run
`make migrate` (SQLite batch mode is configured). `requirements.lock`
(regenerate with `make lock`) pins the Python environment; CI installs from
ranges but the lockfile records the tested set.

## CI

`.github/workflows/ci.yml` runs on every push: backend tests + a
fresh-database migration check, UI type-check + build, and a report-only
audit job (pip-audit + npm audit) that surfaces advisories without blocking
compliance fixes.

## Meta Graph API (Business Discovery + own media)

BSOS talks to Instagram **only** through the official Graph API (kernel policy
P7 structurally closes every other path). Setup:

1. **Meta app**: at <https://developers.facebook.com/apps> create an app of
   type *Business*. Add the products **Facebook Login for Business** and
   **Instagram Graph API**. Business Discovery exists on the **Facebook Login
   path only** — do not use the "Instagram Login" (Basic Display / API with
   Instagram Login) path; it cannot see other professional accounts.
2. **Professional account + Page link**: the Beyond Style Instagram account
   must be a professional (business/creator) account linked to a Facebook
   Page you admin. Instagram app settings → Account type → Professional, then
   link the Page under *Sharing to other apps*.
3. **IG user id**: with a User token holding `pages_show_list`, call
   `GET /me/accounts` → your Page id, then
   `GET /{page-id}?fields=instagram_business_account` → `META_IG_USER_ID`.
4. **Token**: generate a User access token in Graph API Explorer with the
   scopes below, then exchange for a long-lived token
   (`GET /oauth/access_token?grant_type=fb_exchange_token&...`, ~60 days).
   Store it in `.env` as `META_ACCESS_TOKEN`.
5. **App Review — permission list**:
   - `instagram_basic` — required, standard approval.
   - `pages_show_list` — required to resolve the linked Page.
   - `pages_read_engagement` — required by the Page/IG account linkage.
   - `business_management` — only if managing the asset through Business
     Manager.
   - **Unverified/flagged**: exact review outcomes for Business Discovery
     depend on Meta's current policy for your app's use case ("provide
     analytics on public professional accounts"). Meta has changed
     business-discovery review requirements repeatedly; treat the scope list
     above as the tested baseline and re-confirm in the App Review console
     before submission. Age-gated target accounts return nothing regardless
     of approval.
6. **Coded-against constraints** (verified in `adapters/graph_api.py` tests):
   targets must be professional accounts; media fields must come through
   nested field expansion in the single business_discovery request (a direct
   GET on a returned media id fails on permissions); cursor pagination lives
   inside the nested `media` object; app rate limit is ~200 calls/hour — the
   adapter buckets at 150 with exponential backoff on 4xx/429 and surfaces
   remaining budget to the UI.

## Image generation (Google Nano Banana family)

Set `GOOGLE_API_KEY` (Google AI Studio). Configured models
(`BSOS_IMAGEGEN_MODELS`), current as of July 2026:

| Model id | Family | Use |
|---|---|---|
| `gemini-3-pro-image` | Nano Banana Pro (Nov 2025) | final renders, up to 4K |
| `gemini-3.1-flash-image` | Nano Banana 2 (Feb 2026) | general work |
| `gemini-3.1-flash-lite-image` | Nano Banana 2 Lite (Jun 2026) | bulk ideation, ~4 s, ≈$0.034 / 1K image |

BSOS reads the **live model list at startup** and refuses to start if a
configured id has disappeared — no silent substitution.

**Watermarking**: every Nano Banana output carries an invisible SynthID
watermark, and Google is expanding C2PA Content Credentials support. AI
renders are therefore permanently identifiable as AI — a further reason
policy P5 (no AI publication) exists: a watermark-detected "product photo"
in a catalogue would be a trust incident.

Without a key, a **local dev placeholder renderer** is used (draws the
prompt text on a card). It is loudly labelled and is not a product visual.

## LLM providers (local / API / subscription)

`BSOS_LLM_PROVIDER` selects the backend for attribute extraction (vision →
structured JSON; the image never travels past the adapter), bilingual copy
scaffolds, and the jewellery engineering review:

- **`anthropic`** (API): set `ANTHROPIC_API_KEY` and optionally
  `BSOS_LLM_MODEL` (default `claude-sonnet-5`). Pay-per-token API billing.
- **`ollama`** (local): install Ollama, `ollama pull llama3.2` (or a
  multimodal model such as `llava` / `llama3.2-vision` if you want local
  attribute extraction), set `OLLAMA_MODEL`, keep `ollama serve` running.
  No key, no cloud; quality depends on the local model.
- **Subscription** plans (claude.ai Pro/Max) are chat products without a
  programmatic API — they cannot back an adapter. If you have a subscription
  but no API key, use `ollama` for automated calls and the chat product for
  interactive work.
- `auto` (default): Anthropic if a key is present, else Ollama if
  `OLLAMA_MODEL` is set, else the LLM-dependent skills fail with a clear
  configuration error.

## Video recognition

`vision.extract_video` samples up to 6 evenly spaced frames from a licensed
video, abstracts each frame with the vision extractor, aggregates attributes
by majority vote, and runs brand-mark detection per frame. It requires the
video extra:

```bash
pip install -e '.[video]'   # imageio + pyav
```

Without it, the skill fails loudly with that exact instruction — no silent
no-op. Videos are licence-gated (P2) like every other third-party asset, and
frames go no further than the extraction call.

## Second Brain, project progress, sessions log

- **Second Brain** (`var/brain.db`, SQLite FTS5): the owner's durable notes —
  decisions, supplier intel, design lessons. API: `GET/POST /api/brain/notes`,
  `GET /api/brain/notes?q=...`. Agents with the read-only `brain.search`
  grant (Analyst, Designer, Producer) can search it; none can write it.
- **Project progress** (`/api/progress`): milestones with status and notes.
- **Sessions log** (`/api/sessions-log`): one summary row per working
  session. Both live in the domain database and are ledgered on creation.

## Originality gate embedder

Production requires CLIP: `pip install -e '.[clip]'`. Without it BSOS falls
back to a deterministic dev embedder that exercises the machinery but is
**not a perceptual model** — the UI/describe() says so on every gate result.
Do not trust originality decisions until CLIP is installed and the threshold
re-tuned (see `docs/threshold-tuning.md`).

## Threshold tuning procedure

Summarised in `docs/threshold-tuning.md`: assemble known-similar and
known-different pairs, sweep the similarity threshold, pick the value with
zero false-passes on known-similar pairs, and record the run. Every runtime
threshold change writes a ledger entry (old, new, actor, reason).

## OCR for mark detection (optional)

`library.ingest` OCRs the bottom 15% and four corners of every asset. With
`pytesseract` + the Tesseract binary installed it reports detected text;
without it a contrast heuristic flags likely text and the sidecar records
which engine ran. Flagged assets go to the review queue — never auto-cleaned.
