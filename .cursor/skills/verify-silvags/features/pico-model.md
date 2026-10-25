# Pico model viewer

The Pico build page shows a `model-viewer` of simulation geometry (`pico.glb`) with a static poster, then reveals a Start/Pause rotation control after the model loads so visitors can control motion (including when reduced motion is preferred).

## Sub-features

- `pico-page` build notes page loads with title `Pico`.
- `pico-viewer` `#pico-model` is present with poster `pico-preview.webp`.
- `pico-load` after load, caption updates and `#rotation-toggle` becomes visible.
- `pico-rotation` clicking Start/Pause toggles the `auto-rotate` attribute and button label.
- `pico-error` on GLB failure, caption becomes static preview and the toggle stays hidden (failure for the happy path).

## How to get to it (user POV)

- Open `/robots/pico/` from the homepage (`Open Pico →`) or directly.
- After the model loads, use `Pause rotation` / `Start rotation` under the viewer.

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY (includes `pico.glb` and `pico-preview.webp` HTTP 200).
- Navigate to `$VERIFY_URL/robots/pico/`.

- **Page identity.** Heading `Pico` and kicker mentioning self-righting are visible. Screenshot `artifacts/pico-model/page.png`.
- **Viewer present.** Snapshot or CDP: element `#pico-model` exists; poster/img references `pico-preview.webp`.
- **Wait for load.** Wait until `#rotation-toggle` is not `hidden` (or caption contains `drag to rotate`). If after ~15s the toggle stays hidden and caption says `static preview`, the GLB path failed — record failure.
- **Pause rotation.** Click `Pause rotation` (when auto-rotate is on). Button label becomes `Start rotation`. CDP: `document.getElementById('pico-model').hasAttribute('auto-rotate')` is `false`.
- **Start rotation.** Click `Start rotation`. Label returns to `Pause rotation`; `auto-rotate` is present again.
- **Proof.** Screenshots before/after toggle under `artifacts/pico-model/`, plus `notes.md` with feature ID `pico-model`.

## Gotchas

- `#rotation-toggle` starts `hidden` until the `load` event — do not click it immediately on navigate.
- `prefers-reduced-motion: reduce` starts rotation off (`Start rotation` label). Emulated reduced motion changes the baseline; assert labels against the actual starting state.
- model-viewer script loads from `unpkg.com`; offline CDN failure blocks the custom element. Doctor does not check unpkg — if the viewer never upgrades, note the unmet network precondition.
- Poster-only display after error is not a pass for the interactive viewer path.
