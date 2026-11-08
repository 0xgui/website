# AGENTS.md — Guidance for AI coding agents working on this repo

## What this is

A static personal website (silvags.com) + robotics build log. No framework, no build step, no package manager. Pure HTML/CSS/vanilla JS.

## Structure

```
index.html              Homepage
about/ builds/ talks/ writing/   Section pages
writing/<slug>/         Mirrored Binary Paths essay (index.html, index.md, images/)
robots/so-101/          SO-101 build log and media
robots/pico/            Pico build notes and media
llms.txt llms-full.txt  Agent index and full text, generated from the HTML
robots.txt sitemap.xml feed.xml _headers _routes.json
functions/_middleware.js   Accept: text/markdown negotiation
scripts/                Mirror, agent-file builder, gate path check (not deployed)
tests/                  Stdlib unittest plus one node:test file
favicon.svg             Site icon
worker.js               Cloudflare Worker (RSS proxy, deployed separately)
```

Each robot lives in `robots/<name>/` with its page and media together. Adding a robot = new directory, zero root clutter.

## Architecture

Each HTML page is fully self-contained:
- `<style>` is inline — there is no external CSS file
- `<script>` is inline — there is no external JS file (worker.js is the only standalone JS, deployed separately to Cloudflare)
- Media lives alongside the page in the same `robots/<name>/` directory — use relative paths (e.g. `src="arms-wide.webp"`)

Do NOT create `style.css`, `app.js`, or any external CSS/JS files. If you need styles, add them to the page's `<style>` block. `functions/_middleware.js` is the one exception: a Pages Function, not a browser script. New essays reuse the Writing page's inline style and scripts; do not invent a second visual system.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Homepage — hero, builds, writing, talks, about |
| `robots/so-101/index.html` | SO-101 build log — entries, progress, 3D model viewer |
| `worker.js` | Cloudflare Worker — JSON RSS proxy, plus an hourly full-feed snapshot in KV served at `/raw.xml`. Deployed separately |
| `favicon.svg` | Site icon |
| `robots/so-101/*` | Optimized media (webm/webp) for the SO-101 build log |
| `robots/pico/index.html` | Pico build notes — recovery loop, hardware adaptation, progress |
| `robots/pico/pico.glb` | Neutral robot model converted from SelfRisingRobot MuJoCo meshes |
| `robots/pico/pico-preview.webp` | Static render used as the model poster, homepage card, and OG image |
| `writing/<slug>/` | One mirrored Binary Paths essay: HTML, Markdown twin, optimized images |
| `scripts/mirror_substack.py` | Fetches Binary Paths and writes `writing/<slug>/`. High-tier. |
| `scripts/build_agent.py` | Regenerates Markdown twins, `llms.txt`, `llms-full.txt`, `robots.txt`, `sitemap.xml`, `feed.xml`, `_headers` |
| `functions/_middleware.js` | Serves `index.md` when `Accept` prefers `text/markdown` |
| `llms.txt` | Spec index for agents. Links point at the Markdown twins |

Pico's physical self-righting is confirmed working by the owner. Further measurements and training changes are planned. Its visual is labelled as simulation geometry; use actual supplied footage for any physical demo. Build notes use the same `day-XX` anchor pattern as SO-101 but descriptive labels instead of invented diary dates. The model uses the six meshes from `pico-self-rising-robot/RL/assets`, in their neutral pose, converted from Z-up to Y-up. The site's `.viewer` (see 3D viewers below) displays it, with the static poster as fallback. It does not auto-rotate.

## Important rules

1. **No X/Twitter links** — do not link any X/Twitter profile or handle anywhere in these files.
2. **Keep xgeeks as current employer** — the user is still Engineering Manager there.
3. **Substack is "Binary Paths"** — do not rename it or change the URL.
4. **Media must be optimized** — no files over 1MB. Convert GIFs to webm, PNGs to webp before adding.
5. **Theme system** — `:root` is light, `:root.dark` is dark. Toggle via `#theme-toggle` button. State persisted in localStorage key `theme`.

## Worker.js (Cloudflare Worker)

