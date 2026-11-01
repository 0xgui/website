import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "source", "track", "wbr",
}
BANNED = re.compile(
    r"leiria|portugal|https?://(?:www\.)?(?:x\.com|twitter\.com)|https?://t\.co/",
    re.I,
)


class Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style"}:
            self.skip += 1
            return
        if self.skip or tag in VOID:
            return
        self.stack.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1
            return
        if self.skip or tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> with stack {self.stack[-3:]}")
            return
        self.stack.pop()

    def close(self):
        super().close()
        if self.stack:
            self.errors.append(f"unclosed {self.stack}")


def pages():
    found = []
    for path in ROOT.rglob("index.html"):
        rel = path.relative_to(ROOT)
        if any(part in {".git", "tests", "scripts", ".cursor"} for part in rel.parts):
            continue
        found.append(path)
    return found


class HtmlTests(unittest.TestCase):
    def test_pages_are_basically_valid(self):
        for path in pages():
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT).as_posix()
            self.assertTrue(text.lower().startswith("<!doctype html>"), rel)
            self.assertIn('<html lang="en"', text, rel)
            self.assertIn('charset="utf-8"', text, rel)
            self.assertIn("<title>", text, rel)
            self.assertIn('rel="canonical"', text, rel)
            self.assertIn('id="theme-toggle"', text, rel)
            self.assertLessEqual(len(re.findall(r"<h1\b", text)), 1, rel)
            parser = Balance()
            parser.feed(text)
            parser.close()
            self.assertEqual(parser.errors, [], rel)

    def test_published_files_have_no_banned_links_or_place_names(self):
        suffixes = {".html", ".md", ".txt", ".xml"}
        for path in ROOT.rglob("*"):
            rel = path.relative_to(ROOT)
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if any(part in {".git", "tests", "scripts", ".cursor", ".github"} for part in rel.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertIsNone(BANNED.search(text), f"{rel} matches {BANNED.pattern}")

    def test_articles_point_at_substack_and_binary_paths(self):
        folder = ROOT / "writing"
        essays = [path for path in folder.glob("*/index.html")]
        self.assertGreater(len(essays), 0)
        for path in essays:
            text = path.read_text(encoding="utf-8")
            self.assertIn("https://binarypaths.substack.com/p/", text)
            self.assertIn("Originally published on", text)
            self.assertIn("BlogPosting", text)
            self.assertRegex(text, r'<time datetime="\d{4}-\d{2}-\d{2}">')
            self.assertIn('type="text/markdown"', text)


if __name__ == "__main__":
    unittest.main()
