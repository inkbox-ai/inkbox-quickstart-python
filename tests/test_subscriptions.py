from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from inkbox.exceptions import InkboxAPIError
from subscriptions import RECEIVED_EVENTS, ensure_received_subscription, patch_identity_to_tunnel

URL = "https://example.test/webhook"


def row(**kwargs):
    return NS(
        **dict(
            dict(
                id="sub",
                agent_identity_id="identity",
                owner_identity_id="identity",
                url=URL,
                event_types=["message.received"],
                has_auth_token=False,
                auth_token=None,
                revision=3,
            ),
            **kwargs,
        )
    )


def client(rows):
    c = Mock()
    c.webhooks.subscriptions.list.return_value = rows
    return c


def test_create_without_provisioned_channels_only_configured_identity():
    c = client([])
    identity = NS(
        id="identity",
        phone_number=None,
        imessage_enabled=False,
        set_incoming_call_action=Mock(),
    )
    c.get_identity.return_value = identity
    patch_identity_to_tunnel(c, "example.test", "configured")
    c.get_identity.assert_called_once_with("configured")
    c.webhooks.subscriptions.list.assert_called_once_with(agent_identity_id="identity")
    c.webhooks.subscriptions.create.assert_called_once_with(
        agent_identity_id="identity",
        url=URL,
        event_types=["message.received", "text.received"],
    )
    identity.set_incoming_call_action.assert_not_called()
    c.mailboxes.list.assert_not_called()
    c.phone_numbers.list.assert_not_called()


def test_union_preserves_extra_events_and_context_with_revision():
    c = client(
        [
            row(event_types=["a2a.task.created", "message.received"]),
            row(id="other", url="https://other.test"),
        ]
    )
    ensure_received_subscription(c, "identity", URL)
    c.webhooks.subscriptions.update.assert_called_once_with(
        "sub",
        event_types=["a2a.task.created", "message.received", "text.received"],
        expected_revision=3,
    )
    c.webhooks.subscriptions.delete.assert_not_called()


def test_superset_is_noop():
    c = client([row(event_types=["text.received", "message.received", "call.ended"])])
    ensure_received_subscription(c, "identity", URL)
    c.webhooks.subscriptions.update.assert_not_called()


@pytest.mark.parametrize(
    "rows",
    [
        [row(), row(id="second")],
        [row(has_auth_token=True)],
        [row(auth_token="token")],
        [row(agent_identity_id="other")],
    ],
)
def test_ambiguous_configuration_fails_without_mutations(rows):
    c = client(rows)
    with pytest.raises(RuntimeError, match="ambiguous"):
        ensure_received_subscription(c, "identity", URL)
    c.webhooks.subscriptions.update.assert_not_called()
    c.webhooks.subscriptions.create.assert_not_called()
    c.webhooks.subscriptions.delete.assert_not_called()


def test_conflict_rereads_and_preserves_concurrent_added_event():
    c = client([])
    c.webhooks.subscriptions.list.side_effect = [
        [row()],
        [row(revision=4, event_types=["message.received", "call.ended"])],
    ]
    c.webhooks.subscriptions.update.side_effect = [
        InkboxAPIError(409, "revision changed"),
        None,
    ]
    ensure_received_subscription(c, "identity", URL)
    assert c.webhooks.subscriptions.list.call_count == 2
    assert c.webhooks.subscriptions.update.call_args.kwargs == dict(
        event_types=["message.received", "call.ended", "text.received"],
        expected_revision=4,
    )


def test_create_conflict_rereads_existing_superset():
    c = client([])
    c.webhooks.subscriptions.list.side_effect = [
        [],
        [row(event_types=["message.received", "text.received"])],
    ]
    c.webhooks.subscriptions.create.side_effect = InkboxAPIError(409, "overlap")
    ensure_received_subscription(c, "identity", URL)
    c.webhooks.subscriptions.update.assert_not_called()


def test_conflict_retries_are_bounded():
    c = client([row()])
    c.webhooks.subscriptions.update.side_effect = InkboxAPIError(
        409, "revision changed"
    )
    with pytest.raises(RuntimeError, match="repeatedly"):
        ensure_received_subscription(c, "identity", URL)
    assert c.webhooks.subscriptions.list.call_count == 3


def test_non_conflict_error_is_not_retried():
    c = client([row()])
    c.webhooks.subscriptions.update.side_effect = InkboxAPIError(401, "unauthorized")
    with pytest.raises(InkboxAPIError):
        ensure_received_subscription(c, "identity", URL)
    assert c.webhooks.subscriptions.list.call_count == 1


def test_incoming_call_action_remains_separate():
    c = client([])
    identity = NS(
        id="identity",
        phone_number=None,
        imessage_enabled=True,
        set_incoming_call_action=Mock(),
    )
    c.get_identity.return_value = identity
    patch_identity_to_tunnel(c, "example.test", "configured")
    identity.set_incoming_call_action.assert_called_once_with(
        incoming_call_webhook_url=URL,
        client_websocket_url="wss://example.test/phone/media/ws",
        incoming_call_action="webhook",
    )


def test_legacy_split_coverage_is_adopted_without_replacement():
    c = client([row(agent_identity_id=None, event_types=["message.received"]),
                row(id="text", agent_identity_id=None, event_types=["text.received"],
                    context_config={"email": None, "texts": None, "calls": None})])
    ensure_received_subscription(c, "identity", URL)
    c.webhooks.subscriptions.update.assert_not_called()
    c.webhooks.subscriptions.create.assert_not_called()
    c.webhooks.subscriptions.delete.assert_not_called()


def test_different_legacy_contexts_remain_ambiguous():
    c = client([row(event_types=["message.received"], context_config={"email": {"mode": "count", "count": 2}}),
                row(id="text", event_types=["text.received"], context_config=None)])
    with pytest.raises(RuntimeError, match="ambiguous"):
        ensure_received_subscription(c, "identity", URL)
    c.webhooks.subscriptions.update.assert_not_called()


def test_deleted_during_update_rereads_merged_survivor():
    c = client([])
    c.webhooks.subscriptions.list.side_effect = [[row()], [row(id="survivor", event_types=RECEIVED_EVENTS)]]
    c.webhooks.subscriptions.update.side_effect = InkboxAPIError(404, "deleted")
    ensure_received_subscription(c, "identity", URL)
    assert c.webhooks.subscriptions.list.call_count == 2
    c.webhooks.subscriptions.create.assert_not_called()


def test_capacity_conflict_is_actionable_without_retries():
    c = client([])
    c.webhooks.subscriptions.create.side_effect = InkboxAPIError(409, "Owner already has 20 active webhook subscriptions (max 20). Delete one before creating another.")
    with pytest.raises(InkboxAPIError, match="max 20"):
        ensure_received_subscription(c, "identity", URL)
    assert c.webhooks.subscriptions.list.call_count == 1
