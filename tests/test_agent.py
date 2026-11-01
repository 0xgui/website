import unittest
from pathlib import Path

from scripts.build_agent import CONTENT_SIGNAL, diff

ROOT = Path(__file__).resolve().parents[1]


class AgentFileTests(unittest.TestCase):
    def test_generated_files_match_the_html(self):
        changed = diff(ROOT)
        self.assertEqual(changed, [], "run python3 scripts/build_agent.py\n" + "\n".join(changed))

    def test_content_signal_is_shared(self):
        robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
        headers = (ROOT / "_headers").read_text(encoding="utf-8")
        middleware = (ROOT / "functions" / "_middleware.js").read_text(encoding="utf-8")
        self.assertIn(f"Content-Signal: {CONTENT_SIGNAL}", robots)
        self.assertIn(f"Content-Signal: {CONTENT_SIGNAL}", headers)
        self.assertIn(CONTENT_SIGNAL, middleware)
        self.assertIn("search=yes", CONTENT_SIGNAL)
        self.assertIn("ai-input=yes", CONTENT_SIGNAL)
        self.assertIn("ai-train=no", CONTENT_SIGNAL)

    def test_every_page_has_a_markdown_twin_and_llms_links_it(self):
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        self.assertTrue(llms.startswith("# Guilherme Silva\n"))
        self.assertIn("> ", llms)
        self.assertIn("## Site\n", llms)
        full = (ROOT / "llms-full.txt").read_text(encoding="utf-8")
        for html in ROOT.rglob("index.html"):
            rel = html.relative_to(ROOT)
            if any(part in {".git", "tests", "scripts"} for part in rel.parts):
                continue
            twin = html.with_name("index.md")
            self.assertTrue(twin.exists(), str(twin))
            page = html.read_text(encoding="utf-8")
            self.assertIn('rel="alternate" type="text/markdown"', page)
            self.assertIn('rel="describedby"', page)
            self.assertIn(twin.name, page)

    def test_person_sameas_is_only_github_and_linkedin(self):
        import json
        import re
        for rel in ("index.html", "about/index.html"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            match = re.search(
                r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
                text,
                re.S,
            )
            self.assertIsNotNone(match, rel)
            data = json.loads(match.group(1))
            self.assertEqual(data["@type"], "Person")
            self.assertEqual(data["sameAs"], [
                "https://github.com/0xgui",
                "https://www.linkedin.com/in/silva-gs",
            ])

    def test_robot_pages_are_creative_work(self):
        import json
        import re
        for rel in ("robots/so-101/index.html", "robots/pico/index.html"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            match = re.search(
                r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
                text,
                re.S,
            )
            data = json.loads(match.group(1))
            self.assertEqual(data["@type"], "CreativeWork")

    def test_llms_full_contains_page_text(self):
        full = (ROOT / "llms-full.txt").read_text(encoding="utf-8")
        self.assertIn("SO-101", full)
        self.assertIn("Pico", full)


if __name__ == "__main__":
    unittest.main()