- Deployed separately at `rss.silvags.com`
- Fetches `https://binarypaths.substack.com/feed`
- Returns JSON: `{ items: [{ title, link, pubDate, description, image }], fetchedAt, stale }`
- `image` field comes from the RSS `<enclosure>` tag
- Cache stays fresh for 1 hour; last-good articles are retained for up to 7 days and served immediately while stale data refreshes in the background. Cache is best-effort, not durable storage.
- Upstream fetch times out after 6 seconds; malformed/empty feeds never replace a good cache.
- The homepage and Writing page link to the local copies under `writing/<slug>/`. They do not call this worker.
- `GET /` is unchanged: JSON `{ items, fetchedAt, stale }`, at most five items, cache key `/__binary-paths-v2`.
- A cron at minute 17 of every hour fetches the full Substack RSS feed (and, if that is not a valid feed, the posts API), retries each request three times, and rejects challenge pages, empty feeds, and malformed XML. A valid result is stored in the `SNAPSHOT` KV binding under `raw.xml`, with `fetchedAt` in the value and in KV metadata. A failed fetch does not overwrite the last good value.
- `GET /raw.xml` serves that snapshot as `application/rss+xml` with `X-Fetched-At`. It does not fetch Substack. A missing or invalid stored value returns 503 and leaves KV as it is.
- `workers_dev = true` keeps `https://rss-worker.zer0hex.workers.dev` available. That host is outside the silvags.com zone, so Bot Fight Mode and AI-bot blocking on the zone do not apply to it. The current deployment still has workers.dev off; the next deploy from `main` turns it on. `https://rss.silvags.com` stays subject to the zone settings until those are turned off.
- Repo changes do nothing until `.github/workflows/deploy-worker.yml` runs on `main`.
- Render feed strings as text, not interpolated HTML; only accept HTTPS article and image URLs.

## CSS conventions

- Variables defined in `:root` and `:root.dark` (same names, different values)
- `--warm` is the accent color (orange/amber)
- `--bg`, `--text`, `--muted`, `--soft`, `--border`, `--card` are the palette
- Fonts: Instrument Serif for headings, Inter for body
- Max content width: 720px (`.wrap` class)

## When making changes

- Read the full file before editing — these are large inline HTML files
- Match the existing style (inline CSS, no Tailwind, no framework)
- Test with `python3 -m http.server 8000` and open in a browser
- Tests: `python3 -m unittest discover -s tests -v`, `node --test tests/negotiate.test.mjs`, and `node --experimental-detect-module --test tests/worker-snapshot.test.mjs`. CI runs all three on pull requests. The `worker dry-run` job runs `scripts/worker_dry_run.py` (whoami, KV, `wrangler deploy --dry-run`) and does not deploy.
- `python3 scripts/build_agent.py --check` fails when Markdown twins or `llms.txt` drift from the HTML
- Don't add dependencies — scripts use the Python stdlib. Image recompression shells out to `ffmpeg` when a download is not already a small WebP. GIFs become WebM.

## Adding a new robot build

### 1. Create the build directory

```bash
mkdir robots/<project-name>
```

Copy `robots/so-101/index.html` as a template. Change:
- Title, meta description, OG image
- Hero section (title, summary, hero image)
- Progress bar segments and steps
- Log entries (use `<article class="entry" id="day-XX">` pattern)
- All links back to homepage: `href="../../index.html"`
- Nav brand link: `href="../../index.html"`

### 2. Add media

Put optimized media in `robots/<project-name>/` alongside the page:
- Videos: `.webm` (ffmpeg: `ffmpeg -i input.gif -c:v libvpx-vp9 -b:v 200k -an output.webm`)
- Images: `.webp` (PIL: resize to max 1600px wide, quality 78)
- Max 500KB per file, max 1MB hard limit
- Reference with relative paths: `src="arms-wide.webp"` (same directory)

### 3. Add a card on the homepage

In `index.html`, the Builds section currently contains SO-101 and Pico:
- Add the new `<article class="build">` inside the existing `.builds-grid` (two columns, `1.5rem` gap).
- Each card keeps the same structure: `build-img`, `build-body` (badges, title, desc, progress), and one primary link (`Open <name> →`) whose hit area covers the card. Do not add a homepage build-notes list or log teaser.
- Link to `robots/<project-name>/`
- Update the build counter to match the number of cards.
- On mobile (<600px): `grid-template-columns: 1fr`

### 4. Build log entry pattern

```html
<article class="entry" id="day-XX">
  <div class="ehead">
    <span class="day">Day XX</span>
    <span class="date">Month DD, YYYY</span>
  </div>
  <h3>Entry title</h3>
  <p>Content...</p>
  <video class="media wide" autoplay muted loop playsinline preload="none">
    <source src="demo-1.webm" type="video/webm">
  </video>
  <p class="caption">Caption text.</p>
</article>
```

### 5. Update AGENTS.md

Add the new project to the file table and note any project-specific conventions.

## Agent files

`python3 scripts/build_agent.py` reads every `index.html` and writes the Markdown twin beside it (`about/index.md`, and so on), plus `llms.txt`, `llms-full.txt`, `robots.txt`, `sitemap.xml`, `feed.xml`, and `_headers`. Each HTML page gets `<link rel="alternate" type="text/markdown">`, a `describedby` link to `/llms.txt`, and an Atom autodiscovery link. Home and About carry Person JSON-LD (`sameAs` is GitHub and LinkedIn only). Robot pages carry CreativeWork. Essays carry BlogPosting.

