# Support Escalation Demo for Trajectly (Declarative Graph)

This demo shows how to build and test an agent with the declarative graph SDK (`trajectly.App`) and enforce deterministic regression gates in CI.

You will:
- run a graph-based baseline
- run an intentional regression and see deterministic failure
- run determinism break/fix variants
- inspect results in CLI (`report`, `repro`, `shrink`) and CI artifacts

## Dependency note

`requirements.txt` installs Trajectly directly from PyPI (`trajectly==0.4.1`).
This release includes the declarative graph SDK (`trajectly.App` and `trajectly.sdk.graph`).

## Setup

```bash
git clone https://github.com/trajectly/support-escalation-demo.git
cd support-escalation-demo

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Graph architecture in this demo

Main graph builder:
- `agents/support_graph.py`

Thin entry modules used by specs:
- `agents/support_agent.py` -> baseline graph mode
- `agents/support_agent_regression.py` -> regression mode
- `agents/support_agent_determinism_break.py` -> determinism-break mode
- `agents/support_agent_determinism_fix.py` -> determinism-fix mode

The graph routes through the same Trajectly instrumentation path as before and preserves tool event names used in contracts:
- `fetch_ticket`
- `check_entitlements`
- `escalate_to_human`
- `send_resolution`
- `now_utc` (determinism-fix)

## Run baseline

```bash
python -m trajectly init
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: `PASS` (exit code `0`).

## Run intentional regression

```bash
python -m trajectly run specs/trt-support-agent-regression.agent.yaml --project-root .
```

Expected: `FAIL` (exit code `1`).

## Triage commands

```bash
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

Expected exits after the intentional regression run above:
- `report` -> `0`
- `repro` -> `1`
- `shrink` -> `0`

## Determinism scenarios

Break (expected fail):

```bash
python -m trajectly record specs/trt-support-agent-determinism-break.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-determinism-break.agent.yaml --project-root .
```

Fix (expected pass):

```bash
python -m trajectly record specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
```

## CI workflow

`.github/workflows/trajectly.yml` runs:
1. `bash scripts/verify_demo.sh`
2. baseline replay gate
3. report generation + PR comment
4. artifact upload
5. fail job on regression

## One-command local verification

```bash
bash scripts/verify_demo.sh
```

## Optional live OpenAI recording

Default demo mode uses deterministic mock LLM responses.

To record with live OpenAI:

```bash
export OPENAI_API_KEY="sk-..."
export TRAJECTLY_DEMO_USE_OPENAI=1
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
```

After recording, replay remains fixture-based and deterministic.

For the full end-to-end walkthrough (including PR fail/fix loop), see [TUTORIAL.md](TUTORIAL.md).
