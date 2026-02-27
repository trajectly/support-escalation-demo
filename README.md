# Support Escalation Demo for Trajectly

This private demo repository is designed to convince engineering teams why Trajectly belongs in CI for agent systems.

It shows a realistic PR workflow:

1. Record a baseline behavior for a support escalation agent.
2. Run deterministic regression checks locally and in CI.
3. Introduce a subtle "looks safe" change that silently regresses policy behavior.
4. Catch it with Trajectly (witness index + contract/refinement violations).
5. Reproduce, shrink, fix, and turn CI green.

## Why this demo is practical

- **CLI-first**: all core actions run through `python -m trajectly ...`
- **CI-native**: includes `.github/workflows/trajectly.yml`
- **Deterministic**: replay uses fixtures, not flaky output diffs
- **Offline-friendly**: if no API key is set, the demo uses a deterministic mock LLM path

## Repo layout

```text
agents/
  support_agent.py               # baseline behavior
  support_agent_regression.py    # intentionally regressed variant
  support_tools.py               # tools + LLM wrapper
specs/
  trt-support-agent-baseline.agent.yaml
  trt-support-agent-regression.agent.yaml
.github/workflows/trajectly.yml
TUTORIAL.md
```

## 5-minute quickstart

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m trajectly init
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml
python -m trajectly run specs/trt-support-agent-regression.agent.yaml
python -m trajectly report
python -m trajectly repro
python -m trajectly shrink
```

Expected result: regression run fails with `CONTRACT_TOOL_DENIED` for `unsafe_auto_close`.

To also verify baseline pass explicitly:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml
```

Expected result: PASS (exit code `0`).

## Optional live model recording

The demo works without external keys by default.  
If you want real OpenAI recording, set:

```bash
export OPENAI_API_KEY="sk-..."
export TRAJECTLY_DEMO_USE_OPENAI=1
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml
```

`run` still replays deterministically from fixtures.

## CI behavior

The GitHub Actions workflow runs:

```bash
python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
python -m trajectly report --pr-comment > trajectly_pr_comment.md
```

The workflow uploads `.trajectly/**` artifacts and posts/updates a PR comment.

To make Trajectly checks truly block merges, configure GitHub branch protection (or rulesets)
and require the `Trajectly Agent Regression Tests` check on `main`.

## Full walkthrough

See [TUTORIAL.md](TUTORIAL.md) for the full branch/PR regression and fix loop.

## Local dashboard view (optional)

If you want visual trace and flow inspection, point the local Trajectly web viewer at this repo's generated reports:

```bash
git clone https://github.com/trajectly/trajectly-dashboard-local.git
cd trajectly-dashboard-local
npm install

SUPPORT_DEMO_DIR="/absolute/path/to/support-escalation-demo"
cp "$SUPPORT_DEMO_DIR/.trajectly/reports/latest.json" public/data/real/latest.json
cp "$SUPPORT_DEMO_DIR/.trajectly/reports/trt-support-agent.json" public/data/real/reports/

npm run dev
```

Then open `http://localhost:5173/dashboard`.