`llms.txt` follows the v2 shape at https://llmstxt.org: one H1, a blockquote, then H2 sections whose items are Markdown links. Those links point at the twins on `https://silvags.com`.

Content Signals default to `search=yes, ai-input=yes, ai-train=no`. Change `CONTENT_SIGNAL` in `scripts/build_agent.py`, set the same string in `functions/_middleware.js`, and re-run the builder. `tests/test_agent.py` fails if the three copies disagree. `robots.txt` is the file crawlers read. `_headers` repeats the signal on responses.

`functions/_middleware.js` is the free-plan stand-in for Cloudflare Markdown for Agents (that product is not on the free plan). It serves the twin when `Accept` prefers `text/markdown`, with `Content-Type: text/markdown` and `Vary: Accept`. Direct fetches of `index.md` work without the function. `_routes.json` runs the function for HTML and Markdown and skips images, video, and models so those stay ordinary static files. The preview workflow uploads the static tree without the `functions/` directory; Wrangler reads `functions/` from the repo root while deploying that tree. Do not put `_worker.js` in the site or the function is ignored.

The dithered header is the inline module on `.hero`: a poster image first, then a small GLB drawn with three.js from the existing jsDelivr URL and reduced to the page's ink and paper colours. Reduced motion keeps the poster. It is not part of the agent files.

Navigation: the header hero is the home link on every page (`aria-current="page"` on the homepage). The last inline script on every page fetches same-site pages on hover and swaps the children of `.col` in place, so the hero and its WebGL keep running; title, description, canonical and the hero's `href`/`aria-*` are copied from the fetched page, and missing head `<script src>` are added. Anything unexpected falls back to a normal load. So every page must keep the `.col` > `header` + `main` + `footer` shape and the identical `<style>`, and page-specific behaviour must not depend on inline scripts inside `.col` (they are not run after a swap). The hero's `data-robot/anim/seed/glb` and poster style are copied too; the header module keeps one WebGL renderer and, on `site:swap` with a different robot, loads the new GLB and swaps scenes (the old frame stays up until the new one draws). The theme toggle is delegated and listens for the `site:swap` event. Essays inherit all of this from `writing/index.html`; the script must not contain `../`, which the mirror template rewrites.

3D viewers: robot pages use `<div class="viewer" role="img" aria-label="…" data-glb="x.glb" data-orbit="<azimuth> <polar>">` with a poster `<img>` inside. A module on every page (it must be on every page because a swap can bring a viewer in) loads three.js, OrbitControls, RoomEnvironment and DRACOLoader from the same jsDelivr build as the header when a viewer nears the viewport. Drag rotates, scroll or pinch zooms, it renders only while moving, and it frees its WebGL context when swapped out. The poster stays if WebGL or the load fails. `so101.glb` is Draco-compressed, so the Draco decoder is fetched for it alone. Do not reintroduce `model-viewer`: it bundles a second copy of three.js (~258 KB).

Fonts: Newsreader is self-hosted in `fonts/` (SIL OFL, `fonts/OFL.txt`). It is one variable woff2 per style, split into Latin and Latin-ext by `unicode-range`. Every page preloads the normal Latin file and declares the four `@font-face` rules at the top of `<style>` with root-absolute `/fonts/` URLs. A new font version gets a new file name, because `/fonts/*` is cached for a year and marked `immutable`.

404: `404.html` is served by Cloudflare Pages for any unknown path, with status 404. Without it Pages falls back to serving the homepage with 200. It can appear at any depth, so every local URL in it is root-absolute (`/`, `/builds/`, `/robots/…`). Keep its `<style>` and scripts in sync with the other pages.

Caching: `_headers` (generated by `build_agent.py`, `MEDIA_EXTS`) gives media a day of freshness plus a week of stale-while-revalidate, because media file names are not fingerprinted. Replacing a GLB or image can therefore take up to a day to reach repeat visitors. Rename the file if it must be immediate.

Link previews: each essay's `og:image` and JSON-LD `image` are its first local image (`mirror_substack.essay_cover`, usually the Substack cover). Pages without one keep the SO-101 photo.

Sitemap: `lastmod` comes only from dates in the HTML. Essays use their publish date, and the homepage and `writing/` use the newest essay's date. Other pages have none. Do not use git dates, because CI's shallow clone would make `--check` drift.

Markdown negotiation: a client that accepts only `text/markdown` gets 404 for a page that does not exist, and 406 only when the page exists without a twin.

