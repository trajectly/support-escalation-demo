from __future__ import annotations

from trajectly.sdk import agent_step

from agents.support_tools import (
    check_entitlements,
    fetch_ticket,
    generate_escalation_summary,
    send_resolution,
    unsafe_auto_close,
)


def main() -> None:
    agent_step("start", {"agent": "support_escalation_agent", "mode": "regression"})

    ticket = fetch_ticket("TICKET-8801")
    policy = check_entitlements(ticket["account_tier"], ticket["issue_type"])

    summary = generate_escalation_summary(
        "gpt-4o-mini",
        "Write a one-sentence escalation note for a human billing specialist. "
        "Do not propose direct auto-closure for enterprise duplicate-charge cases.\n\n"
        f"Ticket: {ticket['content']}",
    )

    # Intentional bug for demonstration: looks like speed optimization, violates policy.
    if policy["requires_human_review"]:
        result = unsafe_auto_close(ticket["ticket_id"], summary)
    else:
        result = send_resolution(ticket["ticket_id"], summary)

    agent_step("done", {"policy": policy, "summary": summary, "result": result})


if __name__ == "__main__":
    main()
