# SO-101 build log

The SO-101 page is the robotic-arm build log: dithered header, summary, 3D model, and the Day 01 entry with photos and video.

## Sub-features

- `so101-page` page loads with heading `SO-101 robotic arm`.
- `so101-model` `.viewer` is present with `data-glb="so101.glb"` and poster `arms-wide.webp`.
- `so101-day01` the section `Day 01 · The arms, they move` is visible, with `arms-wide.webp`.
- `so101-back` the brand link `Guilherme Silva` returns home.

## How to get to it (user POV)

- From `/`, choose `SO-101 robotic arm` or the header.
- Open `/robots/so-101/` directly.
- Choose `Guilherme Silva` to leave.

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY (includes `so101.glb` and `arms-wide.webp`).
- Start from `$VERIFY_URL/robots/so-101/`.

- **Open log.** Heading `SO-101 robotic arm` is visible. Screenshot `artifacts/so-101-build-log/page.png`.
- **Model.** `.viewer` is in the page, its poster `img` points at `arms-wide.webp`, and it gets the `ready` class once in view.
- **Day 01.** Heading `Day 01 · The arms, they move` is in the page, with the desk photo.
- **Back.** Click `Guilherme Silva`. Homepage returns.
- **Proof.** Save `artifacts/so-101-build-log/notes.md` with feature ID `so-101-build-log`.

## Gotchas

- There is no `#day-01`, `#so-model`, or Start/Pause control. Match the heading text.
- `so101.glb` is large. A poster image is enough if the viewer has not finished loading.
- Video uses `preload="none"`. Do not require video frames.
