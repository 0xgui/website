---
name: verify-silvags
description: >-
  Drive the silvags.com static site (homepage + robot build logs) in a real
  browser to prove user-facing behavior. Use when verifying theme, navigation,
  writing feed, Pico model viewer, or SO-101 build log changes.
---

# Verify silvags.com

Static personal site: pure HTML/CSS/JS, no build step. Primary surface is the web UI at a local `python3 -m http.server`. Secondary surface: Cloudflare Worker RSS at `https://rss.silvags.com` (not started locally; homepage fetches it live). Drive with Cursor's browser tools (navigate / snapshot / click / screenshot / CDP). Do not invent Playwright or other harnesses.

Read `features/README.md` before a run. Use the matching feature file as the recipe.

## Launch

From the repo root:

```bash
.cursor/skills/verify-silvags/bin/launch
```

Optional: `.cursor/skills/verify-silvags/bin/launch 8877` or `VERIFY_PORT=8877`.

- Serves the repo root at `http://127.0.0.1:8765` by default (override with `VERIFY_PORT` / `VERIFY_HOST`).
- Ready when `GET /` returns HTTP 200 (script waits and prints `VERIFY_URL`).
- Writes pid + meta to `.cursor/skills/verify-silvags/.run/` (gitignored).
- Keep the launch shell alive for the whole drive (background terminal with a long sleep after launch, or leave the command running). Some agent shells reap the server process group when the launch command exits even though `python3` was backgrounded.
- Isolation: pick a free port per run. Two instances must use different ports. Theme preference lives in browser `localStorage` key `theme` — clear it or use a fresh browser context before theme proofs so you do not corrupt the user's session. Never drive `https://silvags.com` for verification; only the instance `bin/launch` started.

Teardown: `.cursor/skills/verify-silvags/bin/cleanup` (kills only the recorded pid; keeps `artifacts/`).

## Doctor

```bash
.cursor/skills/verify-silvags/bin/doctor
```

Must print `doctor: HEALTHY` before driving. Checks process, homepage, `/robots/so-101/`, `/robots/pico/`, favicon, key media (webp/glb), theme-toggle presence, and homepage identity (`Guilherme Silva`). If anything looks off mid-run, re-run doctor first.

## Drive

1. `bin/launch` then `bin/doctor`.
2. Open `$VERIFY_URL/` in the Cursor browser (list tabs → navigate → lock before interaction).
3. Prefer ARIA: button `Toggle theme`, links by accessible name (`Open SO-101 →`, `Open Pico →`, `← Back to home`, brand `Guilherme Silva`).
4. Stable IDs when ARIA is thin: `#theme-toggle`, `#articles`, `#articles-status`, `#pico-model`, `#rotation-toggle`, `#day-01`, `#day-02`, `#so-model`.
5. Follow the feature file under `features/`. One feature per proof is enough unless the change spans several.

Pages to cover when relevant: `/`, `/robots/so-101/`, `/robots/pico/`.

## Evidence

Store proof under `.cursor/skills/verify-silvags/artifacts/<feature-id>/` (gitignored; survives cleanup):

| Artifact | Purpose |
|---|---|
| `before.png` / `after.png` | Action vs resulting visual state |
| `aria.txt` | Browser accessibility snapshot (or CDP dump) |
| `notes.md` | Feature ID, entry point, URL, what was observed |

Proof standards:

- Exercise the real user path in the browser (click the control visitors use).
- Capture the action and the resulting state, not only the final screen.
- Theme: assert `document.documentElement.classList.contains('dark')` and `localStorage.theme` via CDP `Runtime.evaluate`, plus a screenshot showing light vs dark.
- Writing feed: assert `#articles` has article links after load (or explicit offline snapshot if the live feed fails); do not treat a green HTTP status alone as proof.
- Model viewer: wait for `model-viewer` load / visible rotation control; poster-only after error is a failure for the GLB path.
- Side effects: `localStorage` for theme; article cache key `binary-paths-articles-v1` when proving feed persistence.
- Do not mock `rss.silvags.com`. If the network fails, prove the static snapshot path and record the unmet live-feed precondition in notes.

## Cleanup

```bash
.cursor/skills/verify-silvags/bin/cleanup
```

Stops the pid recorded by `bin/launch`. Never `pkill -f http.server`. Leaves `artifacts/` and `.run/server.log` alone (log is overwritten on next launch). After cleanup, confirm evidence files still exist under `artifacts/`.

## Helpers

All under `.cursor/skills/verify-silvags/bin/` (executable):

| Command | Role |
|---|---|
| `bin/launch [port]` | Start isolated static server; print `VERIFY_URL` |
| `bin/doctor` | Read-only health check |
| `bin/cleanup` | Stop the launched pid only |

Example session:

```bash
.cursor/skills/verify-silvags/bin/launch
# source .cursor/skills/verify-silvags/.run/meta.env  # VERIFY_URL
.cursor/skills/verify-silvags/bin/doctor
# …browser drive one feature from features/…
.cursor/skills/verify-silvags/bin/cleanup
ls .cursor/skills/verify-silvags/artifacts/
```
