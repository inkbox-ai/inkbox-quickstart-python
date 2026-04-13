"""
src/handlers/dispatch.py

Webhook payload dispatch across handler domains.
"""

from __future__ import annotations

from typing import Any

from handlers.email import is_email_event, summarize_email_payload
from handlers.phone import (
    build_phone_webhook_response,
    is_phone_event,
    summarize_phone_payload,
)


def summarize_webhook_payload(payload: dict[str, Any]) -> str:
    """
    Return a domain-aware one-line summary for an Inkbox webhook payload.

    Dispatches on the event family (email vs. phone) and falls back to a
    generic message when no handler claims the payload.

    Parameters:
        payload (dict[str, Any]): Parsed JSON body of the incoming webhook.

    Returns:
        str: Human-readable summary suitable for logging.
    """
    if is_email_event(payload):
        return summarize_email_payload(payload)
    if is_phone_event(payload):
        return summarize_phone_payload(payload)
    return "Inkbox webhook received (unknown event type)."


def build_webhook_http_response(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Return an optional JSON response body required by some webhook domains.

    Inkbox phone webhooks (e.g. ``incoming_call``) expect an action body in
    the HTTP response; email webhooks do not. Returns ``None`` when the
    caller should reply with a plain ``200 OK``.

    Parameters:
        payload (dict[str, Any]): Parsed JSON body of the incoming webhook.

    Returns:
        dict[str, Any] | None: JSON-serializable response body, or ``None`` if
            the webhook does not require a structured response.
    """
    phone_response = build_phone_webhook_response(payload)
    if phone_response is not None:
        return phone_response
    return None
