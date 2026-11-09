# The Bottleneck Moved

Platform engineering when AI writes the code: how a team can know that an AI-written change does what it intended, and stays acceptable in production, without someone reading every line.

KCD Porto × DevOpsDays · 19 November 2026

[Open the slides](https://silvags.com/talks/bottleneck-moved/slides.html) — arrow keys on a laptop; swipe on a phone (turn it sideways)

## Sources

Every number and quote in the talk, all published in 2026. Company posts are self-reported: read them as what they did, not as proof.

### Everyone uses it, few trust it

- [Stack Overflow Developer Survey 2026 — AI](https://survey.stackoverflow.co/2026/ai) — 30,903 responses. 73% of AI coding-tool users use them daily; 6.6% trust AI for important work decisions; 48% trust it when they can easily verify the output.

### The volume is real

- [State of AI Impact in Engineering: Q3 Report](https://getdx.com/uploads/state-of-ai-impact-in-engineering-q3-report.pdf) — DX, Oct 2026, 500+ engineering organizations. PRs per developer per week up 75.5% in a year. Vendor data.

- [Octoverse 2026](https://github.blog/news-insights/octoverse/octoverse-commits-pushes-reach-new-highs-in-2026-as-developers-build-with-agents/) — GitHub, Oct 2026. Merged pull requests more than tripled; 40%+ of PRs now start with an agent's first draft.

### The bottleneck moved

- [AI Changed How Spotify Builds](https://engineering.atspotify.com/2026/9/ai-changed-how-spotify-builds-what-we-learned-and-fixed-about-quality-at-higher-velocity) — Spotify, Sep 2026. “AI increased the capacity to produce change. The next constraint became our ability to verify it.”

- [AI Engineering Report 2026: The Acceleration Whiplash](https://www.faros.ai/blog/ai-acceleration-whiplash-takeaways) — Faros AI, Apr 2026, 22,000 developers. Median time in review up 441.5%. Vendor data.

- [The ROI of AI-assisted Software Development](https://services.google.com/fh/files/misc/dora-roi-of-ai-assisted-software-development-2026.pdf) — DORA, Apr 2026. AI volume can end up “overwhelming existing deployment pipelines and manual review gates”.

- [When AI builds itself](https://www.anthropic.com/institute/recursive-self-improvement) — Anthropic, 2026. “Human code review has become a new bottleneck.”

### The platform's new job

- [Guardrails, not gates](https://www.cncf.io/blog/2026/10/01/guardrails-not-gates-rethinking-policy-in-platform-teams/) — CNCF blog, Koray Oksay, Oct 2026.

- [Many SWE-bench-Passing PRs Would Not Be Merged into Main](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/) — METR, Mar 2026. Roughly half of test-passing AI patches would not be merged by maintainers.

- Lauren Tan on agents and constraints — Oct 2026. “every mistake and bad pattern you observe from agents, needs to turn into a constraint”.

### The verification loop, step by step

- [GitHub Agentic Workflows technical preview](https://github.blog/changelog/2026-02-13-github-agentic-workflows-are-now-in-technical-preview/) — GitHub, Feb 2026. Step 1: read-only by default, writes through pre-approved outputs.

- [How we contain Claude across products](https://www.anthropic.com/engineering/how-we-contain-claude) — Anthropic, May 2026. Step 1.

- [Minions: Stripe's one-shot, end-to-end coding agents](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2) — Stripe, Feb 2026. Steps 1, 2, 3: a devbox per task, scoped tools, two CI rounds then a human.

- [Sandboxing Untrusted AI Agents at Scale](https://opensource.googleblog.com/2026/11/sandboxing-untrusted-ai-agents-at-scale.html) — Google, Nov 2026. Step 1: Agent Substrate and gVisor donated to the CNCF.

- [The AI engineering stack we built internally](https://blog.cloudflare.com/internal-ai-engineering-stack/) — Cloudflare, Apr 2026. Step 2: AGENTS.md across ~3,900 repos.

- [Evaluating AGENTS.md](https://arxiv.org/abs/2602.11988) — ETH Zurich, ICLR 2026. Step 2: keep context files short, and test them.

- [Using AI to Delete Code](https://www.uber.com/us/en/blog/ai-code-cleanup/) — Uber, Oct 2026. Step 3: a change “can pass CI and still be wrong”.

- [Building an agentic harness that outlasts the model](https://shopify.engineering/building-an-agentic-harness-that-outlasts-the-model) — Shopify, Jul 2026. Step 3: “Tests are the oracle.”

- [Trust but verify; or, the correctness ratchet](https://smallcultfollowing.com/babysteps/blog/2026/10/30/trust-but-verify/) — Niko Matsakis, Oct 2026. Step 3.

- [Orchestrating AI Code Review at scale](https://blog.cloudflare.com/ai-code-review/) — Cloudflare, Apr 2026. Step 4: three risk tiers.

- [Speeding up code review with small-change](https://lethain.com/small-changes/) — Will Larson, Oct 2026. Step 4.

- [Catching Bugs Before They Land: JiTTesting](https://engineering.fb.com/2026/10/29/security/catching-bugs-before-they-land-jittestings-human-on-the-loop-approach-at-full-scale/) — Meta, Oct 2026. Step 5.

- [Argo Rollouts](https://argoproj.github.io/rollouts/) — CNCF project. Step 5: canary releases with automatic rollback.

### Measure it, and does it work?

- [DORA metrics guide](https://dora.dev/guides/dora-metrics/) — DORA, Jan 2026.

- [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/) — Anthropic, Oct 2026. 2× merged PRs, −40% reverts.

- [How Atlassian cut PR cycle time by 45% with AI code reviews](https://www.atlassian.com/blog/rovo/how-we-cut-pr-cycle-time-with-ai-code-reviews) — Atlassian, Jan 2026. Vendor post.

## Try it

- [agent-pr-gate](https://github.com/0xgui/agent-pr-gate) — a GitHub Action that gates agent-written pull requests on risk tier, evidence and review rounds.
