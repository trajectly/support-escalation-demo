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
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml
```

Notes:

- This records the baseline trace and fixtures.
- If `OPENAI_API_KEY` and `TRAJECTLY_DEMO_USE_OPENAI=1` are set, it records live OpenAI outputs.
- If not set, it records a deterministic mock provider output.

## Step 2: Verify baseline passes

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml
```

Expected: `PASS` (exit code `0`).

## Step 3: Run intentionally regressed variant

```bash
python -m trajectly run specs/trt-support-agent-regression.agent.yaml
```

Expected: `FAIL` (exit code `1`) due to:

- `CONTRACT_TOOL_DENIED` (`unsafe_auto_close`)
- sequence/refinement violations (missing expected escalation path)

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

## Step 5: Simulate real PR workflow

The CI workflow gates on `specs/trt-support-agent-baseline.agent.yaml`.
In real PRs, you do not swap specs; you change agent code and rerun same spec.

### 5.1 Create feature branch with subtle bug

```bash
git checkout -b feat/faster-resolution
```

Edit `agents/support_agent.py`:

- change human-review path from `escalate_to_human(...)` to `unsafe_auto_close(...)`
- keep commit message "perf-like" to simulate realistic accidental regression

```bash
git add agents/support_agent.py
git commit -m "perf: reduce support escalation latency"
```

### 5.2 Observe local and CI failure

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly report
```

Then push the branch and open a PR.  
GitHub Action should fail with regression exit code and attach artifacts.

## Step 6: Fix via Trajectly loop

Restore policy-compliant behavior in `agents/support_agent.py`:

- call `escalate_to_human(...)` when `requires_human_review` is true.

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

## CI snippet reference

The workflow in `.github/workflows/trajectly.yml` is intentionally thin:

- install Trajectly
- run spec
- generate report
- upload artifacts
- fail job on Trajectly exit code

This mirrors Trajectly's product philosophy: the CLI is the product, CI wrappers are transport.
