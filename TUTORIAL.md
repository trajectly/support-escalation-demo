# Tutorial: End-to-End Trajectly PR Regression Workflow (Support)

This walkthrough uses real validated outputs from March 5, 2026.

Path placeholders:

1. `$PROJECT_ROOT` = local repo path
2. `$VALIDATION_BRANCH` = `validation/docs-e2e-support-escalation-demo-202603051852`

## Step 0: Setup

```bash
git clone https://github.com/trajectly/support-escalation-demo.git
cd support-escalation-demo

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Observed result summary:

```text
setup_venv=0
setup_pip_upgrade=0
setup_requirements=0
```

## Step 1: Initialize and baseline

Commands:

```bash
python -m trajectly init
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Observed output excerpts:

```text
Initialized Trajectly workspace at $PROJECT_ROOT
Recorded 1 spec(s) successfully
- `trt-support-agent`: clean
  - trt: `PASS`
```

## Step 2: Intentional regression

Command:

```bash
python -m trajectly run specs/trt-support-agent-regression.agent.yaml --project-root .
```

Observed output excerpt:

```text
- `trt-support-agent`: regression
  - trt: `FAIL` (witness=10)
```

Observed exit code:

```text
13_run_regression=1
```

## Step 3: Triage commands

Commands:

```bash
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
python -m trajectly report --json
python -m trajectly report
```

Observed output excerpts:

```text
# report
- `trt-support-agent`: regression
  - trt: `FAIL` (witness=10)

# repro
Repro command: python -m trajectly run "$PROJECT_ROOT/specs/trt-support-agent-regression.agent.yaml" --project-root "$PROJECT_ROOT"
- `trt-support-agent`: regression
  - trt: `FAIL` (witness=10)

# shrink
Shrink completed and report updated with shrink stats.

# report --json excerpt
"trt_failure_class": "REFINEMENT"
"code": "REFINEMENT_BASELINE_CALL_MISSING"
"expected": "fetch_ticket"
"observed": ["send_resolution"]
"trt_shrink_stats": { "original_len": 11, "reduced_len": 1 }

# report (markdown)
- `trt-support-agent`: regression
  - trt: `FAIL` (witness=0)
```

Observed exit behavior:

```text
14_report_after_regression=0
15_repro=1
16_shrink=0
17_report_after_shrink_json=0
18_report_after_shrink_md=0
```

## Step 4: Determinism break and fix

Commands:

```bash
python -m trajectly record specs/trt-support-agent-determinism-break.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-determinism-break.agent.yaml --project-root .

python -m trajectly record specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
```

Observed output excerpts:

```text
# break
- `trt-support-agent-determinism-break`: regression
  - trt: `FAIL` (witness=4)

# fix
- `trt-support-agent-determinism-fix`: clean
  - trt: `PASS`
```

Observed exit behavior:

```text
20_record_det_break=0
21_run_det_break=1
22_record_det_fix=0
23_run_det_fix=0
```

## Step 5: PR drill (risky change)

Create branch:

```bash
git checkout -b $VALIDATION_BRANCH
```

Inject risky change into `agents/support_graph.py`:

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

Commit risky change:

```bash
git add agents/support_graph.py
git commit -m "test: inject risky escalation bypass to rehearse failing PR"
```

Observed output:

```text
[validation/docs-e2e-support-escalation-demo-202603051852 ...] test: inject risky escalation bypass to rehearse failing PR
 1 file changed, 2 insertions(+)
```

Run baseline gate (should fail):

```bash
python -m trajectly init
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly report
```

Observed output excerpt:

```text
- `trt-support-agent`: regression
  - trt: `FAIL` (witness=10)
```

Observed exit behavior:

```text
pr_init_after_risky=0
pr_run_baseline_after_risky=1
pr_report_after_risky=0
```

## Step 6: PR drill (fix commit)

Restore safe behavior and commit fix:

```bash
git checkout origin/main -- agents/support_graph.py
git add agents/support_graph.py
git commit -m "fix: restore required escalation behavior"
```

Observed output:

```text
[validation/docs-e2e-support-escalation-demo-202603051852 ...] fix: restore required escalation behavior
 1 file changed, 2 deletions(-)
```

Re-run baseline gate:

```bash
python -m trajectly init
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Observed output excerpt:

```text
- `trt-support-agent`: clean
  - trt: `PASS`
```

Observed exit behavior:

```text
pr_init_after_fix=0
pr_run_baseline_after_fix=0
```

## Step 7: Push branch and create PR

Commands:

```bash
git push -u origin $VALIDATION_BRANCH
gh pr create --base main --head $VALIDATION_BRANCH --title "docs-validation: support e2e capture" --body "Temporary PR for tutorial output capture. Will close unmerged."
```

Observed output:

```text
Branch '$VALIDATION_BRANCH' set up to track remote branch '$VALIDATION_BRANCH' from 'origin'.
https://github.com/trajectly/support-escalation-demo/pull/8
```

## Step 8: Cleanup (temporary validation branch/PR)

Commands:

```bash
gh pr close 8 --delete-branch --comment "Closing temporary docs-validation PR used to capture tutorial outputs."
git checkout main
git branch -D $VALIDATION_BRANCH
```

Observed output:

```text
✓ Closed pull request trajectly/support-escalation-demo#8 (docs-validation: support e2e capture)
✓ Deleted branch validation/docs-e2e-support-escalation-demo-202603051852
Deleted branch validation/docs-e2e-support-escalation-demo-202603051852 (was 0d2ac9b).
```

## Final expected verdicts

1. Baseline: pass.
2. Regression: fail with witness.
3. Repro: fail (expected).
4. Shrink: success.
5. Determinism break: fail.
6. Determinism fix: pass.
7. PR drill risky commit: fail.
8. PR drill fix commit: pass.
