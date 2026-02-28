# Tutorial: End-to-End Trajectly PR Regression Workflow

This tutorial walks through every Trajectly feature using a real support
escalation agent. By the end you will have:

- Recorded a behavioral baseline
- Viewed it in the local dashboard
- Introduced a subtle regression and watched Trajectly catch it
- Used report/repro/shrink to understand and minimize the failure
- Simulated the exact PR workflow that Trajectly gates in CI
- Fixed the regression and turned CI green

## What Trajectly does under the hood

For each run, Trajectly:

1. Captures normalized trace events (`tool_called`, `llm_called`, etc.).
2. Extracts the tool-call skeleton (ordered list of tool names).
3. Checks contracts (allow/deny lists, required sequences, budget limits).
4. Checks behavioral refinement against the recorded baseline.
5. Returns PASS/FAIL with the witness step (earliest divergence) and
   reproducible artifacts.

The key: this is **deterministic** and **CI-safe**. Same code + same fixtures =
same verdict. Always.

---

## Step 0: Environment and dashboard setup

### 0.1 Python environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 0.2 Local dashboard

Set up the dashboard now so you can visualize results throughout the tutorial.

```bash
cd ..
git clone https://github.com/trajectly/trajectly-dashboard-local.git
cd trajectly-dashboard-local
npm install
cd ../support-escalation-demo
```

You now have two sibling directories. The dashboard reads Trajectly's JSON
report files -- no cloud services, no login required.

Configure the dashboard once so it reads this repo's reports directly:

```bash
printf "VITE_DATA_DIR=%s/.trajectly/reports\n" "$(pwd)" > ../trajectly-dashboard-local/.env.local
```

---

## Step 1: Initialize and record baseline

```bash
python -m trajectly init
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
```

This executes `agents/support_agent.py`, captures every tool call and LLM
response, and stores the trace as the behavioral baseline in `.trajectly/baselines/`.
Fixtures (deterministic replay data) are saved to `.trajectly/fixtures/`.

If `OPENAI_API_KEY` and `TRAJECTLY_DEMO_USE_OPENAI=1` are set, live OpenAI
responses are recorded. Otherwise a deterministic mock is used.

### Verify baseline passes

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: `PASS` (exit code `0`).

---

## Step 2: View baseline in dashboard

Start the dashboard:

```bash
cd ../trajectly-dashboard-local && npm run dev &
cd ../support-escalation-demo
```

Open **http://localhost:5173/dashboard**.

What you see:

- **Support Escalation Demo Agent** -- status **PASS**
- **Agent Flow Graph**: `fetch_ticket` -> `check_entitlements` -> LLM call -> `escalate_to_human` (all green nodes)
- **Trace timeline**: every event in execution order with millisecond timing
- **Contract summary**: all checks passed (tool allow/deny, sequence, budget)

This is the behavioral fingerprint Trajectly records. Any future run that
deviates from this trace structure will be caught.

---

## Step 3: Run the intentionally regressed variant

The repo includes a second agent file (`agents/support_agent_regression.py`)
that contains a subtle one-line business rule change:

```python
# In support_agent_regression.py -- this line overrides escalation:
if policy["max_auto_credit_usd"] >= 100:
    action = "resolve"
```

It looks like a harmless SLA optimization, but it silently bypasses mandatory
human review for enterprise billing disputes.

Run it:

```bash
python -m trajectly run specs/trt-support-agent-regression.agent.yaml --project-root .
```

Expected: `FAIL` (exit code `1`) with violations such as:

- `REFINEMENT_BASELINE_CALL_MISSING` -- the baseline called `escalate_to_human` but the current run did not
- `REFINEMENT_EXTRA_TOOL_CALL` -- current run added a non-baseline tool call
- `REFINEMENT_NEW_TOOL_NAME_FORBIDDEN` -- current run introduced a tool name outside baseline policy

---

## Step 4: View the regression in dashboard

Refresh **http://localhost:5173/dashboard**.

What changed:

