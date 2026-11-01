"""Workflows that publish with GITHUB_TOKEN must create their own checks.

GitHub does not start pull_request or pull_request_target runs for events made
with GITHUB_TOKEN. A workflow that pushes or opens a PR with that token has to
dispatch CI and run agent-pr-gate itself, or branch protection waits forever.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
REQUIRED_CHECK = "test"
REQUIRED_STATUS = "agent-pr-gate"


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _publishes_with_token(text: str) -> bool:
    uses_token = "github.token" in text or "secrets.GITHUB_TOKEN" in text
    publishes = "git push" in text or "gh pr create" in text
    return uses_token and publishes


class WorkflowTests(unittest.TestCase):
    def test_ci_job_is_the_required_check_name(self):
        text = _text("ci.yml")
        self.assertIn("\n  test:\n", text)
        self.assertIn("workflow_dispatch:", text)

    def test_token_publishers_create_checks_themselves(self):
        offenders = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            if not _publishes_with_token(text):
                continue
            missing = []
            if "gh workflow run ci.yml" not in text:
                missing.append("dispatch ci.yml")
            if "pr-number:" not in text:
                missing.append("agent-pr-gate pr-number")
            if "0xgui/agent-pr-gate@" not in text:
                missing.append("agent-pr-gate action")
            if f"status-context: {REQUIRED_STATUS}" not in text:
                missing.append(f"status {REQUIRED_STATUS}")
            if missing:
                offenders.append(f"{path.name}: {', '.join(missing)}")
        self.assertEqual(offenders, [])

    def test_worker_dry_run_is_not_the_required_check(self):
        text = _text("ci.yml")
        self.assertIn("\n  worker-dry-run:\n", text)
        self.assertIn("name: worker dry-run\n", text)
        self.assertIn("python3 scripts/worker_dry_run.py", text)
        self.assertEqual(text.count("\n  test:\n"), 1)
        script = (ROOT / "scripts" / "worker_dry_run.py").read_text(encoding="utf-8")
        self.assertIn('["deploy", "--dry-run"]', script)
        self.assertIn('["whoami"]', script)

    def test_mirror_workflow_requests_both_required_results(self):
        text = _text("mirror-substack.yml")
        self.assertIn("gh workflow run ci.yml --ref", text)
        self.assertIn("pr-number: ${{ steps.pr.outputs.number }}", text)
        self.assertIn(f"status-context: {REQUIRED_STATUS}", text)
        self.assertIn("actions: write", text)
        self.assertNotIn("rss.silvags.com", text)


if __name__ == "__main__":
    unittest.main()
