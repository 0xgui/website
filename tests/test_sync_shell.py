import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts.sync_shell import check_pages, main as sync_main, site_pages


def _make_page(title: str, style: str, scripts: list[str], extra_ld: str = "", body: str = "") -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en" class="dark">\n'
        "<head>\n"
        f"<title>{title}</title>\n"
        f'<meta name="description" content="{title} desc">\n'
        f"<script>{scripts[0]}</script>\n"
        f"<style>{style}</style>\n"
        f"{extra_ld}"
        "</head>\n"
        "<body>\n"
        f'<div class="col"><main><h1>{title}</h1>{body}</main><footer>ok</footer></div>\n'
        f'<script type="module">{scripts[1]}</script>\n'
        f'<script type="module">{scripts[2]}</script>\n'
        f"<script>{scripts[3]}</script>\n"
        "</body>\n"
        "</html>\n"
    )


class SyncShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.style = "body{color:var(--ink)}"
        self.scripts = ["boot();", "header();", "viewer();", "nav();"]
        (self.root / "index.html").write_text(
            _make_page("Home", self.style, self.scripts),
            encoding="utf-8",
        )
        (self.root / "about").mkdir()
        (self.root / "about" / "index.html").write_text(
            _make_page(
                "About",
                self.style,
                self.scripts,
                extra_ld='<script type="application/ld+json">{"@type":"Person"}</script>\n',
                body="<p>About body</p>",
            ),
            encoding="utf-8",
        )
        (self.root / "404.html").write_text(
            _make_page("Not found", self.style, self.scripts, body="<p>Missing</p>"),
            encoding="utf-8",
        )
        slides_dir = self.root / "talks" / "bottleneck-moved"
        slides_dir.mkdir(parents=True)
        (slides_dir / "slides.html").write_text(
            "<!doctype html><html><head><style>slides{}</style></head><body>slides</body></html>\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_check_passes_when_in_sync_and_excludes_slides(self):
        rels = [p.as_posix() for p in site_pages(self.root)]
        self.assertEqual(rels, ["404.html", "index.html", "about/index.html"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = sync_main(["--check", "--root", str(self.root)])
        self.assertEqual(code, 0)
        self.assertIn("in sync", buf.getvalue())

    def test_check_detects_drift_and_apply_fixes_preserving_page_content(self):
        drifted_about = _make_page(
            "About",
            "body{color:red}",
            ["old_boot();", self.scripts[1], self.scripts[2], "old_nav();"],
            extra_ld='<script type="application/ld+json">{"@type":"Person"}</script>\n',
            body="<p>Keep this copy</p>",
        )
        (self.root / "about" / "index.html").write_text(drifted_about, encoding="utf-8")
        slides_before = (self.root / "talks" / "bottleneck-moved" / "slides.html").read_text(encoding="utf-8")

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = sync_main(["--check", "--root", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("about/index.html", buf.getvalue())
        self.assertIn("style", buf.getvalue())
        self.assertIn("script[0]", buf.getvalue())
        self.assertIn("script[3]", buf.getvalue())

        apply_buf = io.StringIO()
        with redirect_stdout(apply_buf):
            apply_code = sync_main(["--apply", "--root", str(self.root)])
        self.assertEqual(apply_code, 0)
        self.assertIn("about/index.html", apply_buf.getvalue())

        self.assertEqual(check_pages(self.root), [])
        updated_about = (self.root / "about" / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>About</title>", updated_about)
        self.assertIn('<script type="application/ld+json">{"@type":"Person"}</script>', updated_about)
        self.assertIn("<p>Keep this copy</p>", updated_about)
        self.assertEqual(
            (self.root / "talks" / "bottleneck-moved" / "slides.html").read_text(encoding="utf-8"),
            slides_before,
        )


if __name__ == "__main__":
    unittest.main()
