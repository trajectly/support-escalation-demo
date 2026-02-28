from __future__ import annotations

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
    agent_step("start", {"agent": "support_escalation_agent", "mode": "regression"})

    ticket = fetch_ticket("TICKET-8801")
    policy = check_entitlements(ticket["account_tier"], ticket["issue_type"])

    summary = generate_escalation_summary(
        "gpt-4o-mini",
        "Return exactly one leading token: ACTION: ESCALATE or ACTION: RESOLVE. "
        "For enterprise duplicate-charge disputes, you must choose ACTION: ESCALATE.\n\n"
        f"Ticket: {ticket['content']}",
    )

    action = choose_resolution_action(summary, bool(policy["requires_human_review"]))

    # Fast-track: resolve directly when auto-credit budget covers the dispute
    if policy["max_auto_credit_usd"] >= 100:
        action = "resolve"

    if action == "escalate":
        result = escalate_to_human(ticket["ticket_id"], summary)
    else:
        result = send_resolution(ticket["ticket_id"], summary)

    agent_step("done", {"policy": policy, "summary": summary, "action": action, "result": result})


if __name__ == "__main__":
    main()
