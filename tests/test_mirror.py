import json
import re
import subprocess
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.feeds import posts_from_api
from scripts.mirror_substack import (
    FeedError,
    _webp_chunks,
    _webp_with_metadata,
    apply_mirror,
    discover,
    fetch_posts,
    outage_is_loud,
    run_mirror,
    essay_cover,
    rewrite_mirrored_essays,
    size_images,
    strip_x_mentions,
    to_webp,
    webp_size,
)

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

    def test_feed_without_ids_keeps_the_saved_id(self):
        posts = posts_from_api(json.loads((FIX / "api.json").read_text(encoding="utf-8")))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            apply_mirror(root, [replace(p, post_id="12345") for p in posts], fetch_bytes=lambda url: TINY_WEBP)
            hello = root / "writing" / "hello-world" / "index.html"
            self.assertIn('<meta name="mirror-id" content="12345">', hello.read_text(encoding="utf-8"))
            apply_mirror(root, [replace(p, post_id="") for p in posts], fetch_bytes=lambda url: TINY_WEBP)
            self.assertIn('<meta name="mirror-id" content="12345">', hello.read_text(encoding="utf-8"))

    def test_stub_does_not_replace_a_full_essay(self):
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

    def test_worker_host_is_not_requested(self):
        seen = []

        def get(url, accept, **_kwargs):
            seen.append(url)
            if "/api/v1/posts" in url:
                return 200, "application/json", (FIX / "api.json").read_bytes()
            raise AssertionError(url)

        posts = fetch_posts(get)
        self.assertEqual(posts[0].slug, "hello-world")
        self.assertFalse(any("rss.silvags.com" in url for url in seen))

    def test_reindex_drops_only_the_removed_essay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            from scripts.mirror_substack import refresh_indexes
            refresh_indexes(root)
            self.assertIn("kept-post/", (root / "writing" / "index.html").read_text(encoding="utf-8"))
            import shutil
            shutil.rmtree(root / "writing" / "kept-post")
            refresh_indexes(root)
            text = (root / "writing" / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("kept-post", text)
            self.assertTrue((root / "index.html").exists())

    def test_discover_keeps_saved_posts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            saved = discover(root)
            self.assertIn("kept-post", saved)
            self.assertEqual(saved["kept-post"][0].kind, "full")


NOW = datetime(2026, 11, 1, 20, 0, tzinfo=timezone.utc)
DEV = "https://rss-worker.example.workers.dev/raw.xml"
HOST = "https://rss.silvags.com/raw.xml"
SNAPSHOTS = (("workers-dev", DEV), ("rss-host", HOST))


def challenge():
    return 403, "text/html", (FIX / "challenge.html").read_bytes()


def ok_json():
    return 200, "application/json", (FIX / "api.json").read_bytes()


def ok_rss():
    return 200, "application/rss+xml", (FIX / "normal.xml").read_bytes()


def stamp(root: Path, when: datetime):
    path = root / "writing" / "last-good.txt"
    path.write_text(when.strftime("%Y-%m-%dT%H:%M:%SZ") + "\n", encoding="utf-8")


class FetchPathTests(unittest.TestCase):
    def _get(self, mapping):
        seen = []

        def get(url, accept, **_kwargs):
            seen.append(url)
            for needle, result in mapping:
                if needle in url:
                    return result() if callable(result) else result
            raise AssertionError(url)

        return get, seen

    def test_api_stops_before_later_sources(self):
        get, seen = self._get((("/api/v1/posts", ok_json()),))
        posts = fetch_posts(get, snapshots=SNAPSHOTS)
        self.assertEqual(posts[0].slug, "hello-world")
        self.assertEqual(seen, ["https://binarypaths.substack.com/api/v1/posts?limit=20"])

    def test_archive_is_second(self):
        get, seen = self._get((
            ("/api/v1/posts", challenge()),
            ("/api/v1/archive", ok_json()),
        ))
        posts = fetch_posts(get, snapshots=SNAPSHOTS)
        self.assertEqual(posts[0].slug, "hello-world")
        self.assertTrue(any("/archive" in url for url in seen))
        self.assertFalse(any(url.endswith("/feed") or "raw.xml" in url for url in seen))

    def test_rss_is_third(self):
        seen = []

        def get(url, accept, **_kwargs):
            seen.append(url)
            if url.endswith("/feed"):
                return ok_rss()
            if "binarypaths.substack.com" in url:
                return challenge()
            raise AssertionError(url)

        posts = fetch_posts(get, snapshots=SNAPSHOTS)
        self.assertEqual(posts[0].slug, "hello-world")
        self.assertTrue(any(url.endswith("/feed") for url in seen))
        self.assertFalse(any("raw.xml" in url for url in seen))

    def test_workers_dev_snapshot_is_before_the_custom_domain(self):
        def direct(url, accept, **_kwargs):
            if "workers.dev" in url:
                return ok_rss()
            if "rss.silvags.com" in url:
                raise AssertionError(url)
            return challenge()

        posts = fetch_posts(direct, snapshots=SNAPSHOTS)
        self.assertEqual(posts[0].slug, "hello-world")
        self.assertEqual(posts[0].body_html, "<p>The full essay.</p><p><img src=\"https://cdn.example/pic.jpg\" alt=\"A picture\"></p>")

    def test_custom_domain_snapshot_is_used_when_workers_dev_is_a_challenge(self):
        seen = []

        def get(url, accept, **_kwargs):
            seen.append(url)
            if "workers.dev" in url:
                return 200, "text/html", (FIX / "challenge.html").read_bytes()
            if "rss.silvags.com" in url:
                xml = (FIX / "normal.xml").read_bytes()
                stamped = xml.replace(
                    b"?>",
                    b"?><!-- fetchedAt: 2026-11-01T18:27:00.000Z -->",
                    1,
                )
                return 200, "application/rss+xml", stamped
            return challenge()

        posts = fetch_posts(get, snapshots=SNAPSHOTS)
        self.assertEqual(posts[0].slug, "hello-world")
        self.assertLess(seen.index(DEV), seen.index(HOST))

    def test_malformed_snapshot_falls_through(self):
        def get(url, accept, **_kwargs):
            if "workers.dev" in url:
                return 200, "application/rss+xml", b"<rss><channel></channel>"
            if "rss.silvags.com" in url:
                return ok_rss()
            return challenge()

        posts = fetch_posts(get, snapshots=SNAPSHOTS)
        self.assertEqual(posts[0].slug, "hello-world")

    def test_empty_snapshot_falls_through(self):
        def get(url, accept, **_kwargs):
            if "workers.dev" in url:
                return 200, "application/rss+xml", (FIX / "empty.xml").read_bytes()
            if "rss.silvags.com" in url:
                return ok_rss()
            return challenge()

        posts = fetch_posts(get, snapshots=SNAPSHOTS)
        self.assertEqual(posts[0].slug, "hello-world")

    def test_every_path_failing_raises(self):
        def get(url, accept, **_kwargs):
            return challenge()

        with self.assertRaises(FeedError) as caught:
            fetch_posts(get, snapshots=SNAPSHOTS)
        message = str(caught.exception)
        for name in ("api:", "archive:", "rss:", "workers-dev:", "rss-host:"):
            self.assertIn(name, message)

    def test_committed_workers_dev_is_first(self):
        import os
        from unittest.mock import patch
        from scripts.mirror_substack import DEFAULT_WORKERS_DEV, default_snapshot_urls
        self.assertTrue(DEFAULT_WORKERS_DEV.startswith("https://rss-worker."))
        self.assertTrue(DEFAULT_WORKERS_DEV.endswith(".workers.dev/raw.xml"))
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WORKERS_DEV_SNAPSHOT", None)
            urls = default_snapshot_urls()
        self.assertEqual(urls[0], ("workers-dev", DEFAULT_WORKERS_DEV))
        self.assertEqual(urls[1][0], "rss-host")

    def test_snapshot_order_prefers_workers_dev(self):
        import os
        from unittest.mock import patch
        from scripts.mirror_substack import default_snapshot_urls
        with patch.dict(os.environ, {"WORKERS_DEV_SNAPSHOT": "https://rss-worker.example.workers.dev"}):
            urls = default_snapshot_urls()
        self.assertEqual([name for name, _url in urls], ["workers-dev", "rss-host"])
        self.assertTrue(urls[0][1].endswith("/raw.xml"))
        self.assertTrue(urls[1][1].endswith("/raw.xml"))


class StalenessTests(unittest.TestCase):
    def _failed(self, root: Path, age: timedelta | None):
        site(root)
        essay = (root / "writing" / "kept-post" / "index.html").read_bytes()
        if age is None:
            self.assertFalse((root / "writing" / "last-good.txt").exists())
        else:
            stamp(root, NOW - age)
        before = essay

        def get(url, accept, **_kwargs):
            return challenge()

        code = run_mirror(root, get, now=NOW, snapshots=SNAPSHOTS)
        self.assertEqual((root / "writing" / "kept-post" / "index.html").read_bytes(), before)
        return code

    def test_recent_good_data_stays_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self._failed(root, timedelta(hours=47)), 0)
            self.assertFalse(outage_is_loud(root, NOW))
            self.assertEqual((root / "writing" / "last-good.txt").read_text(encoding="utf-8").strip(), "2026-10-30T21:00:00Z")

    def test_exactly_48h_is_loud_and_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self._failed(root, timedelta(hours=48)), 1)
            self.assertTrue(outage_is_loud(root, NOW))

    def test_older_than_48h_is_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self._failed(root, timedelta(hours=49)), 1)

    def test_missing_stamp_is_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self._failed(root, None), 1)
            self.assertFalse((root / "writing" / "last-good.txt").exists())

    def test_success_does_not_rewrite_a_fresh_stamp_or_drop_an_essay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            stamp(root, NOW - timedelta(hours=1))
            before = (root / "writing" / "kept-post" / "index.html").read_text(encoding="utf-8")

            def get(url, accept, **_kwargs):
                if "/api/v1/posts" in url:
                    return ok_json()
                raise AssertionError(url)

            self.assertEqual(run_mirror(root, get, now=NOW, snapshots=SNAPSHOTS), 0)
            self.assertTrue((root / "writing" / "hello-world" / "index.html").exists())
            self.assertIn("This sentence must survive a bad fetch.", (root / "writing" / "kept-post" / "index.html").read_text(encoding="utf-8"))
            self.assertIn("This sentence must survive a bad fetch.", before)
            self.assertEqual((root / "writing" / "last-good.txt").read_text(encoding="utf-8").strip(), "2026-11-01T19:00:00Z")

    def test_success_rewrites_a_stamp_older_than_24h(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            stamp(root, NOW - timedelta(hours=24))

            def get(url, accept, **_kwargs):
                if "/api/v1/posts" in url:
                    return ok_json()
                raise AssertionError(url)

            self.assertEqual(run_mirror(root, get, now=NOW, snapshots=SNAPSHOTS), 0)
            self.assertTrue((root / "writing" / "hello-world" / "index.html").exists())
            self.assertEqual((root / "writing" / "last-good.txt").read_text(encoding="utf-8").strip(), "2026-11-01T20:00:00Z")
            self.assertIn("This sentence must survive a bad fetch.", (root / "writing" / "kept-post" / "index.html").read_text(encoding="utf-8"))


class ImageSizeTests(unittest.TestCase):
    def make_webp(self, folder, size):
        path = Path(folder) / "source.webp"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            f"testsrc2=size={size}", "-frames:v", "1", "-c:v", "libwebp", "-lossless", "1", str(path),
        ], check=True)
        return path.read_bytes()

    def test_webp_size_reads_vp8_header(self):
        self.assertEqual(webp_size(TINY_WEBP), (8, 8))
        self.assertIsNone(webp_size(b"not an image"))

    def test_committed_essay_images_all_parse(self):
        for path in (Path(__file__).parent.parent / "writing").glob("*/images/*.webp"):
            size = webp_size(path.read_bytes())
            self.assertIsNotNone(size, path)
            self.assertTrue(all(0 < n <= 16383 for n in size), path)

    def test_size_images_adds_dimensions_and_lazy_after_first(self):
        body = '<figure><img src="images/01.webp" alt="A"></figure><figure><img src="images/02.webp" alt=""></figure>'
        out = size_images(body, {"images/01.webp": TINY_WEBP, "images/02.webp": TINY_WEBP})
        self.assertIn('<img src="images/01.webp" alt="A" width="8" height="8" decoding="async">', out)
        self.assertIn('<img src="images/02.webp" alt="" width="8" height="8" loading="lazy" decoding="async">', out)

    def test_size_images_without_bytes_keeps_the_image(self):
        out = size_images('<img src="images/09.webp" alt="">', {})
        self.assertEqual(out, '<img src="images/09.webp" alt="" decoding="async">')

    def test_webp_cleanup_removes_extra_exif_and_keeps_icc_and_orientation(self):
        profile = b"embedded profile"
        with tempfile.TemporaryDirectory() as tmp:
            oriented = _webp_with_metadata(self.make_webp(tmp, "100x60"), profile, 6)
        chunks = bytearray(b"WEBP")
        for tag, payload in _webp_chunks(oriented):
            if tag == b"EXIF":
                payload += b"unused device metadata"
            chunks.extend(tag + len(payload).to_bytes(4, "little") + payload + b"\0" * (len(payload) % 2))
        source = b"RIFF" + len(chunks).to_bytes(4, "little") + chunks
        cleaned = to_webp(source)
        self.assertEqual(webp_size(cleaned), (60, 100))
        metadata = dict(_webp_chunks(cleaned))
        self.assertEqual(metadata[b"ICCP"], profile)
        self.assertNotIn(b"EXIF", metadata)

        invalid = source.replace(b"II*\0", b"bad!")
        self.assertNotIn(b"EXIF", dict(_webp_chunks(to_webp(invalid))))

    def test_mirror_generates_narrower_smaller_images_and_reuses_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            original = self.make_webp(root, "1440x820")
            post = posts_from_api(json.loads((FIX / "api.json").read_text()))[0]
            post = replace(post, body_html='<p>Hello</p><img src="https://example.com/wide.webp" alt="Sample">')
            apply_mirror(root, [post], fetch_bytes=lambda _: original)
            essay = root / "writing" / post.slug
            html = (essay / "index.html").read_text()
            self.assertIn('srcset="images/01-800w.webp 800w, images/01-1200w.webp 1200w, images/01.webp 1440w"', html)
            self.assertIn('sizes="(max-width: 600px) 100vw, 544px"', html)
            for width in (800, 1200):
                variant = (essay / "images" / f"01-{width}w.webp").read_bytes()
                self.assertEqual(webp_size(variant)[0], width)
                self.assertLess(len(variant), len(original))
            if "<!-- agent:crumbs -->" not in html:
                html = html.replace(
                    "<!-- agent:social -->",
                    "<!-- agent:crumbs -->\nbreadcrumbs\n<!-- /agent:crumbs -->\n<!-- agent:social -->",
                )
                (essay / "index.html").write_text(html)
            self.assertEqual(apply_mirror(root, [post], fetch_bytes=lambda _: original), [])
            self.assertEqual((essay / "index.html").read_text(), html)


