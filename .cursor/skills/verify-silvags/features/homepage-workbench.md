# Homepage workbench

The homepage introduces Gui, leads with the Binary Paths writing feed, and keeps a small Now building strip so visitors can open the SO-101 and Pico build logs and return home.

## Sub-features

- `home-hero` shows the name `Guilherme Silva` and Binary Paths mention.
- `home-now` shows the Now building strip linking into SO-101 and Pico.
- `home-so101-card` opens the SO-101 build log from `Follow the build log →`.
- `home-pico-card` opens Pico build notes from `Follow the build →`.
- `home-back` returns from a robot page via `← Back to home` or the Pico brand link.

## How to get to it (user POV)

- Open the site root `/`.
- Follow Now title `SO-101 — searching for a brain` or `Follow the build log →`.
- Follow Pico's `Follow the build →`.
- From a robot page, choose `← Back to home` (both) or brand `Guilherme Silva` (Pico).

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY.
- Start at `$VERIFY_URL/`.

- **Hero.** Snapshot the homepage. Heading `Guilherme Silva` is visible. Screenshot `artifacts/homepage-workbench/home.png`.
- **Now strip.** Confirm the Now building section links to `robots/so-101/` (accessible name includes SO-101) and `robots/pico/`.
- **Open SO-101.** Click `Follow the build log →`. URL ends with `/robots/so-101/`. Heading `SO-101 Robotic Arm` is visible. Screenshot `artifacts/homepage-workbench/so-101.png`.
- **Back home.** Click `← Back to home`. URL is `$VERIFY_URL/` (or `/index.html`). Hero heading returns.
- **Open Pico.** Click `Follow the build →`. URL ends with `/robots/pico/`. Heading `Pico` is visible. Screenshot `artifacts/homepage-workbench/pico.png`.
- **Proof.** Write `artifacts/homepage-workbench/notes.md` with feature ID `homepage-workbench` and the entry points used. Keep `aria.txt` from the homepage snapshot.

## Gotchas

- The two build links share similar wording; match the full accessible name (`Follow the build log →` vs `Follow the build →`).
- SO-101 nav has no brand link — only `← Back to home` returns to the homepage.
- External GitHub / Substack links leave the site; do not treat those as proof of Now-strip navigation.
- The homepage strip is text-only. Identity proof is the page title/heading, not build-log media.
