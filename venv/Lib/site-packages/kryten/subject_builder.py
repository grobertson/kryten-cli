"""NATS Subject Builder for CyTube Events.

This module provides utilities for constructing and parsing hierarchical NATS
subject strings following the format: cytube.events.{domain}.{channel}.{event_name}

Subject Format
--------------
cytube.events.{domain}.{channel}.{event_name}
            ^        ^         ^
            |        |         +-- Event type (e.g., chatMsg)
            |        +------------ Channel name (e.g., lounge)
            +--------------------- Domain (e.g., cytu.be)

Wildcard Subscriptions
----------------------
NATS supports wildcard subscriptions for flexible filtering:

- Single level wildcard (*):
  cytube.events.*.lounge.chatMsg  # All domains, lounge channel, chatMsg events

- Multi-level wildcard (>):
  cytube.events.cytu.be.>          # All events from cytu.be domain
  cytube.events.*.lounge.>         # All events from any domain's lounge channel

Examples
--------
>>> from kryten import RawEvent
>>> from kryten.subject_builder import build_subject, build_event_subject
>>>
>>> # Build subject from components
>>> subject = build_subject("cytu.be", "lounge", "chatMsg")
>>> print(subject)
'cytube.events.cytu.be.lounge.chatmsg'
>>>
>>> # Build subject from RawEvent
>>> event = RawEvent("chatMsg", {}, "lounge", "cytu.be")
>>> subject = build_event_subject(event)
>>>
>>> # Parse subject back to components
>>> from kryten.subject_builder import parse_subject
>>> components = parse_subject("cytube.events.cytu.be.lounge.chatMsg")
>>> print(components['domain'])
'cytu.be'
"""

from kryten.models import RawEvent

SUBJECT_PREFIX = "kryten.events"
"""NATS subject prefix for all CyTube events."""

COMMAND_PREFIX = "kryten.commands"
"""NATS subject prefix for all CyTube commands."""

MAX_TOKEN_LENGTH = 100
"""Maximum length for individual subject tokens to prevent exceeding NATS limits."""


def normalize_token(token: str) -> str:
    """Normalize token for consistent NATS subject matching.
    
    Aggressively normalizes domains and channels to ensure consistent matching:
    - Converts to lowercase
    - Removes ALL dots (cy.tube -> cytube, cytu.be -> cytube)
    - Replaces spaces with hyphens
    - Removes special characters
    
    This ensures that variations like "cy.tube", "Cy.tube", "cytu.be" all
    normalize to the same subject token, making NATS routing reliable.

    Args:
        token: Raw token string to normalize.

    Returns:
        Normalized token suitable for NATS subject.

    Examples:
        >>> normalize_token("cy.tube")
        'cytube'
        >>> normalize_token("Cytu.be")
        'cytube'
        >>> normalize_token("420Grindhouse")
        '420grindhouse'
        >>> normalize_token("My Channel!")
        'my-channel'
    """
    if not token:
        return ""

    # Convert to lowercase first
    token = token.lower()

    # Remove ALL dots (critical for domain normalization)
    token = token.replace(".", "")

    # Replace spaces with hyphens
    token = token.replace(" ", "-")

    # Remove NATS wildcard characters
    token = token.replace("*", "").replace(">", "")

    # Remove invalid characters for NATS subjects
    # Keep: alphanumeric (ASCII + Unicode), hyphens, underscores only
    # Remove: all other special chars
    invalid_chars = "!@#$%^&*()+=[]{|}\\:;\"'<>,?/"
    for char in invalid_chars:
        token = token.replace(char, "")

    # Truncate to prevent exceeding NATS subject length limit
    if len(token) > MAX_TOKEN_LENGTH:
        token = token[:MAX_TOKEN_LENGTH]

    return token


def sanitize_token(token: str) -> str:
    """Legacy alias for normalize_token. Use normalize_token instead.
    
    Deprecated: This function exists for backward compatibility only.
    Use normalize_token() for new code.
    """
    return normalize_token(token)


def build_subject(domain: str, channel: str, event_name: str) -> str:
    """Build NATS subject from event components.

    Constructs hierarchical subject following the format:
    kryten.events.cytube.{channel}.{event_name}
    
    All components are aggressively normalized (lowercase, dots removed).

    Args:
        domain: CyTube server domain (e.g., "cytu.be", "cy.tube").
        channel: Channel name (e.g., "420Grindhouse").
        event_name: Socket.IO event name (e.g., "chatMsg").

    Returns:
        Formatted NATS subject string.

    Raises:
        ValueError: If any component is empty after normalization.

    Examples:
        >>> build_subject("cytu.be", "lounge", "chatMsg")
        'kryten.events.cytube.lounge.chatmsg'
        >>> build_subject("cy.tube", "420Grindhouse", "chatMsg")
        'kryten.events.cytube.420grindhouse.chatmsg'
        >>> build_subject("CYTU.BE", "Test Channel", "userJoin")
        'kryten.events.cytube.test-channel.userjoin'
    """
    # Normalize all components (domain dots removed, everything lowercase)
    domain_clean = normalize_token(domain)
    channel_clean = normalize_token(channel)
    event_clean = normalize_token(event_name)

    # Validate components are not empty
    if not channel_clean:
        raise ValueError("Channel cannot be empty after normalization")
    if not event_clean:
        raise ValueError("Event name cannot be empty after normalization")

    # Build subject with "cytube" as literal platform name (domain normalized out)
    subject = f"{SUBJECT_PREFIX}.cytube.{channel_clean}.{event_clean}"

    # Final validation
    if len(subject) > 255:
        raise ValueError(f"Subject exceeds NATS limit of 255 characters: {len(subject)}")

    return subject