- **Status: FAIL** with the witness index pointing to the exact step where behavior diverged
- **Agent Flow Graph**: `escalate_to_human` node is now highlighted as **missing/violated**
- **Violation details**: the specific contract and refinement failures
- Compare this with Step 2's healthy graph -- the visual diff is immediate

---

## Step 5: CLI deep dive -- report, repro, shrink

### report

```bash
python -m trajectly report
```

Prints the human-readable verdict: which spec failed, violation code, witness
index, and a copy-paste repro command. This is what CI posts as a PR comment.

### repro

```bash
python -m trajectly repro
```

Re-runs the exact failing trace from fixtures. Deterministic, offline, same
result every time. Share this command with a teammate and they get the same
failure on their machine.

### shrink

```bash
python -m trajectly shrink
```

Minimizes the trace to the shortest prefix that still triggers the violation.
Instead of reading 12 events, you see the 4-5 that matter.

### Generated files reference

| File | Contents |
|------|----------|
| `.trajectly/reports/latest.json` | Machine-readable roll-up of all specs |
| `.trajectly/reports/trt-support-agent.json` | Full report: skeletons, violations, witness, repro |
| `.trajectly/reports/trt-support-agent.md` | Human-readable markdown version |
| `.trajectly/baselines/trt-support-agent.jsonl` | The recorded baseline trace (one JSON event per line) |
| `.trajectly/fixtures/trt-support-agent.json` | Recorded LLM/tool outputs for deterministic replay |

The JSON report contains fields not shown in the dashboard:
- `baseline_skeleton` / `current_skeleton` -- exact ordered tool-call lists
- `all_violations_at_witness[]` -- machine-parseable TRT violation set at witness
- `primary_violation` / `witness_index` -- root cause and earliest failing event
- `repro_command` -- exact CLI command to reproduce

---

## Step 6: Simulate regression on baseline code (the PR scenario)

In real CI, the workflow gates on the **baseline spec**
(`specs/trt-support-agent-baseline.agent.yaml`). You do not swap specs; you
change the agent code and rerun the same baseline spec.

### What to change

Open `agents/support_agent.py`. Find these lines:

```python
    action = choose_resolution_action(summary, bool(policy["requires_human_review"]))
    if action == "escalate":
```

Replace them with:

```python
    action = choose_resolution_action(summary, bool(policy["requires_human_review"]))

    # Fast-track: resolve directly when auto-credit budget covers the dispute
    if policy["max_auto_credit_usd"] >= 100:
        action = "resolve"

    if action == "escalate":
```

You added two lines: a comment and an `if` statement that overrides the
escalation decision when the auto-credit budget is >= $100.

This change:
- Looks like a harmless SLA optimization in code review
- Passes linting and static analysis
- Would not be flagged by AI code review tools

### Verify it fails

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: `FAIL` (exit code `1`).

```bash
python -m trajectly report
```

You should see the same violations as Step 3: the agent now calls
`send_resolution` instead of `escalate_to_human`, breaking the behavioral
contract.

### View in dashboard

Refresh the dashboard to confirm the regression is visible.

---

## Step 7: Fix via Trajectly loop

Remove the two lines you added in Step 6 so `agents/support_agent.py` looks
like the original:

```python
    action = choose_resolution_action(summary, bool(policy["requires_human_review"]))
    if action == "escalate":
```

Verify:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: `PASS` (exit code `0`).

Refresh the dashboard and confirm the status returns to green.

---

## Step 8: Intentional behavior changes

If you intentionally change behavior and want to accept the new trace:

```bash
python -m trajectly baseline update specs/trt-support-agent-baseline.agent.yaml
```

This re-records the baseline from the current agent code. Use this only with
explicit review sign-off -- it permanently changes what Trajectly considers
"correct" behavior.

---

## Step 9: CI/PR loop on GitHub

### 9.1 Publish your own copy

If you cloned this demo, do **not** `git init` again. Create a private copy:

