import unittest
from pathlib import Path

from scripts.gate_paths import load_config, mirror_pr_body, tier_for_paths, verdict

ROOT = Path(__file__).resolve().parents[1]


class GateTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / ".review-gate.yml")

    def test_config_matches_the_site_policy(self):
        self.assertEqual(self.config["default_tier"], "low")
        self.assertEqual(self.config["routing"]["approvals"], {"low": 0, "medium": 0, "high": 0})
        self.assertFalse(self.config["routing"]["high_requires_codeowners"])
        high = set(self.config["tiers"]["high"])
        for pattern in (
            ".github/workflows/**",
            "_headers",
            "_redirects",
            "_routes.json",
            "functions/**",
            "worker.js",
            "wrangler.toml",
            ".review-gate.yml",
            "scripts/mirror_substack.py",
        ):
            self.assertIn(pattern, high)

    def test_mirror_diff_passes_and_may_auto_merge(self):
        paths = [
            "writing/hello-world/index.html",
            "writing/hello-world/index.md",
            "writing/hello-world/images/01.webp",
            "writing/hello-world/media.json",
            "writing/index.html",
            "writing/index.md",
            "index.html",
            "index.md",
            "llms.txt",
            "llms-full.txt",
            "sitemap.xml",
            "feed.xml",
            "robots.txt",
        ]
        result = verdict(paths, mirror_pr_body("Mirrored one essay."), ci_green=True, config=self.config)
        self.assertEqual(tier_for_paths(paths, self.config), "low")
        self.assertEqual(result["gate"], "pass")
        self.assertEqual(result["missing"], [])
        self.assertTrue(result["auto_merge"])
        self.assertEqual(result["required_approvals"], 0)

    def test_workflow_diff_does_not_auto_merge(self):
        paths = [
            ".github/workflows/mirror-substack.yml",
            "writing/hello-world/index.html",
        ]
        result = verdict(paths, mirror_pr_body("Touched a workflow."), ci_green=True, config=self.config)
        self.assertEqual(result["tier"], "high")
        self.assertEqual(result["gate"], "pass")
        self.assertFalse(result["auto_merge"])

    def test_mirror_script_itself_is_high(self):
        self.assertEqual(tier_for_paths(["scripts/mirror_substack.py"], self.config), "high")
        self.assertEqual(tier_for_paths(["scripts/build_agent.py"], self.config), "medium")

    def test_empty_testing_section_blocks(self):
        body = "## Testing\n\nTODO\n\n## Risk\n\nLow.\n\n## How to revert\n\nRevert the commit.\n"
        result = verdict(["writing/a/index.html"], body, ci_green=True, config=self.config)
        self.assertEqual(result["gate"], "blocked")
        self.assertIn("section:Testing", result["missing"])
        self.assertFalse(result["auto_merge"])


if __name__ == "__main__":
    unittest.main()
