"""Configure the tunnel identity without replacing unrelated subscriptions."""

from inkbox import Inkbox
from inkbox.exceptions import InkboxAPIError

RECEIVED_EVENTS = ["message.received", "text.received"]


def ensure_received_subscription(client: Inkbox, identity_id, url: str) -> None:
    for _ in range(3):
        rows = client.webhooks.subscriptions.list(agent_identity_id=identity_id)
        matches = [row for row in rows if row.url == url]
        # This receiver uses signatures, not bearer tokens. Never take over a
        # distinct configuration or guess between rows with different contexts.
        if len(matches) > 1 or any(
            (row.agent_identity_id or row.owner_identity_id) != identity_id
            or row.has_auth_token
            or row.auth_token is not None
            for row in matches
        ):
            raise RuntimeError(
                "Webhook destination has an ambiguous owner or configuration; reconcile it before startup."
            )
        match = matches[0] if matches else None
        try:
            if match is None:
                client.webhooks.subscriptions.create(
                    agent_identity_id=identity_id,
                    url=url,
                    event_types=RECEIVED_EVENTS,
                )
            else:
                events = list(dict.fromkeys([*match.event_types, *RECEIVED_EVENTS]))
                if len(events) == len(set(match.event_types)):
                    return
                if type(match.revision) is not int or match.revision < 1:
                    raise RuntimeError(
                        "Webhook revision is unavailable; update the API before reconciling subscriptions."
                    )
                client.webhooks.subscriptions.update(
                    match.id,
                    event_types=events,
                    expected_revision=match.revision,
                )
            return
        except InkboxAPIError as exc:
            if exc.status_code != 409:
                raise
    raise RuntimeError(
        "Webhook configuration changed repeatedly; retry startup after concurrent edits finish."
    )


def patch_identity_to_tunnel(
    client: Inkbox, public_host: str, identity_handle: str
) -> None:
    identity = client.get_identity(identity_handle)
    webhook_url = f"https://{public_host}/webhook"
    ensure_received_subscription(client, identity.id, webhook_url)
    # Incoming-call responses control routing and remain separate from events.
    if identity.phone_number or identity.imessage_enabled:
        identity.set_incoming_call_action(
            incoming_call_webhook_url=webhook_url,
            client_websocket_url=f"wss://{public_host}/phone/media/ws",
            incoming_call_action="webhook",
        )
