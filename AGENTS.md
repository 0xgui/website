# AGENTS.md — Guidance for AI coding agents working on this repo

## What this is

A static personal website (silvags.com) + robotics build log. No framework, no build step, no package manager. Pure HTML/CSS/vanilla JS.

## Structure

```
index.html              Homepage
robots/
  so-101/
    index.html          Build log page (media alongside, relative paths)
    arms-wide.webp
    demo-1.webm
    ...
favicon.svg             Site icon
worker.js               Cloudflare Worker (RSS proxy, deployed separately)
```

Each robot lives in `robots/<name>/` with its page and media together. Adding a robot = new directory, zero root clutter.

## Architecture

Each HTML page is fully self-contained:
- `<style>` is inline — there is no external CSS file
- `<script>` is inline — there is no external JS file (worker.js is the only standalone JS, deployed separately to Cloudflare)
- Media lives alongside the page in the same `robots/<name>/` directory — use relative paths (e.g. `src="arms-wide.webp"`)

Do NOT create `style.css`, `app.js`, or any external CSS/JS files. If you need styles, add them to the page's `<style>` block.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Homepage — hero, workbench, writing, talks, about |
| `robots/so-101/index.html` | SO-101 build log — entries, progress, 3D model viewer |
| `worker.js` | Cloudflare Worker (RSS proxy) — deployed separately, repo change requires Cloudflare redeploy |
| `favicon.svg` | Site icon |
| `robots/so-101/*` | Optimized media (webm/webp) for the SO-101 build log |

## Important rules

1. **No X/Twitter links** — do not link any X/Twitter profile or handle anywhere in these files.
2. **Keep xgeeks as current employer** — the user is still Engineering Manager there.
3. **Substack is "Binary Paths"** — do not rename it or change the URL.
4. **Media must be optimized** — no files over 1MB. Convert GIFs to webm, PNGs to webp before adding.
5. **Theme system** — `:root` is light, `:root.dark` is dark. Toggle via `#theme-toggle` button. State persisted in localStorage key `theme`.

## Worker.js (Cloudflare Worker)

- Deployed separately at `rss.silvags.com`
- Fetches `https://binarypaths.substack.com/feed`
- Returns JSON: `{ items: [{ title, link, pubDate, description, image }] }`
- `image` field comes from the RSS `<enclosure>` tag
- Cached for 1 hour via Cloudflare cache
- Changes to worker.js in this repo do NOT take effect until redeployed to Cloudflare

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
- No test suite — do ad-hoc verification (tag balance, file reference checks)
- Don't add dependencies — this project has none and should stay that way

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

In `index.html`, the Workbench section (`<article class="build">`) is currently a single card. When adding a second robot:
- Wrap existing + new cards in a grid: `<div class="builds-grid">` with `display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;`
- Each card keeps the same structure: `build-img`, `build-body` (badges, title, desc, progress, links), `log-teaser`
- Link to `robots/<project-name>/`
- Update the counter: `<span class="count">02 builds</span>`
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
