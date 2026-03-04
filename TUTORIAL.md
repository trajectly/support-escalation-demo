# Tutorial: End-to-End Trajectly PR Regression Workflow (Support, Declarative Graph)

This tutorial validates the full lifecycle with the declarative graph SDK (`trajectly.App`) in a realistic support escalation agent.

You will:
1. run baseline (PASS)
2. run intentional regression (FAIL)
3. use `report`, `repro`, `shrink`
4. run determinism break/fix
5. simulate a PR-style risky change in graph logic and recover to green

## Step 0: Setup

```bash
git clone https://github.com/trajectly/support-escalation-demo.git
cd support-escalation-demo

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Optional dashboard setup

```bash
cd ..
git clone https://github.com/trajectly/trajectly-dashboard-local.git
cd trajectly-dashboard-local
npm install
printf "VITE_DATA_DIR=%s/.trajectly/reports\n" "$(pwd)/../support-escalation-demo" > .env.local
npm run dev &
cd ../support-escalation-demo
```

Dashboard URL: <http://localhost:5173/dashboard>

## Step 1: Understand the graph layout

Core graph module:
- `agents/support_graph.py`

Spec entrypoints (thin wrappers):
- baseline -> `agents/support_agent.py`
- regression -> `agents/support_agent_regression.py`
- determinism break -> `agents/support_agent_determinism_break.py`
- determinism fix -> `agents/support_agent_determinism_fix.py`

The graph emits the same tool event names as contracts expect.

## Step 2: Initialize and record baseline

```bash
python -m trajectly init
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: PASS (`0`).

If dashboard is running, baseline appears green.

## Step 3: Run intentional regression variant

```bash
python -m trajectly run specs/trt-support-agent-regression.agent.yaml --project-root .
```

Expected: FAIL (`1`).

Expected failure shape:
- missing baseline escalation path
- refinement/contract evidence in report
- deterministic repro available

## Step 4: Triage from CLI

```bash
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

Expected exit behavior here:
- `report` -> `0`
- `repro` -> `1` (reproduces failure)
- `shrink` -> `0`

## Step 5: Determinism break and fix

### 5.1 Determinism break (expected fail)

```bash
python -m trajectly record specs/trt-support-agent-determinism-break.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-determinism-break.agent.yaml --project-root .
```

Expected: FAIL (`1`).

### 5.2 Determinism fix (expected pass)

```bash
python -m trajectly record specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
```

Expected: PASS (`0`).

## Step 6: Simulate risky PR change in graph baseline logic

Edit `agents/support_graph.py`.

Find `choose_resolution_action_node(...)` and temporarily insert this override:

```python
if int(policy["max_auto_credit_usd"]) >= 100:
    action = "resolve"
```

Now run baseline spec again:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: FAIL (`1`).

This simulates a subtle "performance optimization" that bypasses required escalation.

## Step 7: Revert fix and confirm green

Remove the override you added in Step 6, then run:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: PASS (`0`).

## Step 8: Baseline lifecycle commands (intentional behavior changes)

Use these only when behavior changes are intentionally approved:

```bash
python -m trajectly baseline create --name v2 specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly baseline diff trt-support-agent v1 v2 --project-root . --json
python -m trajectly baseline promote v2 specs/trt-support-agent-baseline.agent.yaml --project-root .
```

## Step 9: PR failure drill (local branch + failing commit)

This section simulates a real PR lifecycle with explicit commits.

Create a feature branch:

```bash
git checkout -b tutorial/pr-fail-drill
```

Re-introduce the risky baseline bypass in `agents/support_graph.py`:

```bash
python - <<'PY'
from pathlib import Path

path = Path("agents/support_graph.py")
text = path.read_text(encoding="utf-8")
needle = '        action = choose_resolution_action(summary, bool(policy["requires_human_review"]))\n'
inject = (
    '        action = choose_resolution_action(summary, bool(policy["requires_human_review"]))\n'
    '        if int(policy["max_auto_credit_usd"]) >= 100:\n'
    '            action = "resolve"\n'
)
if inject not in text:
    text = text.replace(needle, inject, 1)
path.write_text(text, encoding="utf-8")
PY
```

Commit the risky change:

```bash
git add agents/support_graph.py
git commit -m "test: inject risky escalation bypass to rehearse failing PR"
```

Run the same replay gate used by CI for PR verdicts:

```bash
python -m trajectly init
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
echo $?
```

Expected:
- baseline replay exits `1`
- this fail is caused by Trajectly catching a regression (`trt: FAIL` + witness), not by tooling/runtime errors

Confirm the failure reason:

```bash
python -m trajectly report
```

Expected report signal:
- `trt: FAIL`
- witness index present
- regression details tied to baseline-vs-current divergence

## Step 10: PR fix commit and green rerun

Remove the risky override from `agents/support_graph.py` (or restore from `origin/main`), then commit:

```bash
git checkout origin/main -- agents/support_graph.py
git add agents/support_graph.py
git commit -m "fix: restore required escalation behavior"
```

Re-run the same replay gate:

```bash
python -m trajectly init
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
echo $?
```

Expected:
- baseline replay exits `0`
- your branch is ready for PR review

Optional full parity check before opening PR:

```bash
bash scripts/verify_demo.sh
```

## Step 11: Optional GitHub PR execution

If you want to test the full remote loop:

```bash
git push -u origin tutorial/pr-fail-drill
gh pr create --fill --base main --head tutorial/pr-fail-drill
```

After opening the PR, confirm:
1. the first risky commit fails CI
2. the fix commit turns CI green

## Step 12: Optional live OpenAI recording

Default is deterministic mock LLM mode.

To record with OpenAI:

```bash
export OPENAI_API_KEY="sk-..."
export TRAJECTLY_DEMO_USE_OPENAI=1
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Replay remains fixture-based and deterministic.
