# Color scheme

Visitors choose auto, light, or dark from footer radios. The choice persists in `localStorage` under key `theme` and reapplies on later visits to the homepage and robot pages. Auto follows `prefers-color-scheme` and does not set `.dark` or `.light`. Light sets `.light`. Dark sets `.dark`.

## Sub-features

- `theme-dark` selects the `dark` radio and adds `.dark` on `document.documentElement`.
- `theme-persist` writes `theme` as `dark`, `light`, or `auto` in `localStorage`.
- `theme-restore` reapplies dark mode on a fresh navigation when `theme` is `dark`.
- `theme-cross-page` the same preference appears on `/robots/so-101/` and `/robots/pico/`.
- `theme-light` selects the `light` radio, removes `.dark`, and adds `.light`.

## How to get to it (user POV)

- Scroll to the footer fieldset `Color scheme:` on `/`, `/robots/so-101/`, or `/robots/pico/`.
- Choose the radio labelled `auto`, `light`, or `dark`.

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY at `$VERIFY_URL`.
- Clear prior preference first: CDP `localStorage.removeItem('theme')` then reload, or start with a clean profile.
- Do not assume the cleared page is light. With no saved theme the page is auto and follows the browser's color scheme. Drive the radios explicitly.

- **Clear and baseline.** Navigate to `$VERIFY_URL/`. Run CDP `localStorage.removeItem('theme'); location.reload()`. Snapshot shows radios `auto`, `light`, and `dark` inside `#color-scheme`. `auto` is checked. Screenshot `artifacts/theme-toggle/before.png`.
- **Choose dark.** Click the radio labelled `dark`. Observe `html` gains class `dark` and does not have `light`. CDP: `document.documentElement.classList.contains('dark')` is `true` and `localStorage.getItem('theme')` is `'dark'`. Screenshot `artifacts/theme-toggle/after-dark.png`.
- **Persist across reload.** Reload the page. Dark class remains; `localStorage.theme` is still `'dark'`; the `dark` radio is checked.
- **Cross-page.** Navigate to `$VERIFY_URL/robots/pico/`. Dark class is present without clicking again. Navigate to `$VERIFY_URL/robots/so-101/` and confirm the same.
- **Choose light.** Click the radio labelled `light`. `dark` is gone; `light` is present; `localStorage.theme` is `'light'`. Screenshot `artifacts/theme-toggle/after-light.png`.
- **Proof.** Save an ARIA/snapshot excerpt to `artifacts/theme-toggle/aria.txt` and a short `artifacts/theme-toggle/notes.md` with feature ID `theme-toggle` and the URLs used.

## Gotchas

- Driving the user's everyday browser tab will change their real theme preference. Clear or restore `localStorage.theme` after the run if you used a shared profile.
- Same host (`127.0.0.1`) shares `localStorage` across ports — a previous verify run can leave `theme=dark`.
- The head script and the footer script wrap `localStorage` in try/catch; storage failures must not throw. If storage is blocked, prove only the in-session class change and note the unmet persistence precondition.
- Auto does not add `.dark` even when the operating system is dark. Assert the class only after choosing `dark` or `light`.
- There is no `#theme-toggle` button. The control is `#color-scheme`.
