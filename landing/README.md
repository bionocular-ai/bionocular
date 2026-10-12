# Bionocular landing page

The public marketing page served at https://bionocular.ai from Cloudflare Pages. Static HTML, CSS and vanilla JS, no framework.

## Structure

```
landing/
├── index.html              page markup
├── styles.css              hand-written styles
├── script.js               behaviour (hero rotator, nav)
├── tailwind.input.css      Tailwind source
├── tailwind.generated.css  built Tailwind output, committed and served as-is
├── tailwind.config.js
├── _headers                Cloudflare Pages headers (CSP and security headers)
├── fonts/                  self-hosted Plus Jakarta Sans (the wordmark face) and its licence
├── logo.svg, icon.svg, favicon.ico, apple-touch-icon.png, og.jpg, Bionocular.mp4
```

## Local development

```bash
cd landing
python3 -m http.server 8000
```

Then open http://localhost:8000.

After changing Tailwind classes in `index.html`, rebuild the generated CSS and bump the `?v=` cache-bust strings in `index.html`:

```bash
cd landing
npm install
npm run build:tailwind
```

## Deployment

Cloudflare Pages deploys from this repo on every push to `main`:

| Setting | Value |
| --- | --- |
| Repository | `bionocular-ai/bionocular` |
| Production branch | `main` |
| Root directory | `landing` |
| Build command | none |
| Build output directory | `.` |
| Build watch paths (include) | `landing/*` |

The watch path keeps commits to `web/` and `melanoma/` from triggering a landing redeploy.

When adding a third-party script, image host or analytics beacon, allow it in the CSP in `_headers` or the browser will block it.
