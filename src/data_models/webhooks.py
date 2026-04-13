"""
src/data_models/webhooks.py

Pydantic models describing the shapes Inkbox POSTs to this server's
``/webhook`` endpoint.

These exist as documentation-in-code: you can read one file to know
exactly what JSON will hit your endpoint, and the FastAPI app in
``server.py`` uses these same models to validate and parse incoming
bodies. Keep in sync with the Inkbox webhook reference docs.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# Enums ________________________________________________________________________________________


class MailWebhookEventType(StrEnum):
    """
    Mail webhook event types delivered to a mailbox's configured ``webhook_url``.

    Attributes:
        MESSAGE_RECEIVED: An inbound email was delivered to the mailbox.
        MESSAGE_SENT: An outbound email was accepted for delivery.
        MESSAGE_DELIVERED: Downstream delivery to the recipient succeeded.
        MESSAGE_BOUNCED: Outbound message bounced or received a complaint.
        MESSAGE_FAILED: Outbound message failed after all retry attempts.
    """
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_BOUNCED = "message.bounced"
    MESSAGE_FAILED = "message.failed"


class MessageDirection(StrEnum):
    """Whether a message was received by or sent from a mailbox."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(StrEnum):
    """
    Delivery-lifecycle status of a mail message as it appears in webhooks.

    Attributes:
        RECEIVED: Inbound message successfully ingested.
        SENT: Outbound message accepted for delivery.
        DELIVERED: Recipient mail server confirmed delivery.
        BOUNCED: Recipient mail server rejected the message.
        FAILED: Outbound send permanently failed.
    """
    RECEIVED = "received"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


