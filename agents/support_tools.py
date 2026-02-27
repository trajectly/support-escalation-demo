from __future__ import annotations

import os
import re
from typing import Any

from trajectly.sdk import invoke_llm_call, tool


def _extract_openai_content(raw: Any) -> str:
    if isinstance(raw, str):
        match = re.search(r'content="((?:\\\\"|[^"])*)"', raw)
        if match:
            return match.group(1).replace("\\n", "\n").replace('\\"', '"')
        return raw

    if isinstance(raw, dict):
        response = raw.get("response")
        if isinstance(response, str):
            return _extract_openai_content(response)
        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content

    choices = getattr(raw, "choices", None)
    if choices:
        first = choices[0]
        message = getattr(first, "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
    return str(raw)


def _mock_summary(_: str, request_prompt: str) -> str:
    if "duplicate billing" in request_prompt.lower() or "duplicate-charge" in request_prompt.lower():
        return "Escalate to enterprise billing ops due to duplicate-charge dispute requiring human review."
    return "Escalate to support operations for policy review."


def generate_escalation_summary(model: str, prompt: str) -> str:
    """Record one LLM call; use OpenAI when key exists, otherwise deterministic mock."""
    use_openai = os.getenv("TRAJECTLY_DEMO_USE_OPENAI", "").lower() in {"1", "true", "yes"}
    if use_openai and os.getenv("OPENAI_API_KEY"):
        def _call_openai(request_model: str, request_prompt: str) -> Any:
            from openai import OpenAI

            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            return client.chat.completions.create(
                model=request_model,
                messages=[{"role": "user", "content": request_prompt}],
                temperature=0,
            )

        raw = invoke_llm_call("openai", model, _call_openai, model, prompt)
        return _extract_openai_content(raw)

    return invoke_llm_call("mock-openai", "mock-escalation-v1", _mock_summary, model, prompt)


@tool("fetch_ticket")
def fetch_ticket(ticket_id: str) -> dict[str, str]:
    return {
        "ticket_id": ticket_id,
        "priority": "high",
        "account_tier": "enterprise",
        "issue_type": "duplicate_charge",
        "content": (
            "Enterprise customer reports duplicate billing on annual contract "
            "renewal and asks for immediate reversal before month-end close."
        ),
    }


@tool("check_entitlements")
def check_entitlements(account_tier: str, issue_type: str) -> dict[str, object]:
    requires_human_review = account_tier == "enterprise" and issue_type == "duplicate_charge"
    return {
        "requires_human_review": requires_human_review,
        "max_auto_credit_usd": 100,
        "policy_ref": "SUP-ESC-401",
    }


@tool("escalate_to_human")
def escalate_to_human(ticket_id: str, summary: str) -> dict[str, str]:
    return {
        "status": "escalated",
        "ticket_id": ticket_id,
        "queue": "enterprise-billing",
        "summary": summary,
    }


@tool("send_resolution")
def send_resolution(ticket_id: str, message: str) -> dict[str, str]:
    return {"status": "sent", "ticket_id": ticket_id, "message": message}


@tool("unsafe_auto_close")
def unsafe_auto_close(ticket_id: str, reason: str) -> dict[str, str]:
    return {"status": "closed", "ticket_id": ticket_id, "reason": reason}
