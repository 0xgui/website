# Writing feed

The Writing section is the homepage feed. Each post shows a title, date, and excerpt: a static snapshot for first paint / no-JS, then a live refresh from `https://rss.silvags.com` that rewrites `#articles` and updates `#articles-status`.

## Sub-features

- `writing-snapshot` HTML snapshot articles are present before or without a successful feed.
- `writing-live` a successful fetch replaces `#articles` with feed items (HTTPS links only).
- `writing-status` `#articles-status` reflects loading, success, stale, or fallback copy.
- `writing-cache` successful items may land in `localStorage` key `binary-paths-articles-v1`.

## How to get to it (user POV)

- Open `/` and scroll to the `Writing` heading (or land there via page scroll).
- Optionally follow `Subscribe to Binary Paths →` or an article title (external Substack).

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY.
- Start at `$VERIFY_URL/`.
- Network to `https://rss.silvags.com` is available for the live path. If not, prove snapshot + fallback status only and record the unmet precondition.

- **Snapshot present.** Immediately after load (or with JS disabled conceptually via reading source), `#articles` contains at least one link to `binarypaths.substack.com`. Note titles such as house-cleaning or Physical AI posts if still the snapshot.
- **Live refresh.** Wait up to ~10s for the fetch (8s timeout + one retry). Snapshot `#articles`. Article headings are links with `https:` hrefs. `#articles-status` is empty on fresh success, or shows delayed/fallback text otherwise. Screenshot `artifacts/writing-feed/articles.png`.
- **Status role.** Confirm `#articles-status` has `role="status"`.
- **Cache (when live succeeds).** CDP: `JSON.parse(localStorage.getItem('binary-paths-articles-v1')||'null')` has an `items` array with titles and https links.
- **No HTML injection.** Titles/descriptions render as text nodes (no raw markup from the feed visible as executed HTML). Spot-check via snapshot text, not `innerHTML` assignment proofs.
- **Proof.** Save snapshot text to `artifacts/writing-feed/aria.txt` and `artifacts/writing-feed/notes.md` with whether live or snapshot path was proven.

## Gotchas

- The worker is not started by `bin/launch`. Live proof depends on production `rss.silvags.com`.
- First paint already has five snapshot articles (title, date, excerpt, no thumbnails); a failed fetch must still leave useful content — assert that, do not require live success for a partial pass.
- Cache age is seven days; a stale browser cache can show old posts before refresh. Clear `binary-paths-articles-v1` when proving a clean live fetch.
- Do not open Substack in the verify browser as proof of the site feature; stay on `$VERIFY_URL`.
