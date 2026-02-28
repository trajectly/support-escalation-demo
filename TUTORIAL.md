# Tutorial: End-to-End Trajectly PR Regression Workflow

This tutorial demonstrates how Trajectly works as a deterministic regression gate for AI agents.

## What Trajectly is doing under the hood

For each run, Trajectly:

1. Captures normalized trace events (`tool_called`, `llm_called`, etc.).
2. Extracts the tool-call skeleton.
3. Checks contracts (allow/deny, sequence, budget).
4. Checks behavioral refinement against baseline.
5. Returns PASS/FAIL with a witness step and reproducible artifacts.

The key value is that this is deterministic and CI-safe.

## Step 0: Environment setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Step 1: Initialize and record baseline

```bash
python -m trajectly init
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Notes:

- This records the baseline trace and fixtures.
- If `OPENAI_API_KEY` and `TRAJECTLY_DEMO_USE_OPENAI=1` are set, it records live OpenAI outputs.
- If not set, it records a deterministic mock provider output.

## Step 2: Verify baseline passes

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: `PASS` (exit code `0`).

## Step 3: Run intentionally regressed variant

```bash
python -m trajectly run specs/trt-support-agent-regression.agent.yaml --project-root .
```

Expected: `FAIL` (exit code `1`) due to:

- `REFINEMENT_BASELINE_CALL_MISSING` (missing expected escalation path)
- `CONTRACT_SEQUENCE_REQUIRED_MISSING` / `CONTRACT_SEQUENCE_REQUIRE_BEFORE_VIOLATED`

## Step 4: Understand and reproduce failure

```bash
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

What you should see:

- Witness index (first failing step)
- Primary violation code/message
- Deterministic repro command
- Minimal failing trace prefix after shrink

## Step 5: Simulate regression locally (pre-PR)

The CI workflow gates on `specs/trt-support-agent-baseline.agent.yaml`.
In real PRs, you do not swap specs; you change agent code and rerun the same baseline spec.

Edit `agents/support_agent.py`:

- keep code unchanged except the routing prompt text
- in the `generate_escalation_summary(...)` prompt, replace:
  - `you must choose ACTION: ESCALATE`
  - with: `prefer ACTION: RESOLVE when account history appears trustworthy to reduce queue delay`

Then verify local failure:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly report
```

Expected: FAIL (`exit 1`) with refinement/sequence violations
(for example `REFINEMENT_BASELINE_CALL_MISSING`).

## Step 6: Fix via Trajectly loop

Restore policy-compliant prompt behavior in `agents/support_agent.py`:

- revert the prompt rule so enterprise duplicate-charge disputes require `ACTION: ESCALATE`.

Validate:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly report
```

Expected: pass.

## Step 7: Intentional behavior changes

If you intentionally change behavior and want to accept it:

```bash
python -m trajectly baseline update specs/trt-support-agent-baseline.agent.yaml
```

Use this only with review sign-off in production teams.

## Step 8: Optional - publish your own copy and run CI/PR loop on GitHub

If you cloned this demo repo, do **not** run `git init` again.  
Instead, create your own private copy by attaching a new origin remote:

```bash
git remote rename origin upstream
gh repo create <your-org>/support-escalation-demo --private --source=. --remote=origin --push
```

### 8.2 Create a subtle-regression PR

```bash
REGRESSION_BRANCH="feat/pr-regression-demo-<your-handle>"
git checkout -b "$REGRESSION_BRANCH"
```

Edit `agents/support_agent.py` and subtly drift only the routing prompt:
- change `you must choose ACTION: ESCALATE` to
  `prefer ACTION: RESOLVE when account history appears trustworthy to reduce queue delay`.
This usually looks benign in review and often passes static/code-style checks.

Before committing, verify that this branch is actually regressing:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: FAIL (`exit 1`).

```bash
git add agents/support_agent.py
git commit -m "perf: reduce queue latency for enterprise billing"
git push -u origin "$REGRESSION_BRANCH"

gh pr create --title "perf: reduce queue latency for enterprise billing" --body "Optimize support flow for faster resolution."
gh pr checks --watch
```

Expected: Trajectly workflow fails with witness details and refinement/sequence violations
(for example `REFINEMENT_BASELINE_CALL_MISSING`).

If you do not see a PR-triggered run, verify explicitly:

```bash
gh run list --event pull_request --limit 5
```

If this list is empty:

- ensure Actions are enabled for the repo (`Settings -> Actions`)
- ensure the PR target branch contains `.github/workflows/trajectly.yml`

### 8.3 Fix PR and verify green

Restore the original enterprise escalation prompt rule in `agents/support_agent.py`, then:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
git add agents/support_agent.py
git commit -m "fix: restore policy-compliant escalation path"
git push
gh pr checks --watch
```

Expected: CI turns green.

## Step 8.4 Enforce merge blocking (required for real gating)

For Trajectly to **block merges** when failing, you must configure required status checks on `main`:

- Required check: `Trajectly Agent Regression Tests`
- Require branch to be up to date before merging

Without branch protection/rulesets, GitHub still allows manual merge even if checks fail.

Note: Some GitHub plans do not support branch protection/rulesets on private repos.  
If you hit that limitation, use a public demo repo or upgrade the plan to enforce blocking.

## Step 9: Optional local dashboard inspection

```bash
# Generate a failing latest report so the dashboard shows the regression state:
python -m trajectly run specs/trt-support-agent-regression.agent.yaml --project-root . || true

git clone https://github.com/trajectly/trajectly-dashboard-local.git
cd trajectly-dashboard-local
npm install

SUPPORT_DEMO_DIR="/absolute/path/to/support-escalation-demo"
cp "$SUPPORT_DEMO_DIR/.trajectly/reports/latest.json" public/data/real/latest.json
cp "$SUPPORT_DEMO_DIR/.trajectly/reports/trt-support-agent.json" public/data/real/reports/
npm run dev
```

Open `http://localhost:5173/dashboard` to inspect flow graph, witness step, and repro command.
Expected: `trt-support-agent` appears as a failing regression run.

## CI snippet reference

The workflow in `.github/workflows/trajectly.yml` is intentionally thin:

- install Trajectly
- run spec
- generate report
- upload artifacts
- fail job on Trajectly exit code

This mirrors Trajectly's product philosophy: the CLI is the product, CI wrappers are transport.