def build_event_subject(event: RawEvent) -> str:
    """Build NATS subject from RawEvent.

    Convenience function that extracts domain, channel, and event_name from
    a RawEvent instance and builds the subject string.

    Args:
        event: RawEvent instance with domain, channel, and event_name fields.

    Returns:
        Formatted NATS subject string.

    Examples:
        >>> from kryten import RawEvent
        >>> event = RawEvent(event_name="chatMsg", payload={}, channel="lounge", domain="cytu.be")
        >>> build_event_subject(event)
        'cytube.events.cytu.be.lounge.chatmsg'
    """
    return build_subject(event.domain, event.channel, event.event_name)


def build_command_subject(domain: str, channel: str, action: str) -> str:
    """Build NATS subject for commands.

    Constructs hierarchical subject following the format:
    kryten.commands.cytube.{channel}.{action}
    
    All components are aggressively normalized (lowercase, dots removed).

    Args:
        domain: Domain name (e.g., "cytu.be", "cy.tube").
        channel: Channel name (e.g., "420Grindhouse").
        action: Command action (e.g., "chat", "queue").

    Returns:
        Formatted NATS subject string.

    Raises:
        ValueError: If any component is empty after normalization.

    Examples:
        >>> build_command_subject("cytu.be", "lounge", "chat")
        'kryten.commands.cytube.lounge.chat'
        >>> build_command_subject("cy.tube", "420Grindhouse", "chat")
        'kryten.commands.cytube.420grindhouse.chat'
        >>> build_command_subject("Cytu.be", "Test Channel", "queue")
        'kryten.commands.cytube.test-channel.queue'
    """
    # Normalize all components (domain dots removed, everything lowercase)
    domain_clean = normalize_token(domain)
    channel_clean = normalize_token(channel)
    action_clean = normalize_token(action)

    # Validate components are not empty
    if not channel_clean:
        raise ValueError("Channel cannot be empty after normalization")
    if not action_clean:
        raise ValueError("Action cannot be empty after normalization")

    # Build subject with "cytube" as literal platform name (domain normalized out)
    subject = f"{COMMAND_PREFIX}.cytube.{channel_clean}.{action_clean}"

    # Final validation
    if len(subject) > 255:
        raise ValueError(f"Subject exceeds NATS limit of 255 characters: {len(subject)}")

    return subject


def parse_subject(subject: str) -> dict[str, str]:
    """Parse NATS subject into components.

    Extracts prefix, domain, channel, and event_name from a hierarchical
    subject string. Expected format: cytube.events.{domain}.{channel}.{event}

    Domain may contain dots (e.g., cytu.be). Uses TLD detection heuristic.

    Args:
        subject: NATS subject string to parse.

    Returns:
        Dictionary with keys: prefix, domain, channel, event_name.

    Raises:
        ValueError: If subject format is invalid or missing required components.

    Examples:
        >>> components = parse_subject("cytube.events.cytu.be.lounge.chatMsg")
        >>> components['domain']
        'cytu.be'
        >>> components['channel']
        'lounge'
        >>> components['event_name']
        'chatMsg'
    """
    if not subject:
        raise ValueError("Subject cannot be empty")

    # Check prefix first
    if not subject.startswith(SUBJECT_PREFIX + "."):
        raise ValueError(
            f"Invalid subject prefix: expected '{SUBJECT_PREFIX}.', " f"got '{subject[:20]}...'"
        )

    # Remove prefix to get remaining components
    remaining = subject[len(SUBJECT_PREFIX) + 1 :]  # +1 for the dot

    # Split remaining part
    tokens = remaining.split(".")

    if len(tokens) < 3:
        raise ValueError(
            f"Invalid subject format: expected 'cytube.events.{{domain}}.{{channel}}.{{event}}', "
            f"got '{subject}'"
        )

    # Heuristic: Check if second token looks like a TLD
    # Common TLDs for CyTube servers
    tld_extensions = {"com", "be", "org", "net", "io", "tv", "gg", "me", "co"}

    if len(tokens) >= 2 and tokens[1] in tld_extensions:
        # Domain has TLD (e.g., cytu.be)
        domain = f"{tokens[0]}.{tokens[1]}"
        channel = tokens[2] if len(tokens) > 2 else ""
        event_name = ".".join(tokens[3:]) if len(tokens) > 3 else ""
    else:
        # Domain is single token (e.g., localhost)
        domain = tokens[0]
        channel = tokens[1] if len(tokens) > 1 else ""
        event_name = ".".join(tokens[2:]) if len(tokens) > 2 else ""

    if not channel or not event_name:
        raise ValueError(
            f"Invalid subject format: expected 'cytube.events.{{domain}}.{{channel}}.{{event}}', "
            f"got '{subject}'"
        )

    return {
        "prefix": SUBJECT_PREFIX,
        "domain": domain,
        "channel": channel,
        "event_name": event_name,
    }


__all__ = [
    "SUBJECT_PREFIX",
    "COMMAND_PREFIX",
    "MAX_TOKEN_LENGTH",
    "sanitize_token",
    "build_subject",
    "build_event_subject",
    "build_command_subject",
    "parse_subject",
]
