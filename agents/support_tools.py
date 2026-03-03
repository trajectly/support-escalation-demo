from __future__ import annotations

from datetime import datetime, timezone
import os
import re
from typing import Any

def extract_openai_content(raw: Any) -> str:
    if isinstance(raw, str):
        match = re.search(r'content="((?:\\\\"|[^"])*)"', raw)
        if match:
            return match.group(1).replace("\\n", "\n").replace('\\"', '"')
        return raw

    if isinstance(raw, dict):
        response = raw.get("response")
        if isinstance(response, str):
            return extract_openai_content(response)
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


def mock_summary(_: str, request_prompt: str) -> str:
    normalized_prompt = request_prompt.lower()
    if "prefer action: resolve" in normalized_prompt or "favor one-touch resolution" in normalized_prompt:
        return "ACTION: RESOLVE - Duplicate-charge appears already handled; send customer resolution."
    if "duplicate billing" in normalized_prompt or "duplicate-charge" in normalized_prompt:
        return "ACTION: ESCALATE - Enterprise duplicate-charge dispute requires billing specialist review."
    return "ACTION: RESOLVE - Low-risk request can receive standard resolution."


def should_use_openai() -> bool:
    """Return true when demo is configured to use live OpenAI calls."""
    use_openai = os.getenv("TRAJECTLY_DEMO_USE_OPENAI", "").lower() in {"1", "true", "yes"}
    return use_openai and bool(os.getenv("OPENAI_API_KEY"))


def call_openai_chat(model: str, prompt: str) -> str:
    """Execute one live OpenAI chat completion and return plain text content."""
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return extract_openai_content(response)


def generate_escalation_summary(model: str, prompt: str, *, use_openai: bool) -> str:
    """Return summary text from live OpenAI or deterministic mock."""
    if use_openai:
        return call_openai_chat(model, prompt)
    return mock_summary(model, prompt)


def choose_resolution_action(summary: str, requires_human_review: bool) -> str:
    normalized_summary = summary.upper()
    if "ACTION: RESOLVE" in normalized_summary:
        return "resolve"
    if "ACTION: ESCALATE" in normalized_summary:
        return "escalate"
    return "escalate" if requires_human_review else "resolve"


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


def check_entitlements(account_tier: str, issue_type: str) -> dict[str, object]:
    requires_human_review = account_tier == "enterprise" and issue_type == "duplicate_charge"
    return {
        "requires_human_review": requires_human_review,
        "max_auto_credit_usd": 100,
        "policy_ref": "SUP-ESC-401",
    }


def escalate_to_human(ticket_id: str, summary: str) -> dict[str, str]:
    return {
        "status": "escalated",
        "ticket_id": ticket_id,
        "queue": "enterprise-billing",
        "summary": summary,
    }


def send_resolution(ticket_id: str, message: str) -> dict[str, str]:
    return {"status": "sent", "ticket_id": ticket_id, "message": message}


def unsafe_auto_close(ticket_id: str, reason: str) -> dict[str, str]:
    return {"status": "closed", "ticket_id": ticket_id, "reason": reason}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
