# Mirror loop

A GitHub Actions run of Mirror Binary Paths opens a pull request with `GITHUB_TOKEN`, then dispatches CI and runs agent-pr-gate on that pull request. The head commit gets a check named `test` and a commit status named `agent-pr-gate`. A normal low-tier result would auto-merge. A proof run must not.

## Sub-features

- `mirror-open` the workflow run is `workflow_dispatch` or `schedule`, and the pull request author is `github-actions[bot]`.
- `mirror-test` the head SHA has a completed check run named `test` from workflow `CI`.
- `mirror-gate` the head SHA has a commit status named `agent-pr-gate`.
- `mirror-decision` the run log shows the gate result and whether auto-merge was armed. A `proof_slug` run records `proof=yes` and does not call `gh pr merge`.

## How to get to it (user POV)

- This is not a page on the site. Open the Actions run for Mirror Binary Paths, then the pull request it links.
- For a proof, dispatch the workflow on a branch that contains this fix, with `proof_slug` set to an existing essay slug. The schedule leaves that input empty.
- Do not merge a proof pull request. It exists to put checks on a commit. Merging it removes an essay from `main` until a later mirror restores it.

## Driving it with Cursor browser

Preconditions:

- The workflow file on the dispatched ref contains `gh workflow run ci.yml --ref` and `status-context: agent-pr-gate`.
- `gh` is authenticated for `0xgui/website`.
- Do not dispatch the proof against a ref whose workflow is the old one. That file never creates the checks.

- **Dispatch.** `gh workflow run "Mirror Binary Paths" --ref <fix-branch> -f proof_slug=<slug>`.
- **Run.** `gh run watch` that run. It should finish without merging.
- **Pull request.** `gh pr view` the number from the run log. `author.login` is `github-actions[bot]`. `baseRefName` is `main`.
- **Checks.** `gh api repos/0xgui/website/commits/<headSha>/check-runs` includes `name` `test`. `gh api repos/0xgui/website/commits/<headSha>/status` includes context `agent-pr-gate`.
- **Decision.** The run log contains `auto=yes` and `proof=yes` for a proof. `gh pr view --json autoMergeRequest` is null.
- **Proof.** Save the run id, pull request URL, check name, and status context in `artifacts/mirror-loop/notes.md`.

## Gotchas

- `GITHUB_TOKEN` does not start `pull_request` workflows. A green `test` check on a bot pull request came from `workflow_dispatch` of `ci.yml`, not from the pull request event.
- Branch protection is what waits on `test` and `agent-pr-gate`. Until those are required, `gh pr merge --auto` merges immediately. The proof path must not call it.
- The mirror tries Substack, then `workers.dev/raw.xml`, then `rss.silvags.com/raw.xml`. A failed fetch stays quiet while `writing/last-good.txt` is under 48 hours old. `rss.silvags.com` is still challenged while Bot Fight Mode is on. The workers.dev host serves `/raw.xml` only after the worker deploy on `main`.