```bash
git remote rename origin upstream
gh repo create <your-org>/support-escalation-demo --private --source=. --remote=origin --push
gh repo set-default <your-org>/support-escalation-demo
```

The `gh repo set-default` command tells the GitHub CLI which repository to
use for PR operations (required when multiple remotes exist).

### 9.2 Create a subtle-regression PR

```bash
REGRESSION_BRANCH="feat/pr-regression-demo-$(whoami)"
git checkout -b "$REGRESSION_BRANCH"
```

Edit `agents/support_agent.py` -- add the fast-track override. Find:

```python
    action = choose_resolution_action(summary, bool(policy["requires_human_review"]))
    if action == "escalate":
```

Replace with:

```python
    action = choose_resolution_action(summary, bool(policy["requires_human_review"]))

    # Fast-track: resolve directly when auto-credit budget covers the dispute
    if policy["max_auto_credit_usd"] >= 100:
        action = "resolve"

    if action == "escalate":
```

Before pushing, confirm local failure:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: `FAIL` (exit code `1`).

Commit and push:

```bash
git add agents/support_agent.py
git commit -m "perf: reduce queue latency for enterprise billing"
git push -u origin "$REGRESSION_BRANCH"

gh pr create \
  --title "perf: reduce queue latency for enterprise billing" \
  --body "Optimize support flow for faster resolution."

gh pr checks --watch
```

Expected: the **Trajectly Agent Regression Tests** check fails with
refinement violations.

If you do not see a triggered run:
- Ensure Actions are enabled (`Settings -> Actions -> General`)
- Ensure the PR targets `main` and `main` contains `.github/workflows/trajectly.yml`

### 9.3 Fix and verify green

Remove the fast-track override from `agents/support_agent.py` (delete the
comment line and the `if policy["max_auto_credit_usd"]` line), then:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
git add agents/support_agent.py
git commit -m "fix: restore policy-compliant escalation path"
git push
gh pr checks --watch
```

Expected: CI turns green.

### 9.4 Enforce merge blocking (required for real gating)

Right now the Trajectly check **reports** failure on the PR, but GitHub still
allows you to click "Merge". To make failing checks actually **block** the
merge button, you need to configure a Branch Protection Rule (or Ruleset).

**Steps (classic branch protection):**

1. Go to your repo on GitHub: `Settings` -> `Branches`.
2. Click **Add branch protection rule** (or edit the existing rule for `main`).
3. Set **Branch name pattern** to `main`.
4. Check **Require status checks to pass before merging**.
5. In the search box that appears, type `trajectly` and select
   **`Trajectly Agent Regression Tests`** from the dropdown.
   (This name must match the `name:` field in `.github/workflows/trajectly.yml`.
   It only appears after the workflow has run at least once.)
6. Optionally check **Require branches to be up to date before merging** so
   PRs always test against the latest `main`.
7. Click **Save changes** (or **Create** if this is a new rule).

After this, any PR where the Trajectly check fails will show a red
"Merge blocked" status and the merge button will be disabled.

**Using Rulesets (newer alternative):**

GitHub also offers Rulesets (`Settings` -> `Rules` -> `Rulesets`) which
provide the same functionality with a more flexible UI. Create a ruleset
targeting the `main` branch and add a "Require status checks" rule with
`Trajectly Agent Regression Tests`.

**GitHub plan limitations:**

- **Public repos**: branch protection and rulesets are available on all plans.
- **Private repos**: branch protection requires GitHub Pro, Team, or
  Enterprise. Free-plan private repos cannot enforce required checks.
  If you are on a free plan, either make the repo public for this demo
  or verify the check status manually before merging.

---

## CI workflow reference

The workflow in `.github/workflows/trajectly.yml`:

1. Installs Trajectly and project dependencies
2. Runs `python -m trajectly init` + `python -m trajectly run` against the baseline spec
3. Generates a PR comment with the verdict
4. Uploads `.trajectly/` artifacts
5. Fails the job if Trajectly detected a regression

This mirrors Trajectly's philosophy: the CLI is the product, CI wrappers are
transport.
