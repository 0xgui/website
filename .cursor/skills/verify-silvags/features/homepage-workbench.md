# Homepage builds

The homepage introduces Gui and lists SO-101 and Pico under Builds. Each card is one link into that robot page. Visitors can open a robot and return home.

## Sub-features

- `home-hero` shows the name `Guilherme Silva` and Binary Paths mention.
- `home-builds` shows the heading `Builds` and the two robot cards.
- `home-so101-card` opens the SO-101 page from `Open SO-101 →` (the whole card is that link).
- `home-pico-card` opens the Pico page from `Open Pico →` (the whole card is that link).
- `home-back` returns from a robot page via `← Back to home` or the Pico brand link.

## How to get to it (user POV)

- Open the site root `/`.
- Click `Open SO-101 →` or anywhere on the SO-101 card.
- Click `Open Pico →` or anywhere on the Pico card.
- From a robot page, choose `← Back to home` (both) or brand `Guilherme Silva` (Pico).

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY.
- Start at `$VERIFY_URL/`.

- **Hero.** Snapshot the homepage. Heading `Guilherme Silva` is visible. Heading `Builds` is visible. Screenshot `artifacts/homepage-workbench/home.png`.
- **Open SO-101.** Click `Open SO-101 →`. URL ends with `/robots/so-101/`. Heading `SO-101 Robotic Arm` is visible. Screenshot `artifacts/homepage-workbench/so-101.png`.
- **Back home.** Click `← Back to home`. URL is `$VERIFY_URL/` (or `/index.html`). Hero heading returns.
- **Open Pico.** Click `Open Pico →`. URL ends with `/robots/pico/`. Heading `Pico` is visible. Screenshot `artifacts/homepage-workbench/pico.png`.
- **Proof.** Write `artifacts/homepage-workbench/notes.md` with feature ID `homepage-workbench` and the entry points used. Keep `aria.txt` from the homepage snapshot.

## Gotchas

- Each card has one link. Match the full accessible name (`Open SO-101 →` vs `Open Pico →`). Clicking the card image uses that same link.
- The homepage has no Now strip and no build-notes teaser under the cards.
- SO-101 nav has no brand link — only `← Back to home` returns to the homepage.
- Media posters may lazy-load; identity proof is the page title/heading, not video playback.
