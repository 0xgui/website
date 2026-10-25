# silvags.com verification map

This directory is the maintained source for verifying user-facing behavior of the static site. Read this index before driving, then use the matching feature file as the recipe.

## Baseline preconditions

- Launch with `.cursor/skills/verify-silvags/bin/launch` (default `http://127.0.0.1:8765`).
- Run `.cursor/skills/verify-silvags/bin/doctor` and require `doctor: HEALTHY`.
- Drive only the URL printed by launch. Never drive production `https://silvags.com`.
- Prefer a disposable browser context for theme and feed-cache proofs (`localStorage` keys `theme` and `binary-paths-articles-v1`).
- Concurrent runs need different `VERIFY_PORT` values. One browser profile still shares `localStorage` across ports on the same origin host — clear keys before theme/feed proofs if the profile was used before.

## Driving conventions

- Start every recipe from the launched homepage unless preconditions say otherwise.
- Prefer ARIA roles and accessible names over coordinates.
- Browser: Cursor `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_take_screenshot`, and CDP `Runtime.evaluate` for `localStorage` / class checks.
- Record the feature ID and entry point with every artifact under `.cursor/skills/verify-silvags/artifacts/<feature-id>/`.
- Restore nothing to disk after cleanup except evidence; the server is ephemeral.

## Proof and skip reporting

- Capture the user action and the resulting state, not only the final screen.
- UI proof includes an accessibility snapshot and a screenshot with site identity visible (`Guilherme Silva` or the robot page title).
- Mutation proof (theme, feed cache) includes a CDP read of `localStorage` after the action.
- Report an unreachable path with the attempted step and unmet precondition.
- Do not report a skipped entry point as verified through a different path.

## Feature entry contract

Each feature file starts with an H1 and one paragraph, then exactly four H2s: `Sub-features`, `How to get to it (user POV)`, `Driving it with Cursor browser`, `Gotchas`.

## Features

- [Theme toggle](./theme-toggle.md) — light/dark class and `localStorage` persistence across pages.
- [Homepage builds](./homepage-workbench.md) — Builds heading, SO-101 and Pico cards, navigate into each robot page and back.
- [Writing feed](./writing-feed.md) — Binary Paths snapshot, live RSS refresh, status text, offline fallback.
- [Pico model viewer](./pico-model.md) — GLB viewer, poster fallback path, Start/Pause rotation.
- [SO-101 build log](./so-101-build-log.md) — hero, model, Day 01 entry, deep-link `#day-01`.