class ArticleMetadataTests(unittest.TestCase):
    def test_essay_metadata_uses_cover_dimensions_alt_and_canonical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            post = posts_from_api(json.loads((FIX / "api.json").read_text()))[0]
            post = replace(post, body_html='<p>Hello</p><img src="https://example.com/small.webp" alt="A &amp; B">')
            apply_mirror(root, [post], fetch_bytes=lambda _: TINY_WEBP)
            html = (root / "writing" / post.slug / "index.html").read_text()
            for key, value in {
                "og:site_name": "Guilherme Silva",
                "og:locale": "en_GB",
                "og:image": f"https://silvags.com/writing/{post.slug}/images/01.webp",
                "og:image:width": "8",
                "og:image:height": "8",
                "og:image:type": "image/webp",
                "og:image:alt": "A &amp; B",
            }.items():
                self.assertIn(f'<meta property="{key}" content="{value}">', html)
            self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
            self.assertIn('<meta name="twitter:image:alt" content="A &amp; B">', html)
            self.assertIn(f'<link rel="canonical" href="{post.canonical}">', html)
            data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)[1])
            self.assertEqual(data["mainEntityOfPage"], post.canonical)
            self.assertEqual(data["image"], f"https://silvags.com/writing/{post.slug}/images/01.webp")

    def test_mirror_prefers_a_local_og_cover_and_keeps_it_on_rerender(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            post = posts_from_api(json.loads((FIX / "api.json").read_text()))[0]
            post = replace(post, body_html='<p>Hello</p><img src="https://example.com/small.webp" alt="">')
            og = root / "og"
            og.mkdir()
            source = og / "source.webp"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                "testsrc2=size=1200x630", "-frames:v", "1", "-c:v", "libwebp", str(source),
            ], check=True)
            cover = source.read_bytes()
            custom = og / f"essay-{post.slug}-v3.webp"
            custom.write_bytes(cover)
            essay = root / "writing" / post.slug / "index.html"
            apply_mirror(root, [post], fetch_bytes=lambda _: TINY_WEBP)
            self.assertIn(f'og:image" content="https://silvags.com/og/{custom.name}"', essay.read_text())
            preferred = og / f"essay-{post.slug}-v1.webp"
            preferred.write_bytes(cover)
            rerender = replace(post, title="Updated essay")
            apply_mirror(root, [rerender], fetch_bytes=lambda _: TINY_WEBP)
            html = essay.read_text()
            self.assertIn(f'og:image" content="https://silvags.com/og/{preferred.name}"', html)
            self.assertIn('og:image:width" content="1200"', html)
            self.assertIn('og:image:height" content="630"', html)
            self.assertIn('<meta name="twitter:image:alt" content="Updated essay">', html)
            self.assertEqual(preferred.read_bytes(), cover)


