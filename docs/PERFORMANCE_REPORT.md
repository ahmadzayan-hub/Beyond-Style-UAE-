# Performance Report — BSOS UI

Environment: local production build (`npm run build`) served with the
real serverless pipeline mounted (FastAPI, port 4188); Lighthouse 12,
mobile emulation, headless Chromium. Lab numbers — production hardware
and network will differ, but deltas are attributable to the changes.

## Before → after (route `/design`)

| Metric | Baseline | After this pass |
|---|---|---|
| Lighthouse Performance | 73 | **83** |
| Lighthouse Accessibility | 95 | **100** |
| Lighthouse Best Practices | 100 | **100** |
| Lighthouse SEO | 92 | **100** |
| CLS | **0.268** | **0** |
| TBT | 30 ms | 40 ms |
| Initial JS (uncompressed) | 318.9 kB, monolithic | **258 kB** shell + per-page chunks |

## What changed

1. **CLS 0.268 → 0.** The landing showcase panel was injected after an
   async fetch, pushing content down. The panel container is now always
   rendered with reserved space (`min-h-[16rem] sm:min-h-[13rem]`) and a
   skeleton until the SVG arrives.
2. **Route-level code splitting.** All 8 pages load via `React.lazy` +
   `Suspense`; the initial bundle carries only the shell. Page chunks:
   DesignStudio 18.3 kB, Reveal 11.6 kB, others 5–15 kB, loaded on
   navigation.
3. **Self-hosted fonts.** Google Fonts `<link>`s removed from
   `ui/index.html`; Cinzel/Montserrat/Noto Sans Arabic ship via
   `@fontsource` from our own origin — removes a third-party render
   dependency (and the 1-per-route console error in restricted networks).
4. **SEO 92 → 100.** Meta description + `theme-color` added; real
   `robots.txt` served (the SPA rewrite had been returning HTML for it).

## Remaining performance opportunities (recorded)

- Perf 83 is bounded by LCP on the showcase SVG under mobile throttling;
  inlining a low-res placeholder or preloading the demo SVG could recover
  ~5 points.
- The serverless preview endpoint cold-starts Python + font loading
  (~1–2 s first hit after idle); a warm-up cron (`/api/studio/health`
  daily) exists, but a shorter interval would reduce cold hits.
- No CDN-level caching headers are set for `/demo/*` SVGs beyond Vercel
  defaults.

## Reproduction

```bash
cd ui && npm run build
python <scratch>/serve_live.py &          # serves dist + real pipeline on :4188
CHROME_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
  npx lighthouse@12 http://127.0.0.1:4188/design \
  --chrome-flags="--headless=new --no-sandbox --disable-gpu" \
  --output=json --output-path=lh.json
```
