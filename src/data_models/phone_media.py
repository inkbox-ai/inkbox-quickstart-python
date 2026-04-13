"""
src/data_models/phone_media.py

Pydantic models describing the phone media WebSocket protocol Inkbox
uses to stream live call events to this server during an answered call.

Wire format:

    Server (us)  ←  Inkbox          handshake (HTTP upgrade)
      - Request headers include ``X-Call-Context: <json>`` and — if your
        org has a signing key configured — ``X-Inkbox-Request-ID``,
        ``X-Inkbox-Timestamp``, ``X-Inkbox-Signature`` computed over
        ``{request_id}.{timestamp}.{X-Call-Context}``.
      - We accept the handshake and reply with
        ``X-Use-Inkbox-Text-To-Speech: true`` and
        ``X-Use-Inkbox-Speech-To-Text: true`` to opt into Inkbox-managed
        TTS/STT.

    Server (us)  ←  Inkbox          platform → client JSON frames
      - ``start``       — audio pipeline is ready.
      - ``stop``        — call ended.
      - ``media``       — base64 PCMU audio frame.
      - ``transcript``  — STT output (partial or final).
      - ``barge_in``    — caller started speaking over in-flight TTS.

    Server (us)  →  Inkbox          client → platform JSON frames
      - ``text``        — text for Inkbox TTS to synthesize and play.
                          Streaming form: ``{"event":"text","delta":"..."}``
                          followed by ``{"event":"text","done":true}``.
      - ``media``       — base64 PCMU audio frame (if your client does TTS).
      - ``audio_done``  — marker that your outbound audio is finished.
      - ``clear``       — drop any queued outbound audio (e.g. after barge-in).
      - ``transcript``  — STT output from your side (if your client does STT).
      - ``stop``        — hang up the call from your side.

Only the events this sample actually uses (``start``, ``stop``,
``barge_in``, ``transcript``, and outbound ``text``) are modelled
below. Add models for the rest if you extend this file.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# Handshake ____________________________________________________________________________________


class CallContext(BaseModel):
    """
    Parsed contents of the ``X-Call-Context`` request header Inkbox sends
    on the WebSocket handshake.

    Attributes:
        call_id: Inkbox call ID for the current session.
        phone_number: Local (Inkbox-side) phone number on the call.
        direction: Call direction (``"inbound"`` or ``"outbound"``).
    """
    call_id: str = ""
    phone_number: str = ""
    direction: str = ""


# Handshake response headers the server emits. Declaring these as
# constants makes the TTS/STT opt-in contract explicit.
HANDSHAKE_RESPONSE_HEADERS: dict[str, str] = {
    "X-Use-Inkbox-Text-To-Speech": "true",
    "X-Use-Inkbox-Speech-To-Text": "true",
}


# Inbound events (Inkbox → us) _________________________________________________________________


class StartEventStart(BaseModel):
    """Nested ``start`` object on the inbound ``start`` event."""
    call_control_id: str | None = None


class StartEvent(BaseModel):
    """
    Emitted once when the call audio pipeline is ready.

    Attributes:
        event: Discriminator literal ``"start"``.
        stream_id: Inkbox-assigned stream identifier for this session.
        start: Nested object carrying ``call_control_id``.
    """
    event: Literal["start"] = "start"
    stream_id: str | None = None
    start: StartEventStart | None = None


class StopEvent(BaseModel):
    """
    Emitted when the call ends.

    Attributes:
        event: Discriminator literal ``"stop"``.
        reason: Human-readable reason the call ended (e.g. ``"agent_hang_up"``).
    """
    event: Literal["stop"] = "stop"
    reason: str | None = None


class BargeInEvent(BaseModel):
    """
    Emitted when the caller starts speaking over in-flight TTS.
    Clients should drop any pending outbound ``text`` output.

    Attributes:
        event: Discriminator literal ``"barge_in"``.
        trigger: What triggered the barge-in (e.g. ``"caller_speech"``).
        text: The caller text that triggered the barge-in, if available.
        tts_interrupted: True if the platform interrupted in-flight TTS.
        turn_id: Conversation turn identifier the barge-in belongs to.
    """
    event: Literal["barge_in"] = "barge_in"
    trigger: str | None = None
    text: str | None = None
    tts_interrupted: bool | None = None
    turn_id: str | None = None


class TranscriptEvent(BaseModel):
    """
    Speech-to-text result emitted by Inkbox STT.

    Partial (``is_final = False``) chunks arrive as the caller speaks;
    finalize on ``is_final = True`` before responding.

    Attributes:
        event: Discriminator literal ``"transcript"``.
        text: Transcribed utterance text.
        is_final: ``True`` when this is the final chunk for the utterance.
        turn_id: Conversation turn identifier.
    """
    event: Literal["transcript"] = "transcript"
    text: str = ""
    is_final: bool = False
    turn_id: str | None = None


# Outbound events (us → Inkbox) ________________________________________________________________


class TextEvent(BaseModel):
    """
    Outbound text frame for Inkbox TTS to synthesize and play back.

    The platform accepts two shapes:

    1. Streaming deltas: ``{"event":"text","delta":"Hello"}`` followed
       by zero or more additional ``delta`` frames, terminated by a
       ``{"event":"text","done":true}`` frame.
    2. Single-shot: one ``delta`` frame with the full text, then a
       ``done`` frame.

    Attributes:
        event: Discriminator literal ``"text"``.
        delta: Next chunk of text to speak (omit on the final frame).
        done: ``True`` on the frame that closes the utterance.
    """
    event: Literal["text"] = "text"
    delta: str | None = None
    done: bool | None = None