class CoverTests(unittest.TestCase):
    def test_cover_is_first_local_image(self):
        body = '<p>x</p><figure><img src="images/01.webp" alt=""></figure><img src="images/02.webp" alt="">'
        self.assertEqual(essay_cover(body, "https://silvags.com/writing/a/"), "https://silvags.com/writing/a/images/01.webp")
        self.assertIsNone(essay_cover("<p>no images</p>", "https://silvags.com/writing/a/"))

    def test_committed_essays_preview_their_own_cover(self):
        for path in (Path(__file__).parent.parent / "writing").glob("*/index.html"):
            html = path.read_text(encoding="utf-8")
            if '<img src="images/' in html:
                self.assertIn(f'og:image" content="https://silvags.com/writing/{path.parent.name}/images/', html, path)



class StripXMentionsTests(unittest.TestCase):
    def test_signoff_or_x_becomes_linkedin_only(self):
        src = "<p>You can find me on LinkedIn or X.</p>"
        self.assertEqual(strip_x_mentions(src), "<p>You can find me on LinkedIn.</p>")

    def test_signoff_variants_and_html_link(self):
        cases = [
            (
                'You can find me on <a href="https://www.linkedin.com/in/silva-gs/">LinkedIn</a> or X.',
                'You can find me on <a href="https://www.linkedin.com/in/silva-gs/">LinkedIn</a>.',
            ),
            (
                "You can find me on LinkedIn or on X.",
                "You can find me on LinkedIn.",
            ),
            (
                "You can find me on the professional network (LinkedIn) or the digital playground (X).",
                "You can find me on the professional network (LinkedIn).",
            ),
            (
                "You can find me on the professional network (LinkedIn) or the digital playground (Twitter).",
                "You can find me on the professional network (LinkedIn).",
            ),
            (
                'You can find me on <a href="https://www.linkedin.com/in/gssilva-link/">LinkedIn</a> or the digital playground (X).',
                'You can find me on <a href="https://www.linkedin.com/in/gssilva-link/">LinkedIn</a>.',
            ),
            (
                "You can find me on LinkedIn or <em>X</em>.",
                "You can find me on LinkedIn.",
            ),
            (
                "You can find me on LinkedIn or\nX.",
                "You can find me on LinkedIn.",
            ),
            (
                "You can find me on LinkedIn or&nbsp;X.",
                "You can find me on LinkedIn.",
            ),
        ]
        for src, want in cases:
            with self.subTest(src=src):
                self.assertEqual(strip_x_mentions(f"<p>{src}</p>"), f"<p>{want}</p>")

    def test_idempotent_and_preserves_unrelated_text(self):
        src = "<p>I’m all ears! You can find me on LinkedIn or X.</p><p>Thanks for reading.</p>"
        once = strip_x_mentions(src)
        self.assertEqual(once, "<p>I’m all ears! You can find me on LinkedIn.</p><p>Thanks for reading.</p>")
        self.assertEqual(strip_x_mentions(once), once)

    def test_does_not_touch_os_x_or_10x_or_catch_x(self):
        src = "<p>OS X and 10x engineers, then catch(x) in a script.</p>"
        self.assertEqual(strip_x_mentions(src), src)

    def test_drops_a_twitter_sentence_and_keeps_neighbours(self):
        src = (
            "<p>Follow people in your areas of interest on social media. "
            "Twitter is gold for quick tech updates and discussions. "
            "Here are some of my go to follows:</p>"
        )
        out = strip_x_mentions(src)
        self.assertEqual(
            out,
            "<p>Follow people in your areas of interest on social media. "
            "Here are some of my go to follows:</p>",
        )
        self.assertNotIn("Twitter", out)
        self.assertNotIn("twitter", out.lower())

    def test_twitter_sentences_leave_image_attributes_and_link_tags_intact(self):
        src = (
            '<p>Keep this. Read <a href="https://example.com/thread">this Twitter thread</a> tomorrow. '
            'Keep <em>this too</em>.</p>'
            '<figure><img src="images/01.webp" alt="A Twitter post or Twitter"></figure>'
            '<p><a href="https://example.com/Twitter">Keep the unrelated link.</a></p>'
        )
        self.assertEqual(
            strip_x_mentions(src),
            '<p>Keep this.<a href="https://example.com/thread"></a> Keep <em>this too</em>.</p>'
            '<figure><img src="images/01.webp" alt="A Twitter post or Twitter"></figure>'
            '<p><a href="https://example.com/Twitter">Keep the unrelated link.</a></p>',
        )

    def test_rewrite_mirrored_essays_updates_the_article_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            target = root / "writing" / "kept-post" / "index.html"
            html = target.read_text(encoding="utf-8")
            html = html.replace(
                "<p>This sentence must survive a bad fetch.</p>",
                "<p>You can find me on LinkedIn or X.</p>",
            )
            target.write_text(html, encoding="utf-8")
            # A decoy in the shell must not be rewritten.
            shell = root / "writing" / "index.html"
            before_shell = shell.read_text(encoding="utf-8")
            changed = rewrite_mirrored_essays(root)
            self.assertEqual(changed, ["writing/kept-post/index.html"])
            updated = target.read_text(encoding="utf-8")
            self.assertIn("You can find me on LinkedIn.</p>", updated)
            self.assertNotIn("or X", updated)
            self.assertEqual(shell.read_text(encoding="utf-8"), before_shell)
            self.assertEqual(rewrite_mirrored_essays(root), [])

    def test_apply_mirror_strips_the_signoff(self):
        posts = posts_from_api(json.loads((FIX / "api.json").read_text(encoding="utf-8")))
        posts = [
            replace(
                posts[0],
                body_html=(
                    "<p>Hello.</p>"
                    "<p>You can find me on LinkedIn or X.</p>"
                ),
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            apply_mirror(root, posts, fetch_bytes=lambda url: TINY_WEBP)
            html = (root / "writing" / "hello-world" / "index.html").read_text(encoding="utf-8")
            self.assertIn("You can find me on LinkedIn.", html)
            self.assertNotRegex(html, r"or X")


if __name__ == "__main__":
    unittest.main()
