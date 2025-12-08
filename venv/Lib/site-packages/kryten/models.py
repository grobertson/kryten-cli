"""Event and data models for kryten-py library."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class RawEvent(BaseModel):
    """Raw CyTube event with metadata.

    Immutable container for unparsed Socket.IO events with timestamps,
    correlation IDs, and channel information for NATS publishing and
    distributed tracing.

    Attributes:
        event_name: Socket.IO event name (e.g., "chatMsg", "addUser")
        payload: Raw Socket.IO event data as dictionary
        channel: CyTube channel name
        domain: CyTube server domain (e.g., "cytu.be")
        timestamp: UTC ISO 8601 timestamp with microseconds
        correlation_id: UUID4 for distributed tracing

    Examples:
        >>> event = RawEvent(
        ...     event_name="chatMsg",
        ...     payload={"user": "bob", "msg": "hello"},
        ...     channel="lounge",
        ...     domain="cytu.be"
        ... )
        >>> json_bytes = event.to_bytes()
    """

    event_name: str = Field(..., description="Socket.IO event name")
    payload: dict[str, Any] | Any = Field(..., description="Raw event data")
    channel: str = Field(..., description="Channel name")
    domain: str = Field(..., description="CyTube domain")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp",
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID for tracing",
    )

    model_config = {"frozen": True}

    def to_bytes(self) -> bytes:
        """Serialize to UTF-8 encoded JSON bytes.

        Returns:
            UTF-8 encoded JSON bytes suitable for NATS publishing.
        """
        return self.model_dump_json().encode("utf-8")


class ChatMessageEvent(BaseModel):
    """Chat message event.

    Attributes:
        username: Username of sender
        message: Chat message text
        timestamp: Message timestamp
        rank: User rank (0=guest, 1=member, etc.)
        channel: Channel name
        domain: Domain name
        correlation_id: Trace ID
    """

    username: str = Field(..., description="Username of sender")
    message: str = Field(..., description="Chat message text")
    timestamp: datetime = Field(..., description="Message timestamp")
    rank: int = Field(..., description="User rank (0=guest, 1=member, etc.)")
    channel: str = Field(..., description="Channel name")
    domain: str = Field(..., description="Domain name")
    correlation_id: str = Field(..., description="Trace ID")


class UserJoinEvent(BaseModel):
    """User joined channel event.

    Attributes:
        username: Username
        rank: User rank
        timestamp: Join timestamp
        channel: Channel name
        domain: Domain name
        correlation_id: Trace ID
    """

    username: str
    rank: int
    timestamp: datetime
    channel: str
    domain: str
    correlation_id: str


class UserLeaveEvent(BaseModel):
    """User left channel event.

    Attributes:
        username: Username
        timestamp: Leave timestamp
        channel: Channel name
        domain: Domain name
        correlation_id: Trace ID
    """

    username: str
    timestamp: datetime
    channel: str
    domain: str
    correlation_id: str


class ChangeMediaEvent(BaseModel):
    """Media changed event.

    Attributes:
        media_type: Media type (yt, vm, dm, etc.)
        media_id: Media ID
        title: Media title
        duration: Duration in seconds
        uid: Playlist item UID
        timestamp: Change timestamp
        channel: Channel name
        domain: Domain name
        correlation_id: Trace ID
    """

    media_type: str = Field(..., description="Media type (yt, vm, dm, etc.)")
    media_id: str = Field(..., description="Media ID")
    title: str = Field(..., description="Media title")
    duration: int = Field(..., description="Duration in seconds")
    uid: int = Field(..., description="Playlist item UID")
    timestamp: datetime
    channel: str
    domain: str
    correlation_id: str


class PlaylistUpdateEvent(BaseModel):
    """Playlist updated event.

    Attributes:
        action: Action: add, delete, move, clear
        uid: Item UID if applicable
        timestamp: Update timestamp
        channel: Channel name
        domain: Domain name
        correlation_id: Trace ID
    """

    action: str = Field(..., description="Action: add, delete, move, clear")
    uid: int | None = Field(None, description="Item UID if applicable")
    timestamp: datetime
    channel: str
    domain: str
    correlation_id: str


__all__ = [
    "RawEvent",
    "ChatMessageEvent",
    "UserJoinEvent",
    "UserLeaveEvent",
    "ChangeMediaEvent",
    "PlaylistUpdateEvent",
]
