#!/usr/bin/env python3
"""Kryten CLI - Send CyTube commands via NATS.

This command-line tool sends commands to a CyTube channel through NATS messaging.
It provides a simple interface to all outbound commands supported by the Kryten
bidirectional bridge.

Usage:
    kryten [--channel CHANNEL] [OPTIONS] COMMAND [ARGS...]

Global Options:
    --channel CHANNEL       CyTube channel name (required)
    --domain DOMAIN         CyTube domain (default: cytu.be)
    --nats URL              NATS server URL (default: nats://localhost:4222)
                            Can be specified multiple times for clustering
    --config PATH           Path to config file (overrides command-line options)

Examples:
    Specify channel:
        $ kryten --channel lounge say "Hello world"
    
    Use custom domain:
        $ kryten --channel myroom --domain notcytu.be say "Hi!"
    
    Connect to remote NATS:
        $ kryten --channel lounge --nats nats://10.0.0.5:4222 say "Hello"
    
    Send a private message:
        $ kryten --channel lounge pm UserName "Hi there!"
    
    Add video to playlist:
        $ kryten --channel lounge playlist add https://youtube.com/watch?v=xyz
        $ kryten --channel lounge playlist addnext https://youtube.com/watch?v=abc
    
    Delete from playlist:
        $ kryten --channel lounge playlist del 5
    
    Playlist management:
        $ kryten --channel lounge playlist move 3 after 7
        $ kryten --channel lounge playlist jump 5
        $ kryten --channel lounge playlist clear
        $ kryten --channel lounge playlist shuffle
        $ kryten --channel lounge playlist settemp 5 true
    
    Playback control:
        $ kryten --channel lounge pause
        $ kryten --channel lounge play
        $ kryten --channel lounge seek 120.5
    
    Moderation:
        $ kryten --channel lounge kick UserName "Stop spamming"
        $ kryten --channel lounge ban UserName "Banned for harassment"
        $ kryten --channel lounge voteskip

Configuration File:
    You can use a JSON configuration file instead of command-line options:
    
        $ kryten --config myconfig.json say "Hello"
    
    The config file should contain NATS connection settings and channel information.
    See config.example.json for the format.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from kryten import KrytenClient


def _read_project_version() -> str:
    """Read package version from pyproject.toml."""
    try:
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "unknown"


def _print_about() -> None:
    """Print project information and credits."""
    version = _read_project_version()
    print("kryten-cli")
    print("Version: " + version)
    print("Credits: Kryten Robot Team and contributors")
    print("Project: https://github.com/grobertson/kryten-cli")
    print("Thank you to the people who make Cytu.be's Channel-Z excellent.")


class KrytenCLI:
    """Command-line interface for Kryten CyTube commands."""
    
    def __init__(
        self,
        channel: str,
        domain: str = "cytu.be",
        nats_servers: Optional[list[str]] = None,
        config_path: Optional[str] = None,
    ):
        """Initialize CLI with configuration.
        
        Args:
            channel: CyTube channel name (required).
            domain: CyTube domain (default: cytu.be).
            nats_servers: NATS server URLs (default: ["nats://localhost:4222"]).
            config_path: Optional path to configuration file (overrides defaults).
        """
        self.channel = channel
        self.domain = domain
        self.client: Optional[KrytenClient] = None
        
        # Build config dict from command-line args or config file
        if config_path and Path(config_path).exists():
            self.config_dict = self._load_config(config_path)
        else:
            # Use defaults or command-line overrides
            if nats_servers is None:
                nats_servers = ["nats://localhost:4222"]
            
            self.config_dict = {
                "nats": {
                    "servers": nats_servers
                },
                "channels": [
                    {
                        "domain": domain,
                        "channel": channel
                    }
                ]
            }
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file.
        
        Args:
            config_path: Path to configuration file.
        
        Returns:
            Configuration dictionary.
        
        Raises:
            SystemExit: If config file is invalid.
        """
        try:
            with Path(config_path).open("r", encoding="utf-8") as f:
                config = json.load(f)
                
            # Enforce current config format only.
            if "channels" not in config:
                print(
                    "Error: Config must include a 'channels' list (legacy 'cytube' format is no longer supported).",
                    file=sys.stderr,
                )
                sys.exit(1)
                
            return config
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def connect(self) -> None:
        """Connect to NATS server using kryten-py client."""
        try:
            self.client = KrytenClient(self.config_dict)
            await self.client.connect()
        except OSError as e:
            # Network/hostname errors
            servers = self.config_dict.get("nats", {}).get("servers", [])
            print(f"Error: Cannot connect to NATS server {servers}", file=sys.stderr)
            print(f"  {e}", file=sys.stderr)
            print("  Check that:", file=sys.stderr)
            print("    1. NATS server is running", file=sys.stderr)
            print("    2. Hostname/IP is correct", file=sys.stderr)
            print("    3. Port is accessible", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: Failed to connect: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self.client:
            await self.client.disconnect()
    
    def _parse_media_url(self, url: str) -> tuple[str, str]:
        """Parse media URL to extract type and ID.
        
        Args:
            url: Media URL or ID
            
        Returns:
            Tuple of (media_type, media_id)
        """
        # YouTube patterns
        yt_patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$'  # Direct ID
        ]
        
        for pattern in yt_patterns:
            match = re.search(pattern, url)
            if match:
                return ("yt", match.group(1))
        
        # Vimeo
        vimeo_match = re.search(r'vimeo\.com/(\d+)', url)
        if vimeo_match:
            return ("vm", vimeo_match.group(1))
        
        # Dailymotion
        dm_match = re.search(r'dailymotion\.com/video/([a-zA-Z0-9]+)', url)
        if dm_match:
            return ("dm", dm_match.group(1))
        
        # CyTube Custom Media JSON manifest (must end with .json)
        if url.lower().endswith('.json') or '.json?' in url.lower():
            return ("cm", url)
        
        # Default: custom URL (for direct video files, custom embeds, etc.)
        return ("cu", url)

    def _read_playlist_urls_from_file(self, file_path: str) -> list[str]:
        """Read playlist URLs from a file, skipping blank and comment lines."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.lstrip().startswith('#')
            ]
    
    # ========================================================================
    # Chat Commands
    # ========================================================================
    
    async def cmd_say(self, message: str) -> None:
        """Send a chat message.
        
        Args:
            message: Message text.
        """
        await self.client.send_chat(self.channel, message, domain=self.domain)
        print(f"✓ Sent chat message to {self.channel}")
    
    async def cmd_pm(self, username: str, message: str) -> None:
        """Send a private message.
        
        Args:
            username: Target username.
            message: Message text.
        """
        await self.client.send_pm(self.channel, username, message, domain=self.domain)
        print(f"✓ Sent PM to {username} in {self.channel}")
    
    # ========================================================================
    # Playlist Commands
    # ========================================================================
    
    async def cmd_playlist_add(self, url_or_file: str) -> None:
        """Add video(s) to end of playlist.
        
        Args:
            url_or_file: Video URL/ID or path to text file containing URLs (one per line).
                        Lines starting with # are ignored as comments.
        """
        if os.path.exists(url_or_file) and os.path.isfile(url_or_file):
            urls = self._read_playlist_urls_from_file(url_or_file)
            print(f"✓ Adding {len(urls)} video(s) from file to end of playlist in {self.channel}")
            for i, url in enumerate(urls):
                media_type, media_id = self._parse_media_url(url)
                await self.client.add_media(
                    self.channel, media_type, media_id, position="end", domain=self.domain
                )
                print(f"  ✓ Added {media_type}:{media_id}")
                if i < len(urls) - 1:
                    await asyncio.sleep(1)
        else:
            media_type, media_id = self._parse_media_url(url_or_file)
            await self.client.add_media(
                self.channel, media_type, media_id, position="end", domain=self.domain
            )
            print(f"✓ Added {media_type}:{media_id} to end of playlist in {self.channel}")
    
    async def cmd_playlist_addnext(self, url_or_file: str) -> None:
        """Add video(s) to play next.
        
        Args:
            url_or_file: Video URL/ID or path to text file containing URLs (one per line).
                        Lines starting with # are ignored as comments.
                        For files, URLs are inserted in reverse order so they play in file order.
        """
        if os.path.exists(url_or_file) and os.path.isfile(url_or_file):
            urls = self._read_playlist_urls_from_file(url_or_file)
            urls.reverse()
            print(f"✓ Adding {len(urls)} video(s) from file to play next in {self.channel}")
            for i, url in enumerate(urls):
                media_type, media_id = self._parse_media_url(url)
                await self.client.add_media(
                    self.channel, media_type, media_id, position="next", domain=self.domain
                )
                print(f"  ✓ Added {media_type}:{media_id}")
                if i < len(urls) - 1:
                    await asyncio.sleep(1)
        else:
            media_type, media_id = self._parse_media_url(url_or_file)
            await self.client.add_media(
                self.channel, media_type, media_id, position="next", domain=self.domain
            )
            print(f"✓ Added {media_type}:{media_id} to play next in {self.channel}")
    
    async def cmd_playlist_del(self, uid: str) -> None:
        """Delete video from playlist.
        
        Args:
            uid: Video UID or position number (1-based).
        """
        uid_int = int(uid)
        
        # If uid looks like a position (small number), fetch playlist and map position to UID
        # CyTube UIDs are typically 4+ digits, positions are 1-based small numbers
        if uid_int < 1000:  # Assume this is a position, not a UID
            bucket_name = f"kryten_{self.channel}_playlist"
            try:
                playlist = await self.client.kv_get(bucket_name, "items", default=None, parse_json=True)
                
                if playlist is None or not isinstance(playlist, list):
                    print(f"Cannot resolve position {uid_int}: playlist not available", file=sys.stderr)
                    sys.exit(1)
                
                if uid_int < 1 or uid_int > len(playlist):
                    print(f"Position {uid_int} out of range (playlist has {len(playlist)} items)", file=sys.stderr)
                    sys.exit(1)
                
                # Get the actual UID from the playlist item
                item = playlist[uid_int - 1]  # Convert 1-based to 0-based
                actual_uid = item.get("uid")
                
                if actual_uid is None:
                    print(f"Could not find UID for position {uid_int}", file=sys.stderr)
                    sys.exit(1)
                
                await self.client.delete_media(self.channel, actual_uid, domain=self.domain)
                title = item.get("media", {}).get("title", "Unknown")
                print(f"✓ Deleted position {uid_int} (UID {actual_uid}): {title}")
            
            except Exception as e:
                print(f"Error resolving position {uid_int}: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Large number, treat as direct UID
            await self.client.delete_media(self.channel, uid_int, domain=self.domain)
            print(f"✓ Deleted media UID {uid} from {self.channel}")
    
    async def cmd_playlist_move(self, uid: str, after: str) -> None:
        """Move video in playlist.
        
        Args:
            uid: Video UID or position to move.
            after: UID or position to place after.
        """
        uid_int = int(uid)
        after_int = int(after)
        
        # Map positions to UIDs if needed (same logic as delete)
        bucket_name = f"kryten_{self.channel}_playlist"
        
        try:
            playlist = await self.client.kv_get(bucket_name, "items", default=None, parse_json=True)
            
            if playlist is None or not isinstance(playlist, list):
                print(f"Cannot resolve positions: playlist not available", file=sys.stderr)
                sys.exit(1)
            
            # Resolve 'from' position to UID if it's a position number
            actual_uid = uid_int
            if uid_int < 1000:  # Position number
                if uid_int < 1 or uid_int > len(playlist):
                    print(f"Position {uid_int} out of range (playlist has {len(playlist)} items)", file=sys.stderr)
                    sys.exit(1)
                actual_uid = playlist[uid_int - 1].get("uid")
                if actual_uid is None:
                    print(f"Could not find UID for position {uid_int}", file=sys.stderr)
                    sys.exit(1)
            
            # Resolve 'after' position to UID if it's a position number
            actual_after = after_int
            if after_int < 1000:  # Position number
                if after_int < 1 or after_int > len(playlist):
                    print(f"Position {after_int} out of range (playlist has {len(playlist)} items)", file=sys.stderr)
                    sys.exit(1)
                actual_after = playlist[after_int - 1].get("uid")
                if actual_after is None:
                    print(f"Could not find UID for position {after_int}", file=sys.stderr)
                    sys.exit(1)
            
            await self.client.move_media(self.channel, actual_uid, actual_after, domain=self.domain)
            print(f"✓ Moved media {uid} after {after} in {self.channel}")
        
        except Exception as e:
            print(f"Error moving media: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_playlist_jump(self, uid: str) -> None:
        """Jump to video in playlist.
        
        Args:
            uid: Video UID to jump to.
        """
        uid_int = int(uid)
        await self.client.jump_to(self.channel, uid_int, domain=self.domain)
        print(f"✓ Jumped to media {uid} in {self.channel}")
    
    async def cmd_playlist_clear(self) -> None:
        """Clear entire playlist."""
        await self.client.clear_playlist(self.channel, domain=self.domain)
        print(f"✓ Cleared playlist in {self.channel}")
    
    async def cmd_playlist_shuffle(self) -> None:
        """Shuffle playlist."""
        await self.client.shuffle_playlist(self.channel, domain=self.domain)
        print(f"✓ Shuffled playlist in {self.channel}")
    
    async def cmd_playlist_settemp(self, uid: str, temp: bool) -> None:
        """Set video temporary status.
        
        Args:
            uid: Video UID.
            temp: Temporary status (true/false).
        """
        uid_int = int(uid)
        await self.client.set_temp(self.channel, uid_int, temp, domain=self.domain)
        print(f"✓ Set temp={temp} for media {uid} in {self.channel}")
    
    # ========================================================================
    # Playback Commands
    # ========================================================================
    
    async def cmd_pause(self) -> None:
        """Pause playback."""
        await self.client.pause(self.channel, domain=self.domain)
        print(f"✓ Paused playback in {self.channel}")
    
    async def cmd_play(self) -> None:
        """Resume playback."""
        await self.client.play(self.channel, domain=self.domain)
        print(f"✓ Resumed playback in {self.channel}")
    
    async def cmd_seek(self, time: float) -> None:
        """Seek to timestamp.
        
        Args:
            time: Target time in seconds.
        """
        await self.client.seek(self.channel, time, domain=self.domain)
        print(f"✓ Seeked to {time}s in {self.channel}")
    
    # ========================================================================
    # Moderation Commands
    # ========================================================================
    
    async def cmd_kick(self, username: str, reason: Optional[str] = None) -> None:
        """Kick user from channel.
        
        Args:
            username: Username to kick.
            reason: Optional kick reason.
        """
        await self.client.kick_user(self.channel, username, reason, domain=self.domain)
        print(f"✓ Kicked {username} from {self.channel}")
    
    async def cmd_ban(self, username: str, reason: Optional[str] = None) -> None:
        """Ban user from channel.
        
        Args:
            username: Username to ban.
            reason: Optional ban reason.
        """
        await self.client.ban_user(self.channel, username, reason, domain=self.domain)
        print(f"✓ Banned {username} from {self.channel}")
    
    async def cmd_voteskip(self) -> None:
        """Vote to skip current video."""
        await self.client.voteskip(self.channel, domain=self.domain)
        print(f"✓ Voted to skip in {self.channel}")

    # ========================================================================
    # Persistent Moderation Commands
    # ========================================================================

    async def _moderator_request(self, command: str, **kwargs) -> dict:
        """Send a request to the kryten-moderator service."""
        request = {
            "service": "moderator",
            "command": command,
            **kwargs,
        }
        try:
            return await self.client.nats_request(
                "kryten.moderator.command",
                request,
                timeout=5.0,
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def cmd_moderator_ban(self, username: str, reason: Optional[str] = None) -> None:
        """Add user to persistent ban list (kicks on join)."""
        response = await self._moderator_request(
            "entry.add",
            username=username,
            action="ban",
            reason=reason,
            moderator="cli",
        )
        if response.get("success"):
            print(f"✓ Added ban for {username}")
        else:
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

    async def cmd_moderator_unban(self, username: str) -> None:
        """Remove user from persistent ban list."""
        response = await self._moderator_request("entry.remove", username=username)
        if response.get("success"):
            print(f"✓ Removed ban for {username}")
        else:
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

    async def cmd_moderator_smute(self, username: str, reason: Optional[str] = None) -> None:
        """Shadow mute a user (not notified)."""
        response = await self._moderator_request(
            "entry.add",
            username=username,
            action="smute",
            reason=reason,
            moderator="cli",
        )
        if response.get("success"):
            print(f"✓ Added shadow mute for {username}")
        else:
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

    async def cmd_moderator_unsmute(self, username: str) -> None:
        """Remove shadow mute from user."""
        response = await self._moderator_request("entry.remove", username=username)
        if response.get("success"):
            print(f"✓ Removed shadow mute for {username}")
        else:
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

    async def cmd_moderator_mute(self, username: str, reason: Optional[str] = None) -> None:
        """Visible mute a user (notified)."""
        response = await self._moderator_request(
            "entry.add",
            username=username,
            action="mute",
            reason=reason,
            moderator="cli",
        )
        if response.get("success"):
            print(f"✓ Added visible mute for {username}")
        else:
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

    async def cmd_moderator_unmute(self, username: str) -> None:
        """Remove visible mute from user."""
        response = await self._moderator_request("entry.remove", username=username)
        if response.get("success"):
            print(f"✓ Removed visible mute for {username}")
        else:
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

    async def cmd_moderator_list(self, filter_action: Optional[str] = None, format: str = "table") -> None:
        """List moderated users."""
        response = await self._moderator_request("entry.list", filter=filter_action)
        if not response.get("success"):
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

        data = response.get("data", {})
        entries = data.get("entries", [])

        if format == "json":
            print(json.dumps(data, indent=2))
            return

        if not entries:
            print("No moderation entries found.")
            return

        print(f"\nModeration List ({len(entries)} entries)")
        print("-" * 80)
        print(f"{'Username':<20} {'Action':<10} {'Reason':<28} {'Moderator':<15}")
        print("-" * 80)
        for entry in entries:
            reason = (entry.get("reason") or "")[:28]
            moderator = (entry.get("moderator") or "")[:15]
            print(f"{entry.get('username', ''):<20} {entry.get('action', ''):<10} {reason:<28} {moderator:<15}")

    async def cmd_moderator_check(self, username: str, format: str = "text") -> None:
        """Check moderation status for one user."""
        response = await self._moderator_request("entry.get", username=username)
        if not response.get("success"):
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

        data = response.get("data", {})
        if format == "json":
            print(json.dumps(data, indent=2))
            return

        entry = data.get("entry")
        if not entry:
            print(f"{username} is not currently moderated.")
            return

        print(f"\nModeration status for {username}")
        print("-" * 40)
        print(f"Action:    {entry.get('action', '')}")
        print(f"Reason:    {entry.get('reason') or '(none)'}")
        print(f"Moderator: {entry.get('moderator', '')}")
        print(f"Timestamp: {entry.get('timestamp', '')}")

    async def cmd_moderator_patterns_list(self, format: str = "table") -> None:
        """List all banned username patterns."""
        response = await self._moderator_request("pattern.list")
        if not response.get("success"):
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

        data = response.get("data", {})
        patterns = data.get("patterns", [])
        if format == "json":
            print(json.dumps(data, indent=2))
            return

        if not patterns:
            print("No patterns configured.")
            return

        print(f"\nBanned Username Patterns ({len(patterns)} patterns)")
        print("-" * 90)
        print(f"{'Pattern':<30} {'Type':<10} {'Action':<10} {'Description':<35}")
        print("-" * 90)
        for p in patterns:
            ptype = "regex" if p.get("is_regex") else "substring"
            desc = (p.get("description") or "")[:35]
            print(f"{p.get('pattern', '')[:30]:<30} {ptype:<10} {p.get('action', ''):<10} {desc:<35}")

    async def cmd_moderator_patterns_add(
        self,
        pattern: str,
        is_regex: bool = False,
        action: str = "ban",
        description: Optional[str] = None,
    ) -> None:
        """Add a banned username pattern."""
        response = await self._moderator_request(
            "pattern.add",
            pattern=pattern,
            is_regex=is_regex,
            action=action,
            added_by="cli",
            description=description,
        )
        if response.get("success"):
            print(f"✓ Added pattern: {pattern}")
        else:
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

    async def cmd_moderator_patterns_remove(self, pattern: str) -> None:
        """Remove a banned username pattern."""
        response = await self._moderator_request("pattern.remove", pattern=pattern)
        if response.get("success"):
            print(f"✓ Removed pattern: {pattern}")
        else:
            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

    # ========================================================================
    # Userstats Commands
    # ========================================================================

    async def cmd_userstats_all(
        self,
        format: str = "text",
        top_users: int = 20,
        media_history: int = 15,
        leaderboards: int = 10,
    ) -> None:
        """Fetch and display channel stats from the userstats service."""
        try:
            request = {
                "service": "userstats",
                "command": "channel.all_stats",
                "limits": {
                    "top_users": top_users,
                    "media_history": media_history,
                    "leaderboards": leaderboards,
                },
            }
            response = await self.client.nats_request(
                "kryten.userstats.command",
                request,
                timeout=10.0,
            )
            if not response.get("success"):
                print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
                sys.exit(1)

            data = response.get("data", {})
            if format == "json":
                print(json.dumps(data, indent=2))
                return

            print("\nUserstats Channel Report")
            print("=" * 80)

            system = data.get("system", {})
            health = system.get("health", {})
            stats = system.get("stats", {})
            print("\nSystem")
            print(f"  Service:   {health.get('service', 'N/A')}")
            print(f"  Status:    {health.get('status', 'N/A')}")
            print(f"  Uptime:    {health.get('uptime_seconds', 0) / 3600:.2f} hours")
            print(f"  Events:    {stats.get('events_processed', 0):,}")
            print(f"  Commands:  {stats.get('commands_processed', 0):,}")

            leaderboards_data = data.get("leaderboards", {})
            print("\nKudos Leaderboard")
            for i, entry in enumerate(leaderboards_data.get("kudos", []), 1):
                print(f"  {i:2}. {entry.get('username', ''):20} {entry.get('count', 0):,} kudos")

            print("\nEmote Leaderboard")
            for i, entry in enumerate(leaderboards_data.get("emotes", []), 1):
                print(f"  {i:2}. {entry.get('emote', ''):20} {entry.get('count', 0):,} uses")

            channel = data.get("channel", {})
            print("\nTop Active Users")
            for i, entry in enumerate(channel.get("top_users", []), 1):
                print(f"  {i:2}. {entry.get('username', ''):20} {entry.get('count', 0):,} messages")

            print("\nRecent Media")
            for i, entry in enumerate(channel.get("media_history", []), 1):
                print(f"  {i:2}. [{entry.get('media_type', '?')}] {entry.get('media_title', 'Unknown')}")

        except TimeoutError:
            print("Error: Timeout waiting for userstats service", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error fetching userstats: {e}", file=sys.stderr)
            sys.exit(1)
    
    # ========================================================================
    # List Commands
    # ========================================================================
    
    async def cmd_list_queue(self) -> None:
        """Display current playlist queue."""
        try:
            # Query state via unified command pattern
            request = {
                "service": "robot",
                "command": "state.playlist"
            }
            response = await self.client.nats_request(
                "kryten.robot.command",
                request,
                timeout=5.0
            )
            
            if not response.get("success"):
                print(f"Error: {response.get('error', 'Unknown error')}")
                print(f"Is Kryten-Robot running for channel '{self.channel}'?")
                return
            
            playlist = response.get("data", {}).get("playlist", [])
            
            if not playlist:
                print("Playlist is empty.")
                return
            
            print(f"\n{self.channel} Playlist ({len(playlist)} items):")
            print("=" * 80)
            
            for i, item in enumerate(playlist, 1):
                media = item.get("media", {})
                title = media.get("title", "Unknown")
                duration = media.get("duration", "--:--")
                media_type = media.get("type", "??")
                uid = item.get("uid", "")
                temp = " [TEMP]" if item.get("temp") else ""
                queueby = item.get("queueby", "")
                
                print(f"{i:3}. [{media_type}] {title}")
                print(f"     Duration: {duration} | UID: {uid}{temp}")
                if queueby:
                    print(f"     Queued by: {queueby}")
                print()
        
        except Exception as e:
            print(f"Error retrieving playlist: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_list_users(self) -> None:
        """Display current user list."""
        try:
            # Query state via unified command pattern
            request = {
                "service": "robot",
                "command": "state.userlist"
            }
            response = await self.client.nats_request(
                "kryten.robot.command",
                request,
                timeout=5.0
            )
            
            if not response.get("success"):
                print(f"Error: {response.get('error', 'Unknown error')}")
                print(f"Is Kryten-Robot running for channel '{self.channel}'?")
                return
            
            users = response.get("data", {}).get("userlist", [])
            
            if not users:
                print("No users online.")
                return
            
            # Sort by rank (descending) then name
            users_sorted = sorted(users, key=lambda u: (-u.get("rank", 0), u.get("name", "").lower()))
            
            print(f"\n{self.channel} Users ({len(users)} online):")
            print("=" * 80)
            
            rank_names = {
                0: "Guest",
                1: "Registered",
                2: "Moderator",
                3: "Channel Admin",
                4: "Site Admin",
            }
            
            for user in users_sorted:
                name = user.get("name", "Unknown")
                rank = user.get("rank", 0)
                rank_name = rank_names.get(rank, f"Rank {rank}")
                afk = " [AFK]" if user.get("meta", {}).get("afk") else ""
                
                print(f"  [{rank}] {name} - {rank_name}{afk}")
        
        except Exception as e:
            print(f"Error retrieving user list: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_list_emotes(self) -> None:
        """Display channel emotes."""
        try:
            # Query state via unified command pattern
            request = {
                "service": "robot",
                "command": "state.emotes"
            }
            response = await self.client.nats_request(
                "kryten.robot.command",
                request,
                timeout=5.0
            )
            
            if not response.get("success"):
                print(f"Error: {response.get('error', 'Unknown error')}")
                print(f"Is Kryten-Robot running for channel '{self.channel}'?")
                return
            
            emotes = response.get("data", {}).get("emotes", [])
            
            if not emotes:
                print("No custom emotes configured.")
                return
            
            print(f"\n{self.channel} Custom Emotes ({len(emotes)} total):")
            print("=" * 80)
            
            for emote in emotes:
                name = emote.get("name", "Unknown")
                image = emote.get("image", "")
                
                # Truncate long URLs for display
                if len(image) > 60:
                    image_display = image[:57] + "..."
                else:
                    image_display = image
                
                print(f"  {name:30} {image_display}")
        
        except Exception as e:
            print(f"Error retrieving emotes: {e}", file=sys.stderr)
            sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser.
    
    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="kryten",
        description="Send commands to CyTube channel via NATS",
        epilog="See 'kryten <command> --help' for command-specific help."
    )
    
    # Global options
    parser.add_argument(
        "--channel",
        help="CyTube channel name (required for all commands except 'about')"
    )
    
    parser.add_argument(
        "--domain",
        default="cytu.be",
        help="CyTube domain (default: cytu.be)"
    )
    
    parser.add_argument(
        "--nats",
        action="append",
        dest="nats_servers",
        help="NATS server URL (can be specified multiple times, default: nats://localhost:4222)"
    )
    
    parser.add_argument(
        "--config",
        help="Path to configuration file (overrides other options if present)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Chat commands
    say_parser = subparsers.add_parser("say", help="Send a chat message")
    say_parser.add_argument("message", help="Message text")
    
    pm_parser = subparsers.add_parser("pm", help="Send a private message")
    pm_parser.add_argument("username", help="Target username")
    pm_parser.add_argument("message", help="Message text")

    # Metadata command
    subparsers.add_parser("about", help="Show project information and credits")
    
    # Playlist commands
    playlist_parser = subparsers.add_parser("playlist", help="Playlist management")
    playlist_subparsers = playlist_parser.add_subparsers(dest="playlist_cmd")
    
    add_parser = playlist_subparsers.add_parser("add", help="Add video to end")
    add_parser.add_argument("url", help="Video URL or ID")
    
    addnext_parser = playlist_subparsers.add_parser("addnext", help="Add video to play next")
    addnext_parser.add_argument("url", help="Video URL or ID")
    
    del_parser = playlist_subparsers.add_parser("del", help="Delete video")
    del_parser.add_argument("uid", help="Video UID or position")
    
    move_parser = playlist_subparsers.add_parser("move", help="Move video")
    move_parser.add_argument("uid", help="Video UID to move")
    move_parser.add_argument("after", help="UID to place after")
    
    jump_parser = playlist_subparsers.add_parser("jump", help="Jump to video")
    jump_parser.add_argument("uid", help="Video UID")
    
    playlist_subparsers.add_parser("clear", help="Clear playlist")
    playlist_subparsers.add_parser("shuffle", help="Shuffle playlist")
    
    settemp_parser = playlist_subparsers.add_parser("settemp", help="Set temp status")
    settemp_parser.add_argument("uid", help="Video UID")
    settemp_parser.add_argument("temp", choices=["true", "false"], help="Temporary status")
    
    # Playback commands
    subparsers.add_parser("pause", help="Pause playback")
    subparsers.add_parser("play", help="Resume playback")
    
    seek_parser = subparsers.add_parser("seek", help="Seek to timestamp")
    seek_parser.add_argument("time", type=float, help="Time in seconds")
    
    # Moderation commands
    kick_parser = subparsers.add_parser("kick", help="Kick user")
    kick_parser.add_argument("username", help="Username to kick")
    kick_parser.add_argument("reason", nargs="?", help="Kick reason")
    
    ban_parser = subparsers.add_parser("ban", help="Ban user")
    ban_parser.add_argument("username", help="Username to ban")
    ban_parser.add_argument("reason", nargs="?", help="Ban reason")
    
    subparsers.add_parser("voteskip", help="Vote to skip current video")
    
    # List commands
    list_parser = subparsers.add_parser("list", help="List channel information")
    list_subparsers = list_parser.add_subparsers(dest="list_cmd")
    
    list_subparsers.add_parser("queue", help="Show current playlist")
    list_subparsers.add_parser("users", help="Show online users")
    list_subparsers.add_parser("emotes", help="Show channel emotes")

    # Userstats commands
    userstats_parser = subparsers.add_parser("userstats", help="User statistics commands")
    userstats_subparsers = userstats_parser.add_subparsers(dest="userstats_cmd")

    all_stats_parser = userstats_subparsers.add_parser("all", help="Fetch all channel statistics")
    all_stats_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    all_stats_parser.add_argument("--top-users", type=int, default=20, help="Top users to include")
    all_stats_parser.add_argument("--media-history", type=int, default=15, help="Recent media entries to include")
    all_stats_parser.add_argument("--leaderboards", type=int, default=10, help="Leaderboard entries to include")

    # Persistent moderator commands
    moderator_parser = subparsers.add_parser("moderator", help="Persistent moderation list commands")
    moderator_sub = moderator_parser.add_subparsers(dest="moderator_cmd")

    mod_ban = moderator_sub.add_parser("ban", help="Add user to persistent ban list")
    mod_ban.add_argument("username", help="Username to ban")
    mod_ban.add_argument("reason", nargs="?", help="Reason (optional)")

    mod_unban = moderator_sub.add_parser("unban", help="Remove user from persistent ban list")
    mod_unban.add_argument("username", help="Username to unban")

    mod_smute = moderator_sub.add_parser("smute", help="Shadow mute user")
    mod_smute.add_argument("username", help="Username to shadow mute")
    mod_smute.add_argument("reason", nargs="?", help="Reason (optional)")

    mod_unsmute = moderator_sub.add_parser("unsmute", help="Remove shadow mute from user")
    mod_unsmute.add_argument("username", help="Username to unshadow mute")

    mod_mute = moderator_sub.add_parser("mute", help="Visible mute user")
    mod_mute.add_argument("username", help="Username to mute")
    mod_mute.add_argument("reason", nargs="?", help="Reason (optional)")

    mod_unmute = moderator_sub.add_parser("unmute", help="Remove visible mute from user")
    mod_unmute.add_argument("username", help="Username to unmute")

    mod_list = moderator_sub.add_parser("list", help="List moderated users")
    mod_list.add_argument("--filter", choices=["ban", "smute", "mute"], help="Filter by action")
    mod_list.add_argument("--format", choices=["table", "json"], default="table", help="Output format")

    mod_check = moderator_sub.add_parser("check", help="Check moderation status for a user")
    mod_check.add_argument("username", help="Username to check")
    mod_check.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    mod_patterns = moderator_sub.add_parser("patterns", help="Manage banned username patterns")
    mod_patterns_sub = mod_patterns.add_subparsers(dest="patterns_cmd")

    patterns_list = mod_patterns_sub.add_parser("list", help="List patterns")
    patterns_list.add_argument("--format", choices=["table", "json"], default="table", help="Output format")

    patterns_add = mod_patterns_sub.add_parser("add", help="Add pattern")
    patterns_add.add_argument("pattern", help="Pattern to add")
    patterns_add.add_argument("--regex", action="store_true", help="Treat pattern as regex")
    patterns_add.add_argument("--action", choices=["ban", "smute", "mute"], default="ban", help="Action on match")
    patterns_add.add_argument("--description", help="Optional description")

    patterns_remove = mod_patterns_sub.add_parser("remove", help="Remove pattern")
    patterns_remove.add_argument("pattern", help="Pattern to remove")
    
    return parser


async def main() -> None:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "about":
        _print_about()
        return
    
    # Channel is now required for all network commands.
    channel = args.channel
    if not channel:
        print("Error: --channel is required for this command.", file=sys.stderr)
        sys.exit(1)
    
    # Initialize CLI with discovered or specified channel
    cli = KrytenCLI(
        channel=channel,
        domain=args.domain,
        nats_servers=args.nats_servers,
        config_path=args.config,
    )
    
    # Connect to NATS
    await cli.connect()
    
    try:
        # Route to appropriate command handler
        if args.command == "say":
            await cli.cmd_say(args.message)
        
        elif args.command == "pm":
            await cli.cmd_pm(args.username, args.message)

        elif args.command == "about":
            _print_about()
        
        elif args.command == "playlist":
            if args.playlist_cmd == "add":
                await cli.cmd_playlist_add(args.url)
            elif args.playlist_cmd == "addnext":
                await cli.cmd_playlist_addnext(args.url)
            elif args.playlist_cmd == "del":
                await cli.cmd_playlist_del(args.uid)
            elif args.playlist_cmd == "move":
                await cli.cmd_playlist_move(args.uid, args.after)
            elif args.playlist_cmd == "jump":
                await cli.cmd_playlist_jump(args.uid)
            elif args.playlist_cmd == "clear":
                await cli.cmd_playlist_clear()
            elif args.playlist_cmd == "shuffle":
                await cli.cmd_playlist_shuffle()
            elif args.playlist_cmd == "settemp":
                temp_bool = args.temp == "true"
                await cli.cmd_playlist_settemp(args.uid, temp_bool)
            else:
                parser.parse_args(["playlist", "--help"])
        
        elif args.command == "pause":
            await cli.cmd_pause()
        
        elif args.command == "play":
            await cli.cmd_play()
        
        elif args.command == "seek":
            await cli.cmd_seek(args.time)
        
        elif args.command == "kick":
            await cli.cmd_kick(args.username, args.reason)
        
        elif args.command == "ban":
            await cli.cmd_ban(args.username, args.reason)
        
        elif args.command == "voteskip":
            await cli.cmd_voteskip()
        
        elif args.command == "list":
            if args.list_cmd == "queue":
                await cli.cmd_list_queue()
            elif args.list_cmd == "users":
                await cli.cmd_list_users()
            elif args.list_cmd == "emotes":
                await cli.cmd_list_emotes()
            else:
                parser.parse_args(["list", "--help"])

        elif args.command == "userstats":
            if args.userstats_cmd == "all":
                await cli.cmd_userstats_all(
                    format=args.format,
                    top_users=args.top_users,
                    media_history=args.media_history,
                    leaderboards=args.leaderboards,
                )
            else:
                parser.parse_args(["userstats", "--help"])

        elif args.command == "moderator":
            if args.moderator_cmd == "ban":
                await cli.cmd_moderator_ban(args.username, args.reason)
            elif args.moderator_cmd == "unban":
                await cli.cmd_moderator_unban(args.username)
            elif args.moderator_cmd == "smute":
                await cli.cmd_moderator_smute(args.username, args.reason)
            elif args.moderator_cmd == "unsmute":
                await cli.cmd_moderator_unsmute(args.username)
            elif args.moderator_cmd == "mute":
                await cli.cmd_moderator_mute(args.username, args.reason)
            elif args.moderator_cmd == "unmute":
                await cli.cmd_moderator_unmute(args.username)
            elif args.moderator_cmd == "list":
                await cli.cmd_moderator_list(filter_action=args.filter, format=args.format)
            elif args.moderator_cmd == "check":
                await cli.cmd_moderator_check(args.username, format=args.format)
            elif args.moderator_cmd == "patterns":
                if args.patterns_cmd == "list":
                    await cli.cmd_moderator_patterns_list(format=args.format)
                elif args.patterns_cmd == "add":
                    await cli.cmd_moderator_patterns_add(
                        pattern=args.pattern,
                        is_regex=args.regex,
                        action=args.action,
                        description=args.description,
                    )
                elif args.patterns_cmd == "remove":
                    await cli.cmd_moderator_patterns_remove(args.pattern)
                else:
                    parser.parse_args(["moderator", "patterns", "--help"])
            else:
                parser.parse_args(["moderator", "--help"])
        
        else:
            print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
            sys.exit(1)
    
    finally:
        await cli.disconnect()


def run() -> None:
    """Entry point wrapper for setuptools."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()