class CallDirection(StrEnum):
    """Direction of a phone call relative to the Inkbox number."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(StrEnum):
    """
    Lifecycle status of a phone call as it appears in webhooks.

    Attributes:
        INITIATED: Call record created, dialing not yet started.
        RINGING: Call is ringing.
        ANSWERED: Call was answered and audio is flowing.
        COMPLETED: Call ended normally.
        FAILED: Call failed (network, signalling, etc.).
        CANCELED: Call was canceled before being answered.
    """
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class HangupReason(StrEnum):
    """
    Reason a call ended.

    Attributes:
        LOCAL: Your side hung up.
        REMOTE: The remote party hung up.
        MAX_DURATION: Call hit the configured maximum duration.
        VOICEMAIL: Call was routed to voicemail.
        REJECTED: Call was rejected before being answered.
    """
    LOCAL = "local"
    REMOTE = "remote"
    MAX_DURATION = "max_duration"
    VOICEMAIL = "voicemail"
    REJECTED = "rejected"


# Rate limit snapshot __________________________________________________________________________


class RateLimitInfo(BaseModel):
    """
    Organization-level phone rate-limit snapshot, included on some
    incoming-call webhooks.

    Attributes:
        calls_used: Number of calls counted against the rolling 24h window.
        calls_remaining: Remaining calls in the current window.
        calls_limit: Hard ceiling for calls in the window.
        minutes_used: Number of call-minutes consumed in the window.
        minutes_remaining: Remaining call-minutes in the window.
        minutes_limit: Hard ceiling for call-minutes in the window.
    """
    calls_used: int
    calls_remaining: int
    calls_limit: int
    minutes_used: float
    minutes_remaining: float
    minutes_limit: float


# Mail webhook payloads ________________________________________________________________________


class MailWebhookMessageData(BaseModel):
    """
    Message payload nested under ``data.message`` in mail webhooks.

    Attributes:
        id: Unique message identifier.
        mailbox_id: Owning mailbox identifier.
        thread_id: Mailbox-local thread identifier, if resolved.
        message_id: RFC 5322 Message-ID header value, if known.
        from_address: Sender email address.
        to_addresses: Primary recipient addresses.
        cc_addresses: CC recipient addresses, if any.
        subject: Message subject line.
        snippet: Short preview of the plain-text body.
        direction: ``inbound`` or ``outbound``.
        status: Current message delivery-lifecycle status.
        has_attachments: Whether the message has attachments.
        created_at: Timestamp when the message record was created.
    """
    id: UUID
    mailbox_id: UUID
    thread_id: UUID | None = None
    message_id: str | None = None
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str] | None = None
    subject: str | None = None
    snippet: str | None = None
    direction: MessageDirection
    status: MessageStatus
    has_attachments: bool = False
    created_at: datetime | None = None


class MailWebhookData(BaseModel):
    """Wrapper object under the mail webhook ``data`` field."""
    message: MailWebhookMessageData


class MailWebhookPayload(BaseModel):
    """
    Envelope payload sent for mailbox webhooks.

    Attributes:
        event_type: The mail event that triggered this webhook.
        timestamp: ISO 8601 timestamp of when the event occurred.
        data: Wrapped event payload.
    """
    event_type: MailWebhookEventType = Field(
        description="The type of mail event that triggered this webhook.",
    )
    timestamp: datetime = Field(
        description="ISO 8601 timestamp of when the event occurred.",
    )
    data: MailWebhookData


# Phone webhook payloads _______________________________________________________________________


class PhoneIncomingTextData(BaseModel):
    """
    Text message payload nested under ``data.text_message`` in SMS/MMS webhooks.

    Attributes:
        id: Unique text message identifier.
        local_phone_number: E.164 Inkbox-side phone number.
        remote_phone_number: E.164 remote party phone number.
        direction: Always ``inbound`` for this webhook.
        text: Plain-text message body, if any.
        created_at: Timestamp when the message was received.
    """
    id: UUID
    local_phone_number: str
    remote_phone_number: str
    direction: Literal[CallDirection.INBOUND] = CallDirection.INBOUND
    text: str | None = None
    created_at: datetime


class PhoneIncomingTextWebhookData(BaseModel):
    """Wrapper object under the incoming-text webhook ``data`` field."""
    text_message: PhoneIncomingTextData


class PhoneIncomingTextWebhookPayload(BaseModel):
    """
    Envelope payload sent for inbound SMS/MMS webhooks.

    Attributes:
        event_type: Always ``text.received`` for this webhook.
        timestamp: ISO 8601 timestamp of when the event occurred.
        data: Wrapped event payload.
    """
    event_type: Literal["text.received"] = Field(
        default="text.received",
        description="The type of text event that triggered this webhook.",
    )
    timestamp: datetime = Field(
        description="ISO 8601 timestamp of when the event occurred.",
    )
    data: PhoneIncomingTextWebhookData


class PhoneIncomingCallWebhookPayload(BaseModel):
    """
    Flat payload sent to incoming-call webhook endpoints.

    Unlike mail and text webhooks, incoming-call webhooks are delivered
    as a flat object with no ``event_type`` / ``data`` envelope. Your
    endpoint must respond with an ``IncomingCallActionResponse`` body.

    Attributes:
        id: Unique phone call identifier.
        phone_number_id: Identifier of the Inkbox phone number receiving the call.
        local_phone_number: E.164 phone number receiving the call.
        remote_phone_number: E.164 caller phone number.
        direction: Always ``inbound`` for this webhook.
        status: Current call lifecycle status.
        client_websocket_url: Negotiated client WebSocket URL, if any.
        use_inkbox_tts: Whether Inkbox should provide TTS for the call.
        use_inkbox_stt: Whether Inkbox should provide STT for the call.
        hangup_reason: Why the call ended, if already known.
        started_at: Timestamp when the call was answered.
        ended_at: Timestamp when the call ended.
        created_at: Timestamp when the call record was created.
        updated_at: Timestamp when the call record was last updated.
        rate_limit: Organization rate-limit snapshot, included on some calls.
    """
    id: UUID
    phone_number_id: UUID | None = None
    local_phone_number: str
    remote_phone_number: str
    direction: Literal[CallDirection.INBOUND] = CallDirection.INBOUND
    status: CallStatus
    client_websocket_url: str | None = None
    use_inkbox_tts: bool | None = None
    use_inkbox_stt: bool | None = None
    hangup_reason: HangupReason | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    rate_limit: RateLimitInfo | None = None


# Response body this server returns to Inkbox _________________________________________________


class IncomingCallActionResponse(BaseModel):
    """
    JSON body returned in response to an ``incoming_call`` webhook.

    Attributes:
        action: ``answer`` accepts the call; ``reject`` declines it.
        client_websocket_url: URL Inkbox should connect to for live call
            media (only honored when ``action == "answer"``). If omitted,
            Inkbox falls back to the phone number's default
            ``client_websocket_url``.
    """
    action: Literal["answer", "reject"]
    client_websocket_url: str | None = None
