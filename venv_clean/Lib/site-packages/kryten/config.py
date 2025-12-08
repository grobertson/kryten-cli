"""Configuration models for kryten-py library."""

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class NatsConfig(BaseModel):
    """NATS connection configuration.

    Attributes:
        servers: List of NATS server URLs
        user: Optional NATS username for authentication
        password: Optional NATS password
        token: Optional NATS token for authentication
        tls_cert: Optional path to TLS client certificate
        tls_key: Optional path to TLS client key
        tls_ca: Optional path to TLS CA certificate
        connect_timeout: Connection timeout in seconds
        reconnect_time_wait: Seconds between reconnection attempts
        max_reconnect_attempts: Max reconnect attempts (-1 = infinite)
        ping_interval: Ping interval in seconds

    Examples:
        >>> config = NatsConfig(
        ...     servers=["nats://localhost:4222"],
        ...     user="myuser",
        ...     password="mypass"
        ... )
    """

    servers: list[str] = Field(
        ..., description="List of NATS server URLs (e.g., ['nats://localhost:4222'])"
    )
    user: str | None = Field(None, description="NATS username for authentication")
    password: str | None = Field(None, description="NATS password")
    token: str | None = Field(None, description="NATS token for authentication")
    tls_cert: str | None = Field(None, description="Path to TLS client certificate")
    tls_key: str | None = Field(None, description="Path to TLS client key")
    tls_ca: str | None = Field(None, description="Path to TLS CA certificate")
    connect_timeout: int = Field(10, description="Connection timeout in seconds", ge=1)
    reconnect_time_wait: int = Field(2, description="Seconds between reconnection attempts", ge=1)
    max_reconnect_attempts: int = Field(-1, description="Max reconnect attempts (-1 = infinite)")
    ping_interval: int = Field(120, description="Ping interval in seconds", ge=1)

    @field_validator("servers")
    @classmethod
    def validate_servers(cls, v: list[str]) -> list[str]:
        """Ensure at least one server is provided."""
        if not v:
            raise ValueError("At least one NATS server must be configured")
        return v


class ChannelConfig(BaseModel):
    """CyTube channel configuration.

    Attributes:
        domain: CyTube server domain (e.g., 'cytu.be')
        channel: Channel name (e.g., 'lounge')

    Examples:
        >>> channel = ChannelConfig(domain="cytu.be", channel="lounge")
    """

    domain: str = Field(..., description="CyTube server domain (e.g., 'cytu.be')")
    channel: str = Field(..., description="Channel name (e.g., 'lounge')")

    @field_validator("domain", "channel")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure domain and channel are not empty."""
        if not v or not v.strip():
            raise ValueError("Domain and channel must not be empty")
        return v.strip()


class KrytenConfig(BaseModel):
    """Complete Kryten client configuration.

    Attributes:
        nats: NATS connection settings
        channels: List of CyTube channels to connect to
        retry_attempts: Command retry attempts
        retry_delay: Initial retry delay in seconds
        handler_timeout: Max handler execution time
        max_concurrent_handlers: Max concurrent handlers
        log_level: Logging level

    Examples:
        >>> config = KrytenConfig(
        ...     nats=NatsConfig(servers=["nats://localhost:4222"]),
        ...     channels=[ChannelConfig(domain="cytu.be", channel="lounge")]
        ... )
    """

    nats: NatsConfig = Field(..., description="NATS connection settings")
    channels: list[ChannelConfig] = Field(..., description="List of CyTube channels to connect to")
    retry_attempts: int = Field(3, description="Command retry attempts", ge=0, le=10)
    retry_delay: float = Field(1.0, description="Initial retry delay in seconds", ge=0.1)
    handler_timeout: float = Field(30.0, description="Max handler execution time", ge=1.0)
    max_concurrent_handlers: int = Field(1000, description="Max concurrent handlers", ge=1)
    log_level: str = Field("INFO", description="Logging level")

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: list[ChannelConfig]) -> list[ChannelConfig]:
        """Ensure at least one channel is configured."""
        if not v:
            raise ValueError("At least one channel must be configured")
        return v

    @classmethod
    def from_json(cls, path: str) -> "KrytenConfig":
        """Load configuration from JSON file with environment variable substitution.

        Args:
            path: Path to JSON configuration file

        Returns:
            KrytenConfig instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If JSON is invalid or validation fails

        Examples:
            >>> config = KrytenConfig.from_json("config.json")
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        content = file_path.read_text()
        # Substitute environment variables
        content = _substitute_env_vars(content)
        data = json.loads(content)
        return cls(**data)

    @classmethod
    def from_yaml(cls, path: str) -> "KrytenConfig":
        """Load configuration from YAML file with environment variable substitution.

        Args:
            path: Path to YAML configuration file

        Returns:
            KrytenConfig instance

        Raises:
            ImportError: If PyYAML is not installed
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid or validation fails

        Examples:
            >>> config = KrytenConfig.from_yaml("config.yaml")
        """
        try:
            import yaml
        except ImportError as e:
            raise ImportError(
                "PyYAML is required for YAML support. "
                "Install it with: pip install kryten-py[yaml]"
            ) from e

        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        content = file_path.read_text()
        # Substitute environment variables
        content = _substitute_env_vars(content)
        data = yaml.safe_load(content)
        return cls(**data)


def _substitute_env_vars(content: str) -> str:
    """Substitute environment variables in format ${VAR_NAME}.

    Args:
        content: String content with ${VAR_NAME} placeholders

    Returns:
        String with environment variables substituted
    """
    import re

    def replace_env_var(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return re.sub(r"\$\{([^}]+)\}", replace_env_var, content)


__all__ = [
    "NatsConfig",
    "ChannelConfig",
    "KrytenConfig",
]