Essay images: `mirror_substack.size_images` adds `width`/`height` read from the WebP header, `decoding="async"`, and `loading="lazy"` to every image but the first. Alt text stays whatever Substack has. Most images have a `figcaption`; add alt text in Substack for ones that need it.

## Mirroring Binary Paths

`python3 scripts/mirror_substack.py` copies every public essay to `writing/<slug>/` using the Writing page as the template. The HTML is sanitized with an allowlist. Images are saved next to the essay and kept under 1MB (GIFs become WebM). Each essay has `<link rel="canonical">` pointing at its `https://binarypaths.substack.com/p/...` URL, a visible "Originally published on Binary Paths" link, the publish date, and a Markdown twin.

The homepage "Latest writing" list (four essays) and the Writing page link to these local copies. The subscribe link stays on Binary Paths. Paywalled or truncated posts become a local excerpt that links back. The script tries, in order, the Substack posts API, the archive API, the RSS feed, `https://rss-worker.zer0hex.workers.dev/raw.xml`, then `https://rss.silvags.com/raw.xml`. It accepts a snapshot when `posts_from_rss` can read at least one item and the body is not a challenge page. GitHub-hosted runners currently receive a Cloudflare challenge page (`Just a moment...`) from the three Substack URLs, measured on Actions run 41346947263. A browser User-Agent does not skip it. `rss.silvags.com` is challenged the same way while Bot Fight Mode and AI-bot blocking are on for the silvags.com zone. `workers.dev` is the path that avoids those zone settings, once this worker has been deployed from `main`.

`writing/last-good.txt` is the newest successful fetch, currently `2026-11-01T18:27:00Z` (the worker JSON `fetchedAt` read from an unchallenged network). A successful run rewrites it only when it is missing or at least 24 hours old, so an unchanged mirror does not open a pull request every time. When every source fails, the run writes nothing. It exits 0, and the workflow does not open the failure issue, while that stamp is under 48 hours old. It exits 1, and the workflow opens or updates the issue, when the stamp is missing or at least 48 hours old. It never deletes an essay that is already on disk, and it never replaces a full essay with a shorter or paywalled body.

`.github/workflows/mirror-substack.yml` runs that script every 6 hours (minute 17) and on `workflow_dispatch`. It opens a pull request with `GITHUB_TOKEN`. GitHub does not start `pull_request` or `pull_request_target` workflows for that token, so this workflow then dispatches `ci.yml` on the mirror branch and runs `agent-pr-gate` with `pr-number`. That puts the check run `test` and the commit status `agent-pr-gate` on the head SHA. Branch protection on `main` should require those two names and no others from this repo. Auto-merge is requested only when `scripts/gate_paths.py` says the diff is not high tier, CI passed, and the gate result is `pass`. A proof dispatch (`proof_slug`) omits one essay on a scratch branch and does not enable auto-merge. A diff that touches a workflow, `_headers`, `_redirects`, `_routes.json`, `functions/`, `worker.js`, `wrangler.toml`, `.review-gate.yml`, or `scripts/mirror_substack.py` is left for a person. If the run fails, it opens or updates a GitHub issue titled "Binary Paths mirror failed" and leaves the live site alone.

Pages Functions are on the free Workers quota (100,000 requests a day, shared with Workers, reset at midnight UTC). `_routes.json` skips images, video, models, and the icon, so those requests stay static and do not count. The default for every Pages project is fail open. After the daily limit, Cloudflare skips the function and serves the static file. HTML still loads. `Accept: text/markdown` falls back to HTML until the next UTC day. Fail closed would return an error page instead. Leave the projects on fail open. The function is not an auth check.

## Cursor Cloud specific instructions

There is no package install and no build. `start` serves this directory with `python3 -m http.server 8000` (all interfaces). Open `http://127.0.0.1:8000`. Check `/`, `/writing/`, one `writing/<slug>/` essay, `/robots/so-101/`, and `/robots/pico/`. The theme toggle is `#theme-toggle` and persists `theme` in localStorage. `/llms.txt` and `/writing/<slug>/index.md` are static files the same server can return. `Accept: text/markdown` negotiation needs the Pages function; the Python server will not do it.

`worker.js` is the Cloudflare RSS proxy and snapshot. It is not started by the local server. Repo changes do nothing until the deploy workflow on `main`. `scripts/worker_dry_run.py` only dry-runs that deploy.

Pull requests can publish a Cloudflare Pages preview from `.github/workflows/pages-preview.yml`. That workflow uploads the static site only (not `worker.js`) to the Pages project `silvags-preview`, on the pull request branch, and comments the preview URL. The live site is a different Pages project, `website` (`silvags.com` / `website-5fv.pages.dev`). Do not direct-upload to `website`. The preview workflow does not deploy `silvags.com` or a Pages production branch.
