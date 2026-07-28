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

## LLM / vision extraction

Set `ANTHROPIC_API_KEY` for attribute extraction (vision → structured JSON;
the image never travels past the adapter) and bilingual copy scaffolds.

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
