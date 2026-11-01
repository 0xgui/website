# Homepage builds

The homepage introduces Gui and lists SO-101 and Pico under "On the bench". Each name is a link into that robot page. The dithered header above the column is the SO-101 poster, and it is itself a link to the SO-101 log.

## Sub-features

- `home-hero` shows the name `Guilherme Silva` and the dithered header.
- `home-bench` shows the heading `On the bench` and links for SO-101 and Pico.
- `home-so101` opens the SO-101 page from the bench link or the header.
- `home-pico` opens the Pico page from the bench link.
- `home-back` returns from a robot page via the brand link `Guilherme Silva`.

## How to get to it (user POV)

- Open `/`.
- Follow `SO-101 robotic arm` or the header image.
- Follow `Pico`.
- From a robot page, choose `Guilherme Silva` in the header to return home.

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY.
- Start at `$VERIFY_URL/`.

- **Hero.** Snapshot the homepage. The name `Guilherme Silva` is visible. Heading `On the bench` is visible. Screenshot `artifacts/homepage-workbench/home.png`.
- **Open SO-101.** Click `SO-101 robotic arm`. URL ends with `/robots/so-101/`. Heading `SO-101 robotic arm` is visible.
- **Back home.** Click `Guilherme Silva`. URL is `$VERIFY_URL/` (or `/index.html`).
- **Open Pico.** Click `Pico`. URL ends with `/robots/pico/`. Heading `Pico` is visible.
- **Proof.** Write `artifacts/homepage-workbench/notes.md` with feature ID `homepage-workbench`.

## Gotchas

- There is no "Open SO-101 →" card and no "← Back to home" link. The bench links and the brand link are the path.
- The header canvas may stay on its poster when WebGL or reduced motion is unavailable. The poster is enough for this proof.
- Latest writing is covered by `writing-feed.md`, not this file.
