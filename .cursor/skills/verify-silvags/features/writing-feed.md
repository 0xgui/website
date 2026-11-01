# Writing

Writing is a static list of essays mirrored from Binary Paths. Each title links to `/writing/<slug>/` on this site. The page still links to Binary Paths for the original and for subscribing.

## Sub-features

- `writing-local` `#articles` links to local essay pages, with a date and a short description.
- `writing-essay` an essay page shows the title, the publish date, the full text, and "Originally published on Binary Paths".
- `writing-canonical` the essay's canonical URL is the Binary Paths post.
- `writing-subscribe` the Writing page and the homepage keep a Binary Paths subscribe link.

## How to get to it (user POV)

- Open `/` and read `Latest writing`, or open `/writing/` from the nav.
- Open an essay title. It stays on this site.
- Use the Binary Paths link when you want the original or the subscribe page.

## Driving it with Cursor browser

Preconditions:

- `bin/doctor` is HEALTHY.
- Start at `$VERIFY_URL/`.

- **Homepage list.** `#articles` has at least one link whose href contains `/writing/` and does not point at `binarypaths.substack.com`. The subscribe link to `https://binarypaths.substack.com` is still on the page. Screenshot `artifacts/writing-feed/home-list.png`.
- **Writing index.** Open `Writing` in the nav. URL ends with `/writing/`. `#articles` lists the same kind of local links. `#articles-status` is present and mentions Binary Paths. Screenshot `artifacts/writing-feed/index.png`.
- **Essay.** Open the first title. The heading matches the link text. A time element shows the date. The words `Originally published on Binary Paths` are visible, and that link goes to `binarypaths.substack.com`. Screenshot `artifacts/writing-feed/essay.png`.
- **No live rewrite.** Wait a couple of seconds. `#articles` hrefs are still local. There is no request required to `rss.silvags.com`.
- **Proof.** Save `artifacts/writing-feed/aria.txt` and `artifacts/writing-feed/notes.md` with feature ID `writing-feed`.

## Gotchas

- The Python static server does not apply `Accept: text/markdown`. Fetch `index.md` directly if you need the twin. Negotiation is the Pages function.
- Essay canonical links leave the site. Proof is the href on the essay page, not a visit to Substack.
- The old `binary-paths-articles-v1` localStorage key is unused. Do not require it.
- Homepage shows four essays. The Writing page shows every mirrored essay.
