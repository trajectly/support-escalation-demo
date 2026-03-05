# Support Escalation Demo for Trajectly (Declarative Graph)

This demo shows a support escalation workflow built with `trajectly.App` and validated with deterministic replay.

## What the agent does and why Trajectly is used

1. The agent reads a support ticket, checks entitlements, then chooses whether to escalate to a human or send a direct resolution.
2. The baseline path escalates enterprise duplicate-charge tickets; the regression variant intentionally resolves directly.
3. Trajectly is used to record baseline behavior and replay it as a deterministic gate so policy regressions are caught with a reproducible witness.

## What this demonstrates

1. Baseline behavior passes.
2. Intentional regression fails deterministically.
3. `report`, `repro`, and `shrink` provide triage signals.
4. Determinism break fails and determinism fix passes.

## Setup

```bash
git clone https://github.com/trajectly/support-escalation-demo.git
cd support-escalation-demo

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Validated on: March 5, 2026 (clean run).

## End-to-end Commands With Observed Outputs

### 1) Initialize workspace

Command:

```bash
python -m trajectly init
```

Observed output:

```text
Initialized Trajectly workspace at $PROJECT_ROOT
```

What this means:

1. `.trajectly/` workspace metadata is ready.

### 2) Record and run baseline

Commands:

```bash
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Observed output excerpts:

```text
Recorded 1 spec(s) successfully

- `trt-support-agent`: clean
  - trt: `PASS`
```

What this means:

1. Baseline trace exists.
2. Baseline replay is clean.

### 3) Run intentional regression

Command:

```bash
python -m trajectly run specs/trt-support-agent-regression.agent.yaml --project-root .
```

Observed output excerpt:

```text
- `trt-support-agent`: regression
  - trt: `FAIL` (witness=10)
```

What this means:

1. Regression is detected.
2. This step is expected to exit non-zero.

### 4) Triage with report, repro, shrink

Commands:

```bash
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
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
```

What this means:

1. `report` summarizes the failure.
2. `repro` replays the same failing case.
3. `shrink` reduces the failing counterexample.

### 5) Inspect JSON after shrink

Command:

```bash
python -m trajectly report --json
```

Observed output excerpt:

```json
{
  "regressions": 1,
  "reports": [
    {
      "trt_failure_class": "REFINEMENT",
      "trt_primary_violation": {
        "code": "REFINEMENT_BASELINE_CALL_MISSING",
        "expected": "fetch_ticket",
        "observed": ["send_resolution"]
      },
      "trt_shrink_stats": {
        "original_len": 11,
        "reduced_len": 1
      },
      "trt_status": "FAIL"
    }
  ]
}
```

What this means:

1. Failure class is explicit (`REFINEMENT_BASELINE_CALL_MISSING`).
2. Shrink reduced the failing trace.

### 6) Determinism break and fix

Commands:

```bash
python -m trajectly record specs/trt-support-agent-determinism-break.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-determinism-break.agent.yaml --project-root .

python -m trajectly record specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
```

Observed output excerpts:

```text
# determinism break
- `trt-support-agent-determinism-break`: regression
  - trt: `FAIL` (witness=4)

# determinism fix
- `trt-support-agent-determinism-fix`: clean
  - trt: `PASS`
```

What this means:

1. Non-deterministic behavior is catchable.
2. Determinism fix restores clean replay.

## What success looks like

From the validated run:

1. Baseline run: exit `0`, `PASS`.
2. Regression run: exit `1`, `FAIL` with witness.
3. `report`: exit `0`.
4. `repro`: exit `1` (expected).
5. `shrink`: exit `0`.
6. Determinism break run: exit `1`.
7. Determinism fix run: exit `0`.

## One-command local verification

```bash
bash scripts/verify_demo.sh
```

## Repository structure

1. `agents/support_graph.py`: graph logic and routing policy.
2. `agents/support_agent*.py`: spec entry modules.
3. `specs/*.agent.yaml`: baseline/regression/determinism specs.
4. `scripts/verify_demo.sh`: CI-equivalent local check.
5. `.github/workflows/trajectly.yml`: CI workflow.

For the full walkthrough including PR drill and cleanup, see [TUTORIAL.md](TUTORIAL.md).
