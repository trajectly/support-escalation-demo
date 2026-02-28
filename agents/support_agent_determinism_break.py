from __future__ import annotations

from datetime import datetime, timezone

from trajectly.sdk import agent_step

from agents.support_tools import (
    check_entitlements,
    choose_resolution_action,
    escalate_to_human,
    fetch_ticket,
    generate_escalation_summary,
    send_resolution,
)


def main() -> None:
    agent_step("start", {"agent": "support_escalation_agent", "mode": "determinism_break"})

    ticket = fetch_ticket("TICKET-8801")
    policy = check_entitlements(ticket["account_tier"], ticket["issue_type"])
    observed_clock = datetime.now(timezone.utc).isoformat()

    summary = generate_escalation_summary(
        "gpt-4o-mini",
        "Return exactly one leading token: ACTION: ESCALATE or ACTION: RESOLVE. "
        "For enterprise duplicate-charge disputes, you must choose ACTION: ESCALATE.\n\n"
        f"Observed clock: {observed_clock}\n"
        f"Ticket: {ticket['content']}",
    )

    action = choose_resolution_action(summary, bool(policy["requires_human_review"]))
    if action == "escalate":
        result = escalate_to_human(ticket["ticket_id"], summary)
    else:
        result = send_resolution(ticket["ticket_id"], summary)

    agent_step(
        "done",
        {"policy": policy, "summary": summary, "action": action, "result": result, "clock": observed_clock},
    )


if __name__ == "__main__":
    main()
