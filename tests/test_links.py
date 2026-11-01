import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
ATTRS = re.compile(r'''(?:href|src|data-glb)\s*=\s*["']([^"']+)["']''', re.I)
URLS = re.compile(r'''url\(([^)]+)\)''')
MD_LINKS = re.compile(r'''\[[^\]]*\]\(([^)\s]+)\)''')


def pages():
    found = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if rel.as_posix() in {"AGENTS.md", "README.md"}:
            continue
        if any(part in {".git", "tests", "scripts", ".cursor", ".github", "functions"} for part in rel.parts):
            continue
        if path.suffix in {".html", ".md", ".txt", ".xml"}:
            found.append(path)
    return found


def local_target(page: Path, href: str):
    href = href.strip().strip("\"'")
    if not href or href.startswith(("#", "mailto:", "javascript:", "data:")):
        return None
    if href.startswith("//"):
        return "external"
    parsed = urlparse(href)
    if parsed.scheme in {"http", "https"}:
        if parsed.netloc != "silvags.com":
            return "external"
        path = unquote(parsed.path)
    else:
        path = unquote(href.split("#", 1)[0].split("?", 1)[0])
        if path.startswith("/"):
            path = path
        else:
            path = (page.parent / path).resolve().relative_to(ROOT.resolve()).as_posix()
            if href.endswith("/"):
                path += "/"
    if path.startswith("/"):
        path = path[1:]
    if path in {"", "."}:
        return ROOT / "index.html"
    target = ROOT / path
    if path.endswith("/") or (target.is_dir()):
        return target / "index.html"
    if not target.suffix and (target / "index.html").exists():
        return target / "index.html"
    return target


class LinkTests(unittest.TestCase):
    def test_internal_links_and_assets_resolve(self):
        missing = []
        for page in pages():
            text = page.read_text(encoding="utf-8", errors="replace")
            refs = ATTRS.findall(text) + [item.strip("\"'") for item in URLS.findall(text)]
            if page.suffix in {".md", ".txt"}:
                refs += MD_LINKS.findall(text)
            for href in refs:
                if href.startswith("javascript:"):
                    missing.append(f"{page}: javascript link {href}")
                    continue
                target = local_target(page, href)
                if target in {None, "external"}:
                    continue
                if isinstance(target, Path) and not target.exists():
                    missing.append(f"{page.relative_to(ROOT)} -> {href}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
