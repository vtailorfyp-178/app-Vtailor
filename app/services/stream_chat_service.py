"""Stream Chat server-side helper."""

from typing import Any

from stream_chat import StreamChat  # type: ignore

from app.core.config import get_settings

_client: StreamChat | None = None


def get_stream_client() -> StreamChat:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.STREAM_API_KEY or not settings.STREAM_API_SECRET:
            raise RuntimeError(
                "STREAM_API_KEY and STREAM_API_SECRET must be set in .env. "
                "Get them from https://dashboard.getstream.io/"
            )
        _client = StreamChat(
            api_key=settings.STREAM_API_KEY.strip(),
            api_secret=settings.STREAM_API_SECRET.strip(),
        )
    return _client


def is_stream_configured() -> bool:
    settings = get_settings()
    return bool(settings.STREAM_API_KEY and settings.STREAM_API_SECRET)


def create_stream_user_token(user_id: str) -> str:
    """Generate a Stream user token for the given user_id."""
    return get_stream_client().create_token(user_id)


def upsert_stream_user(user_id: str, name: str | None = None, role: str | None = None, image: str | None = None, phone: str | None = None, email: str | None = None) -> None:
    """Create or update a Stream user profile (fire-and-forget; errors are logged only)."""
    payload: dict[str, Any] = {"id": user_id}
    if name:
        payload["name"] = name
    if role:
        payload["role"] = "user"
        payload["custom_role"] = role
    if image:
        payload["image"] = image
    if phone:
        payload["phone"] = phone
    if email:
        payload["email"] = email
    get_stream_client().update_user(payload)


def get_or_create_channel(tailor_id: str, customer_id: str) -> dict[str, Any]:
    """
    Return (creating if needed) a 1-to-1 Stream channel between tailor and customer.
    Channel id is deterministic: sorted so it never duplicates.
    """
    members = sorted([tailor_id, customer_id])
    channel_id = f"{members[0]}--{members[1]}"
    client = get_stream_client()

    # Ensure both users exist in Stream — required before channel.create()
    try:
        client.update_users([
            {"id": tailor_id},
            {"id": customer_id},
        ])
    except Exception:
        pass  # best-effort; channel.create may still succeed if users already exist

    # Pass only members in data — created_by is set via channel.create(user_id)
    # Do NOT include created_by_id here; Stream rejects having both.
    channel = client.channel(
        "messaging",
        channel_id,
        {
            "members": [tailor_id, customer_id],
        },
    )
    response = channel.create(customer_id)
    return {
        "channel_id": channel_id,
        "channel_type": "messaging",
        "cid": f"messaging:{channel_id}",
        "members": [tailor_id, customer_id],
        "channel": response.get("channel", {}),
    }
