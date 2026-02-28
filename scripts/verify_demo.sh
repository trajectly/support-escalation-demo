#!/usr/bin/env bash
set -euo pipefail

expect_exit() {
  local expected="$1"
  shift
  set +e
  "$@"
  local actual=$?
  set -e
  if [[ "$actual" -ne "$expected" ]]; then
    echo "Expected exit $expected but got $actual for: $*" >&2
    exit 1
  fi
}

python -m trajectly init
python -m trajectly record specs/trt-support-agent-baseline.agent.yaml --project-root .
expect_exit 0 python -m trajectly run specs/trt-support-agent-baseline.agent.yaml --project-root .
expect_exit 1 python -m trajectly run specs/trt-support-agent-regression.agent.yaml --project-root .

python -m trajectly record specs/trt-support-agent-determinism-break.agent.yaml --project-root .
expect_exit 1 python -m trajectly run specs/trt-support-agent-determinism-break.agent.yaml --project-root .

python -m trajectly record specs/trt-support-agent-determinism-fix.agent.yaml --project-root .
expect_exit 0 python -m trajectly run specs/trt-support-agent-determinism-fix.agent.yaml --project-root .

echo "Support escalation demo verification succeeded."
