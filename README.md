# silvags.com

Personal website and robot build log of Guilherme Silva. Plain HTML, CSS and JS. No framework, no build step, no dependencies.

## Run it

```bash
python3 -m http.server 8000
```

Open http://127.0.0.1:8000.

## Test it

```bash
python3 -m unittest discover -s tests -v
node --test tests/negotiate.test.mjs
node --experimental-detect-module --test tests/worker-snapshot.test.mjs
python3 scripts/build_agent.py --check
```

## What's where

| Path | What |
|------|------|
| `index.html` | Homepage |
| `about/` `builds/` `talks/` `writing/` | Section pages |
| `writing/<slug>/` | Essays mirrored from Binary Paths |
| `robots/<name>/` | One robot build log per folder, media alongside |
| `scripts/` | Essay mirror and agent-file builder (Python stdlib) |
| `worker.js` | Cloudflare Worker for the RSS feed, deployed separately |
| `llms.txt`, `*/index.md` | Markdown versions for agents, generated |

## Common jobs

- **Edit a page:** change its `index.html`, then run `python3 scripts/build_agent.py` to regenerate the Markdown versions.
- **Pull new essays:** `python3 scripts/mirror_substack.py`. A GitHub Action also does this every 6 hours and merges its own PR.
- **Add a robot:** copy `robots/so-101/` to `robots/<name>/` and add a card on the homepage.

## Rules

- All CSS and JS stay inline in each page. No `style.css` or `app.js`.
- No media file over 1 MB. Use WebP for images and WebM for video.
- Never push to `main`. Open a pull request.

Working on this with an AI agent? Read [AGENTS.md](AGENTS.md).
