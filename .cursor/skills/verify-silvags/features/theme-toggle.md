# Theme toggle

Visitors switch between light and dark appearance with the nav button. The choice persists in `localStorage` under key `theme` and reapplies on later visits to the homepage and robot pages.

## Sub-features

- `theme-toggle-click` flips `:root.dark` on the current page.
- `theme-persist` writes `theme` as `dark` or `light` in `localStorage`.
- `theme-restore` reapplies dark mode on a fresh navigation when `theme` is `dark`.
- `theme-cross-page` the same preference appears on `/robots/so-101/` and `/robots/pico/`.

## How to get to it (user POV)

- Choose the button labelled `Toggle theme` in the sticky site nav (sun/moon icon) on `/`, `/robots/so-101/`, or `/robots/pico/`.

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY at `$VERIFY_URL`.
- Clear prior preference first: CDP `localStorage.removeItem('theme')` then reload, or start with a clean profile.
- Homepage shows light mode (`document.documentElement.classList.contains('dark') === false`).

- **Clear and baseline.** Navigate to `$VERIFY_URL/`. Run CDP `localStorage.removeItem('theme'); location.reload()`. Snapshot shows button `Toggle theme`. Screenshot `artifacts/theme-toggle/before.png` with light background.
- **Toggle to dark.** Click the button with accessible name `Toggle theme`. Observe `html` gains class `dark`. CDP: `document.documentElement.classList.contains('dark')` is `true` and `localStorage.getItem('theme')` is `'dark'`. Screenshot `artifacts/theme-toggle/after-dark.png`.
- **Persist across reload.** Reload the page. Dark class remains; `localStorage.theme` is still `'dark'`.
- **Cross-page.** Navigate to `$VERIFY_URL/robots/pico/`. Dark class is present without clicking again. Navigate to `$VERIFY_URL/robots/so-101/` and confirm the same.
- **Toggle back to light.** Click `Toggle theme` once. `dark` class is gone; `localStorage.theme` is `'light'`. Screenshot `artifacts/theme-toggle/after-light.png`.
- **Proof.** Save an ARIA/snapshot excerpt to `artifacts/theme-toggle/aria.txt` and a short `artifacts/theme-toggle/notes.md` with feature ID `theme-toggle` and the URLs used.

## Gotchas

- Driving the user's everyday browser tab will flip their real theme preference. Clear or restore `localStorage.theme` after the run if you used a shared profile.
- Same host (`127.0.0.1`) shares `localStorage` across ports — a previous verify run can leave `theme=dark`.
- The homepage wraps `localStorage` in try/catch; storage failures must not throw. If storage is blocked, prove only the in-session class toggle and note the unmet persistence precondition.
- Icon swap (sun vs moon) is CSS-driven via `.dark`; assert the `dark` class, not SVG visibility alone.
