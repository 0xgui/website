# Homepage workbench

The homepage introduces Gui, shows a Now strip for the active robot, and lists SO-101 and Pico build cards so visitors can open each build log and return home.

## Sub-features

- `home-hero` shows the name `Guilherme Silva` and Binary Paths mention.
- `home-now` shows the Now strip linking into SO-101.
- `home-so101-card` opens the SO-101 build log from the workbench card.
- `home-pico-card` opens Pico build notes from the workbench card.
- `home-back` returns from a robot page via `← Back to home` or the Pico brand link.

## How to get to it (user POV)

- Open the site root `/`.
- Follow Now title `SO-101 — searching for a brain` or card link `Follow the build log →`.
- Follow Pico card link `Follow the build →` or teaser anchors into `#day-01` / `#day-02`.
- From a robot page, choose `← Back to home` (both) or brand `Guilherme Silva` (Pico).

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY.
- Start at `$VERIFY_URL/`.

- **Hero.** Snapshot the homepage. Heading `Guilherme Silva` is visible. Screenshot `artifacts/homepage-workbench/home.png`.
- **Now strip.** Confirm the Now section links to `robots/so-101/` (accessible name includes SO-101).
- **Open SO-101.** Click `Follow the build log →`. URL ends with `/robots/so-101/`. Heading `SO-101 Robotic Arm` is visible. Screenshot `artifacts/homepage-workbench/so-101.png`.
- **Back home.** Click `← Back to home`. URL is `$VERIFY_URL/` (or `/index.html`). Hero heading returns.
- **Open Pico.** Click `Follow the build →`. URL ends with `/robots/pico/`. Heading `Pico` is visible. Screenshot `artifacts/homepage-workbench/pico.png`.
- **Deep teaser (optional).** From home, click `Two motors, back on its feet` (href `robots/pico/#day-01`). Land on `#day-01` with heading `Two motors, back on its feet`.
- **Proof.** Write `artifacts/homepage-workbench/notes.md` with feature ID `homepage-workbench` and the entry points used. Keep `aria.txt` from the homepage snapshot.

## Gotchas

- Card primary links share similar wording; match the full accessible name (`Follow the build log →` vs `Follow the build →`).
- SO-101 nav has no brand link — only `← Back to home` returns to the homepage.
- External GitHub / Substack links leave the site; do not treat those as proof of workbench navigation.
- Media (`teleop-v2.webm`, posters) may lazy-load; identity proof is the page title/heading, not video playback.
