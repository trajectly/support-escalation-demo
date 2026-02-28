# Support Escalation Demo for Trajectly

This demo shows why Trajectly belongs in CI for AI agent systems.

You will record a baseline, introduce a subtle "looks safe" code change that silently
bypasses mandatory escalation, and watch Trajectly catch it -- both locally and in CI --
with a visual dashboard, deterministic repro commands, and precise violation reports.

## 1. Setup

```bash
git clone https://github.com/trajectly/support-escalation-demo.git
cd support-escalation-demo

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 2. Set up the local dashboard

Set up the dashboard now so you can visualize every step that follows.

```bash
cd ..
git clone https://github.com/trajectly/trajectly-dashboard-local.git
cd trajectly-dashboard-local
npm install
cd ../support-escalation-demo
```

You now have two sibling directories: `support-escalation-demo/` and
`trajectly-dashboard-local/`. The dashboard reads JSON report files that
Trajectly generates -- no cloud services, no login.

Configure the dashboard once to read this repo's reports directly:

```bash
printf "VITE_DATA_DIR=%s/.trajectly/reports\n" "$(pwd)" > ../trajectly-dashboard-local/.env.local
```

## 3. Record baseline and view in dashboard

```bash
python -m trajectly init
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
```

Expected: `PASS` (exit code `0`).

Start the dashboard:

```bash
cd ../trajectly-dashboard-local && npm run dev &
cd ../support-escalation-demo
```

Open **http://localhost:5173/dashboard**. You should see:

- **Support Escalation Demo Agent** with status **PASS**
- Click into it to see the **Agent Flow Graph**: `fetch_ticket` -> `check_entitlements` -> LLM call -> `escalate_to_human` -- all green
- The **trace timeline** shows every event in order with timing
- The **contract summary** shows all checks passed

This is what a healthy agent trace looks like. Trajectly captured the full
behavioral fingerprint of the agent so it can detect if anything changes.

## 4. Introduce a regression and view what Trajectly catches

```bash
python -m trajectly run specs/trt-support-agent-regression.agent.yaml --project-root .
```

Expected: `FAIL` (exit code `1`).

Refresh `http://localhost:5173/dashboard`. Now you should see:

- **Status: FAIL** with a witness index pointing to the exact step where behavior diverged
- The **Agent Flow Graph** highlights the violation: `escalate_to_human` is missing
- The **violation details** include refinement failures such as:
  - `REFINEMENT_BASELINE_CALL_MISSING`
  - `REFINEMENT_EXTRA_TOOL_CALL`
  - `REFINEMENT_NEW_TOOL_NAME_FORBIDDEN`

The regression agent added a single "fast-track" business rule that overrides
the escalation decision. It looks like a harmless SLA optimization in code review,
but Trajectly catches it because the tool-call sequence no longer matches the
baseline behavioral contract.

## 5. Determinism break and fix

Trajectly catches workflow regressions, and it also exposes nondeterministic
agent code paths that make replay flaky.

### 5.1 Break replay by reading clock directly in agent code

```bash
python -m trajectly record specs/trt-support-agent-determinism-break.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-determinism-break.agent.yaml --project-root .
```

Expected: `FAIL` (exit code `1`).

This variant injects `datetime.now(timezone.utc)` directly into the LLM prompt.
On replay, the clock value changes, so fixture matching fails and Trajectly
flags the behavior as a regression.

### 5.2 Fix replay by routing time through an explicit tool

```bash
python -m trajectly record specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
python -m trajectly run specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
```

Expected: `PASS` (exit code `0`).

This variant moves time access into `@tool("now_utc")`, so Trajectly records
the tool output and replays it deterministically.

## 6. CLI deep dive: report, repro, shrink

```bash
python -m trajectly report
```

This prints the human-readable verdict: which spec failed, the violation code,
the witness index (first divergent step), and a copy-paste repro command.

```bash
python -m trajectly repro
```

Re-runs the exact failing trace from fixtures -- deterministic, offline, same
result every time. Share this command with a teammate and they get the same failure.

```bash
python -m trajectly shrink
```

Minimizes the failing trace to the shortest prefix that still reproduces the
violation. Instead of reading through 12 events, you get the 4-5 that matter.

### What's in the generated files

Trajectly writes detailed artifacts to `.trajectly/reports/`:

| File | What it contains |
|------|------------------|
| `latest.json` | Machine-readable roll-up of all specs in the last run |
| `trt-support-agent.json` | Full report: baseline skeleton, current skeleton, violations, witness index, repro command |
| `trt-support-agent.md` | Human-readable markdown version of the above |
| `latest.md` | Human-readable summary across all specs |

The JSON report contains fields the dashboard does not surface, including:
- `baseline_skeleton` and `current_skeleton` -- the exact ordered tool-call lists
- `all_violations_at_witness[]` -- machine-parseable TRT violation set at witness
- `primary_violation` and `witness_index` -- root cause + earliest failing event
- `repro_command` -- the exact CLI command to reproduce the failure

These are useful for scripting, CI integrations, and detailed debugging.

## 7. CI integration

The included `.github/workflows/trajectly.yml` runs on every push to `main`
and every pull request targeting `main`. It:

1. Installs Trajectly
2. Runs `python -m trajectly run` against the baseline spec
3. Generates a PR comment with `python -m trajectly report --pr-comment`
4. Uploads `.trajectly/` artifacts
5. Fails the job if Trajectly detected a regression

See [TUTORIAL.md](TUTORIAL.md) for the full branch/PR regression-and-fix loop,
including creating a subtle regression PR and watching Trajectly block it.

For a one-command local sanity check of all baseline/regression/determinism
paths:

```bash
bash scripts/verify_demo.sh
```

## Repo layout

```text
agents/
  support_agent.py               # baseline behavior
  support_agent_regression.py    # intentionally regressed variant
  support_agent_determinism_break.py
  support_agent_determinism_fix.py
  support_tools.py               # tools + LLM wrapper
specs/
  trt-support-agent-baseline.agent.yaml
  trt-support-agent-regression.agent.yaml
  trt-support-agent-determinism-break.agent.yaml
  trt-support-agent-determinism-fix.agent.yaml
scripts/
  verify_demo.sh
.github/workflows/trajectly.yml
TUTORIAL.md
```

## Optional: live OpenAI recording

The demo works fully offline with a deterministic mock LLM. To record live
OpenAI responses instead:

```bash
export OPENAI_API_KEY="sk-..."
export TRAJECTLY_DEMO_USE_OPENAI=1
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
```

All subsequent `trajectly run` calls replay from the recorded fixtures --
fully offline and deterministic regardless of which provider was used to record.
