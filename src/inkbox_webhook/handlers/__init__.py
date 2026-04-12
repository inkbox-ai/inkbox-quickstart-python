"""Webhook payload handlers.

This package is where event-domain logic lives (email today, phone + more next).
"""

from .email import is_email_event, summarize_email_payload
from .phone import build_phone_webhook_response, is_phone_event, summarize_phone_payload


def summarize_webhook_payload(payload: dict) -> str:
    """Return a domain-aware summary for a webhook payload."""
    if is_email_event(payload):
        return summarize_email_payload(payload)
    if is_phone_event(payload):
        return summarize_phone_payload(payload)
    return "Inkbox webhook received. Check the newest file in ~/openclaw-config/spool/."


def build_webhook_http_response(payload: dict, config: dict) -> dict | None:
    """Return optional JSON response body required by some webhook domains."""
    phone_response = build_phone_webhook_response(payload, config)
    if phone_response is not None:
        return phone_response
    return None
