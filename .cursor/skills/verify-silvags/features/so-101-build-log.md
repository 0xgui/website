# SO-101 build log

The SO-101 page is the robotic-arm build log: hero summary, 3D CAD model, progress, and dated Day 01 entry with media, reachable from the homepage and via `#day-01` deep links.

## Sub-features

- `so101-page` page loads with heading `SO-101 Robotic Arm`.
- `so101-model` `#so-model` is present with `so101.glb` / poster `arms-wide.webp`.
- `so101-day01` log entry `#day-01` titled `The arms, they move` is visible.
- `so101-deeplink` navigating to `#day-01` scrolls/highlights that entry.
- `so101-back` `← Back to home` returns to the homepage.

## How to get to it (user POV)

- From `/`, choose `Open SO-101 →`.
- Open `/robots/so-101/` or `/robots/so-101/#day-01` directly.
- Choose `← Back to home` to leave.

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY (includes `so101.glb` and `arms-wide.webp`).
- Start from `$VERIFY_URL/` or go directly to `$VERIFY_URL/robots/so-101/`.

- **Open log.** Navigate to `$VERIFY_URL/robots/so-101/`. Heading `SO-101 Robotic Arm` is visible. Screenshot `artifacts/so-101-build-log/page.png`.
- **Model.** Confirm `#so-model` exists (custom element `model-viewer`). Poster path `arms-wide.webp`. Wait briefly for load; a console warn alone is not enough — prefer that the viewer remains in the DOM without replacing the page.
- **Day 01.** Scroll or query `#day-01`. Heading `The arms, they move` and media (`arms-wide.webp`, teleop videos) are present.
- **Deep link.** Navigate to `$VERIFY_URL/robots/so-101/#day-01`. Entry `#day-01` is in view (or has class `log-flash`). Screenshot `artifacts/so-101-build-log/day-01.png`.
- **Back.** Click `← Back to home`. Homepage hero returns.
- **Proof.** Save `artifacts/so-101-build-log/notes.md` with feature ID `so-101-build-log` and entry points used.

## Gotchas

- SO-101 has no Start/Pause rotation control (unlike Pico); do not look for `#rotation-toggle`.
- `so101.glb` is large (~1.2MB); allow time before asserting interactive orbit.
- Video sources use `preload="none"`; autoplay may not start until near viewport — do not require video frames for page proof.
- Deep-link highlight animation is transient; assert scroll target id/heading, not the flash class alone after several seconds.
