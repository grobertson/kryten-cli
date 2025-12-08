"""Health monitoring models for kryten-py library."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChannelInfo(BaseModel):
    """Information about connected channel.

    Attributes:
        domain: Channel domain
        channel: Channel name
        subscribed: Whether actively subscribed
        events_received: Events from this channel
    """

    domain: str
    channel: str
    subscribed: bool = Field(..., description="Whether actively subscribed")
    events_received: int = Field(..., description="Events from this channel")


class HealthStatus(BaseModel):
    """Client health status and metrics.

    Attributes:
        connected: Whether NATS is connected
        state: Connection state: connected, connecting, disconnected, error
        uptime_seconds: Seconds since connection established
        channels: List of connected channels
        events_received: Total events received
        commands_sent: Total commands sent
        errors: Total errors encountered
        avg_event_latency_ms: Average event processing time
        last_event_time: Timestamp of last event
        handlers_registered: Number of event handlers
    """

    connected: bool = Field(..., description="Whether NATS is connected")
    state: str = Field(
        ...,
        description="Connection state: connected, connecting, disconnected, error",
    )
    uptime_seconds: float = Field(..., description="Seconds since connection established")
    channels: list[str] = Field(..., description="List of connected channels")
    events_received: int = Field(..., description="Total events received")
    commands_sent: int = Field(..., description="Total commands sent")
    errors: int = Field(..., description="Total errors encountered")
    avg_event_latency_ms: float = Field(..., description="Average event processing time")
    last_event_time: datetime | None = Field(None, description="Timestamp of last event")
    handlers_registered: int = Field(..., description="Number of event handlers")


__all__ = [
    "ChannelInfo",
    "HealthStatus",
]
