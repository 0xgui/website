import json
import unittest
from pathlib import Path

from scripts.feeds import posts_from_api
from scripts.mirror_substack import FeedError, apply_mirror, discover, fetch_posts

FIX = Path(__file__).parent / "fixtures"
TINY_WEBP = bytes.fromhex(
    "52494646240000005745425056503820180000003001009d012a0800080002403825a400037000fefb9cc000"
)


def page(title, canonical, body, kind="full"):
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="description" content="Kept">
<meta name="mirror-kind" content="{kind}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="Kept">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="article">
<link rel="canonical" href="{canonical}">
</head><body><main>
<h1>{title}</h1>
<p class="meta"><time datetime="2026-01-01">January 1, 2026</time></p>
<article class="post">{body}</article>
</main></body></html>
"""


def site(root: Path):
    writing = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Writing · Guilherme Silva</title>
<meta name="description" content="Posts">
<meta property="og:title" content="Writing">
<meta property="og:description" content="Posts">
<meta property="og:url" content="https://silvags.com/writing/">
<meta property="og:type" content="website">
<link rel="canonical" href="https://silvags.com/writing/">
<link rel="icon" href="../favicon.svg">
</head><body>
<header><a href="../">Guilherme Silva</a></header>
<main>
<h1>Writing</h1>
<ul class="posts" id="articles"><li>old</li></ul>
</main>
<script>
// Binary Paths via rss.silvags.com (worker.js). Text only, HTTPS only; the snapshot stays on failure.
var stale = 1;
</script>
</body></html>
"""
    home = writing.replace("Writing · Guilherme Silva", "Guilherme Silva").replace('href="../"', 'href="./"')
    home = home.replace('href="../favicon.svg"', 'href="favicon.svg"')
    (root / "writing").mkdir(parents=True)
    (root / "writing" / "index.html").write_text(writing, encoding="utf-8")
    (root / "index.html").write_text(home, encoding="utf-8")
    kept = root / "writing" / "kept-post"
    kept.mkdir()
    (kept / "index.html").write_text(
        page(
            "Kept essay",
            "https://binarypaths.substack.com/p/kept-post",
            "<p>This sentence must survive a bad fetch.</p>",
        ),
        encoding="utf-8",
    )


class MirrorTests(unittest.TestCase):
    def test_fetch_failure_leaves_the_essay(self):
        root = Path(self.id().replace(".", "_"))
        # use a real temp dir
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            before = (root / "writing" / "kept-post" / "index.html").read_bytes()

            def get(url, accept, **_kwargs):
                return 403, "text/html", (FIX / "challenge.html").read_bytes()

            with self.assertRaises(FeedError):
                fetch_posts(get)
            self.assertEqual((root / "writing" / "kept-post" / "index.html").read_bytes(), before)

    def test_missing_slug_is_not_deleted_and_run_is_idempotent(self):
        import tempfile
        payload = json.loads((FIX / "api.json").read_text(encoding="utf-8"))
        posts = posts_from_api(payload)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            before = (root / "writing" / "kept-post" / "index.html").read_text(encoding="utf-8")
            apply_mirror(root, posts, fetch_bytes=lambda url: TINY_WEBP)
            kept = (root / "writing" / "kept-post" / "index.html").read_text(encoding="utf-8")
            self.assertIn("This sentence must survive a bad fetch.", kept)
            self.assertTrue((root / "writing" / "hello-world" / "index.html").exists())
            hello = (root / "writing" / "hello-world" / "index.html").read_text(encoding="utf-8")
            self.assertIn('rel="canonical" href="https://binarypaths.substack.com/p/hello-world"', hello)
            self.assertIn("Originally published on", hello)
            self.assertIn("Binary Paths", hello)
            self.assertNotIn("rss.silvags.com", (root / "index.html").read_text(encoding="utf-8"))
            self.assertIn('href="writing/hello-world/"', (root / "index.html").read_text(encoding="utf-8"))
            self.assertIn('href="kept-post/"', (root / "writing" / "index.html").read_text(encoding="utf-8"))
            snap = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            apply_mirror(root, posts, fetch_bytes=lambda url: TINY_WEBP)
            again = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            self.assertEqual(snap, again)
            self.assertIn("This sentence must survive a bad fetch.", before)

    def test_stub_does_not_replace_a_full_essay(self):
        import tempfile
        paid = posts_from_api(json.loads((FIX / "api-paid.json").read_text(encoding="utf-8")))
        # Pretend the paid slug is the one we already mirrored in full.
        full = paid[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            target = root / "writing" / "paid-essay"
            target.mkdir()
            original = page(
                "Paid essay",
                "https://binarypaths.substack.com/p/paid-essay",
                "<p>" + ("A full public essay. " * 40) + "</p>",
            )
            (target / "index.html").write_text(original, encoding="utf-8")
            apply_mirror(root, [full], fetch_bytes=lambda url: TINY_WEBP)
            saved = (target / "index.html").read_text(encoding="utf-8")
            self.assertIn("A full public essay.", saved)
            self.assertNotIn("This is a preview", saved)

    def test_discover_keeps_saved_posts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            saved = discover(root)
            self.assertIn("kept-post", saved)
            self.assertEqual(saved["kept-post"][0].kind, "full")


if __name__ == "__main__":
    unittest.main()
