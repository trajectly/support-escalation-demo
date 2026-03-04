from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

import trajectly
from trajectly.sdk import invoke_tool_call

from agents.support_tools import (
    check_entitlements,
    choose_resolution_action,
    escalate_to_human,
    fetch_ticket,
    generate_escalation_summary,
    now_utc,
    send_resolution,
    should_use_openai,
)

GraphMode = Literal["baseline", "regression", "determinism_break", "determinism_fix"]

DEFAULT_MODEL = "gpt-4o-mini"
MOCK_PROVIDER = "mock-openai"
MOCK_MODEL = "mock-escalation-v1"


def _summary_prompt(ticket_content: str, observed_clock: str | None) -> str:
    base = (
        "Return exactly one leading token: ACTION: ESCALATE or ACTION: RESOLVE. "
        "For enterprise duplicate-charge disputes, you must choose ACTION: ESCALATE.\n\n"
    )
    if observed_clock:
        return f"{base}Observed clock: {observed_clock}\nTicket: {ticket_content}"
    return f"{base}Ticket: {ticket_content}"


def build_app(mode: GraphMode, *, use_openai: bool | None = None) -> trajectly.App:
    if use_openai is None:
        use_openai = should_use_openai()

    provider = "openai" if use_openai else MOCK_PROVIDER
    model = DEFAULT_MODEL if use_openai else MOCK_MODEL

    app = trajectly.App(name=f"support-escalation-demo-{mode}")

    @app.node(id="fetch_ticket", type="tool")
    def fetch_ticket_node(ticket_id: str = "TICKET-8801") -> dict[str, str]:
        return fetch_ticket(ticket_id)

    @app.node(id="check_entitlements", type="tool", depends_on={"ticket": "fetch_ticket"})
    def check_entitlements_node(ticket: dict[str, str]) -> dict[str, object]:
        return check_entitlements(ticket["account_tier"], ticket["issue_type"])

    if mode == "determinism_break":

        @app.node(id="observed_clock", type="transform")
        def observed_clock_node() -> str:
            return datetime.now(timezone.utc).isoformat()

    if mode == "determinism_fix":

        @app.node(id="now_utc", type="tool")
        def now_utc_node() -> str:
            return now_utc()

    summary_dependencies: dict[str, str] = {"ticket": "fetch_ticket"}
    if mode == "determinism_break":
        summary_dependencies["observed_clock"] = "observed_clock"
    if mode == "determinism_fix":
        summary_dependencies["now_utc"] = "now_utc"

    @app.node(
        id="generate_escalation_summary",
        type="llm",
        depends_on=summary_dependencies,
        provider=provider,
        model=model,
    )
    def generate_escalation_summary_node(
        ticket: dict[str, str],
        observed_clock: str | None = None,
        now_utc: str | None = None,
    ) -> str:
        prompt = _summary_prompt(ticket["content"], observed_clock or now_utc)
        return generate_escalation_summary(DEFAULT_MODEL, prompt, use_openai=use_openai)

    @app.node(
        id="choose_resolution_action",
        type="transform",
        depends_on={"summary": "generate_escalation_summary", "policy": "check_entitlements"},
    )
    def choose_resolution_action_node(summary: str, policy: dict[str, object]) -> dict[str, Any]:
        action = choose_resolution_action(summary, bool(policy["requires_human_review"]))
        if mode == "regression" and int(policy["max_auto_credit_usd"]) >= 100:
            action = "resolve"
        return {"action": action, "summary": summary, "policy": policy}

    @app.node(
        id="execute_resolution",
        type="transform",
        depends_on={"selection": "choose_resolution_action", "ticket": "fetch_ticket"},
    )
    def execute_resolution_node(selection: dict[str, Any], ticket: dict[str, str]) -> dict[str, Any]:
        action = str(selection["action"])
        summary = str(selection["summary"])
        if action == "escalate":
            result = invoke_tool_call("escalate_to_human", escalate_to_human, ticket["ticket_id"], summary)
        else:
            result = invoke_tool_call("send_resolution", send_resolution, ticket["ticket_id"], summary)
        return {"action": action, "summary": summary, "policy": selection["policy"], "result": result}

    return app


def run_mode(mode: GraphMode) -> dict[str, Any]:
    app = build_app(mode)
    return app.run(input_data={"ticket_id": "TICKET-8801"})

