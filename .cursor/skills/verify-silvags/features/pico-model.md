# Pico model

The Pico page shows the dithered header, the build notes, and a three.js `.viewer` of the simulation geometry with poster `pico-preview.webp`. Dragging the model rotates it. There is no separate Start/Pause button.

## Sub-features

- `pico-page` heading `Pico` is visible.
- `pico-viewer` `.viewer` has `data-glb="pico.glb"` and the poster `pico-preview.webp`.
- `pico-caption` the caption says the geometry is the simulation pose.
- `pico-back` `Guilherme Silva` returns home.

## How to get to it (user POV)

- Open `/robots/pico/` from the homepage bench link or directly.
- The model sits under the summary. Drag to rotate when it has loaded.

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY (includes `pico.glb` and `pico-preview.webp`).
- Start at `$VERIFY_URL/robots/pico/`.

- **Page.** Heading `Pico` is visible. Screenshot `artifacts/pico-model/page.png`.
- **Viewer.** `.viewer` is present with `data-glb="pico.glb"` and poster `pico-preview.webp`; once scrolled into view it gets the `ready` class.
- **Caption.** Text `Simulation geometry, neutral pose` is visible.
- **Proof.** Save `artifacts/pico-model/notes.md` with feature ID `pico-model` and whether the model finished loading or the poster was still showing.

## Gotchas

- There is no `#pico-model` and no `#rotation-toggle`. Do not fail the page for their absence.
- The dithered header is separate from the model viewer. A missing WebGL header is not a failure of the GLB if `.viewer` is in the DOM.
- The poster is the fallback while the GLB loads. Note it if the load does not finish.
