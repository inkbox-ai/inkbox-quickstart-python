"""
src/env_config.py

Centralized environment configuration.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Env class

class EnvConfig():
    """
    Centralized configuration for environment variables.
    """

    # Inkbox signing

    # Webhook signing secret. Required when INKBOX_REQUIRE_SIGNATURE=true
    # (the default). Can be left unset in dev if you disable verification.
    INKBOX_SIGNING_KEY: str | None = os.getenv("INKBOX_SIGNING_KEY")

    # When true (default), the /webhook HTTP endpoint and the
    # /phone/media/ws WebSocket handshake both reject requests that
    # lack a valid X-Inkbox-Signature. Set to "false" for local testing
    # only.
    INKBOX_REQUIRE_SIGNATURE: bool = os.getenv(
        "INKBOX_REQUIRE_SIGNATURE", "true",
    ).strip().lower() in {"1", "true", "yes", "on"}


    # Webhook server

    LISTEN_PORT: int = int(os.getenv("LISTEN_PORT", "8080"))


    # Phone webhook behavior

    # If true, incoming_call webhooks respond with {"action": "answer"} (default true)
    INKBOX_PHONE_AUTO_ANSWER: bool = os.getenv(
        "INKBOX_PHONE_AUTO_ANSWER", "true",
    ).strip().lower() in {"1", "true", "yes", "on"}

    # WebSocket URL Inkbox should connect to for live call media.
    # Handed back in the /webhook incoming-call response body so Inkbox
    # knows where to open the media session. Leave unset to let Inkbox
    # fall back to the phone number's default client_websocket_url.
    INKBOX_PHONE_CLIENT_WEBSOCKET_URL: str = os.getenv(
        "INKBOX_PHONE_CLIENT_WEBSOCKET_URL", "",
    )
