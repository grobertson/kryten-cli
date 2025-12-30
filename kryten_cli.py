#!/usr/bin/env python3
"""Kryten CLI - Send CyTube commands via NATS.

This command-line tool sends commands to a CyTube channel through NATS messaging.
It provides a simple interface to all outbound commands supported by the Kryten
bidirectional bridge.

Channel Auto-Discovery:
    If --channel is not specified, the CLI automatically discovers available channels
    from running Kryten-Robot instances. If only one channel is found, it's used
    automatically. If multiple channels exist, you must specify which one to use.

Usage:
    kryten [--channel CHANNEL] [OPTIONS] COMMAND [ARGS...]

Global Options:
    --channel CHANNEL       CyTube channel name (auto-discovered if not specified)
    --domain DOMAIN         CyTube domain (default: cytu.be)
    --nats URL              NATS server URL (default: nats://localhost:4222)
                            Can be specified multiple times for clustering
    --config PATH           Path to config file (overrides command-line options)

Examples:
    Auto-discover single channel:
        $ kryten say "Hello world"
    
    Specify channel explicitly:
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
    You can optionally use a JSON configuration file instead of command-line options:
    
        $ kryten --config myconfig.json say "Hello"
    
    The config file should contain NATS connection settings and channel information.
    See config.example.json for the format.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from kryten import KrytenClient


class Colors:
    """ANSI color codes for terminal output.
    
    Colors are automatically disabled when output is not a TTY
    or when NO_COLOR environment variable is set.
    """
    
    # Check if colors should be enabled
    _enabled = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    
    # ANSI codes
    RED = "\033[91m" if _enabled else ""
    GREEN = "\033[92m" if _enabled else ""
    YELLOW = "\033[93m" if _enabled else ""
    BLUE = "\033[94m" if _enabled else ""
    MAGENTA = "\033[95m" if _enabled else ""
    CYAN = "\033[96m" if _enabled else ""
    ORANGE = "\033[38;5;208m" if _enabled else ""
    GRAY = "\033[90m" if _enabled else ""
    RESET = "\033[0m" if _enabled else ""
    BOLD = "\033[1m" if _enabled else ""
    DIM = "\033[2m" if _enabled else ""
    
    # Emoji (with fallbacks for terminals that don't support them)
    EMOJI_SUCCESS = "✅" if _enabled else "[OK]"
    EMOJI_ERROR = "❌" if _enabled else "[ERROR]"
    EMOJI_WARNING = "⚠️" if _enabled else "[WARN]"
    EMOJI_INFO = "ℹ️" if _enabled else "[INFO]"
    EMOJI_BAN = "🔨" if _enabled else "[BAN]"
    EMOJI_MUTE = "🔇" if _enabled else "[MUTE]"
    EMOJI_USER = "👤" if _enabled else ""
    EMOJI_PATTERN = "🎯" if _enabled else "[PAT]"
    EMOJI_CHAT = "💬" if _enabled else ""
    EMOJI_PLAYLIST = "🎵" if _enabled else ""
    EMOJI_PLAY = "▶️" if _enabled else "[PLAY]"
    EMOJI_PAUSE = "⏸️" if _enabled else "[PAUSE]"
    EMOJI_SKIP = "⏭️" if _enabled else "[SKIP]"
    EMOJI_STATS = "📊" if _enabled else ""
    EMOJI_CONFIG = "⚙️" if _enabled else ""
    EMOJI_PING = "🏓" if _enabled else ""
    EMOJI_SHUTDOWN = "🛑" if _enabled else ""
    EMOJI_CLOCK = "🕐" if _enabled else ""


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
            config_path: Optional path to configuration file. If None, checks default locations.
        """
        self.channel = channel
        self.domain = domain
        self.client: Optional[KrytenClient] = None
        
        # Determine config file path if not explicitly provided
        if config_path is None:
            # Try default locations in order
            default_paths = [
                Path("/etc/kryten/kryten-cli/config.json"),
                Path("config.json")
            ]
            
            for path in default_paths:
                if path.exists() and path.is_file():
                    config_path = str(path)
                    break
        
        # Build config dict from config file or command-line args
        if config_path and Path(config_path).exists():
            self.config_dict = self._load_config(config_path)
            
            # Allow command-line args to override config file
            if nats_servers is not None:
                self.config_dict["nats"]["servers"] = nats_servers
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
                
            # Ensure channels list exists for kryten-py
            if "channels" not in config and "cytube" in config:
                # Convert legacy format
                cytube = config["cytube"]
                config["channels"] = [{
                    "domain": cytube.get("domain", "cytu.be"),
                    "channel": cytube["channel"]
                }]
                
            return config
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def connect(self) -> None:
        """Connect to NATS server using kryten-py client."""
        try:
            # Create a logger that only shows warnings and errors
            # This keeps CLI output clean (no "Connected/Disconnected" messages)
            logger = logging.getLogger('kryten_cli')
            logger.setLevel(logging.WARNING)
            logger.addHandler(logging.NullHandler())
            
            self.client = KrytenClient(self.config_dict, logger=logger)
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
    
    # ========================================================================
    # Chat Commands
    # ========================================================================
    
    async def cmd_say(self, message: str) -> None:
        """Send a chat message.
        
        Args:
            message: Message text.
        """
        await self.client.send_chat(self.channel, message, domain=self.domain)
        print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_CHAT} Sent chat message to {Colors.CYAN}{self.channel}{Colors.RESET}")
    
    async def cmd_pm(self, username: str, message: str) -> None:
        """Send a private message.
        
        Args:
            username: Target username.
            message: Message text.
        """
        await self.client.send_pm(self.channel, username, message, domain=self.domain)
        print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_CHAT} Sent PM to {Colors.BOLD}{username}{Colors.RESET} in {Colors.CYAN}{self.channel}{Colors.RESET}")
    
    # ========================================================================
    # Playlist Commands
    # ========================================================================
    
    async def cmd_playlist_add(self, url: str) -> None:
        """Add video to end of playlist.
        
        Args:
            url: Video URL or ID.
        """
        media_type, media_id = self._parse_media_url(url)
        await self.client.add_media(
            self.channel, media_type, media_id, position="end", domain=self.domain
        )
        print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_PLAYLIST} Added {Colors.CYAN}{media_type}:{media_id}{Colors.RESET} to end of playlist")
    
    async def cmd_playlist_addnext(self, url: str) -> None:
        """Add video to play next.
        
        Args:
            url: Video URL or ID.
        """
        media_type, media_id = self._parse_media_url(url)
        await self.client.add_media(
            self.channel, media_type, media_id, position="next", domain=self.domain
        )
        print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_PLAYLIST} Added {Colors.CYAN}{media_type}:{media_id}{Colors.RESET} to play {Colors.GREEN}next{Colors.RESET}")
    
    async def cmd_playlist_del(self, uid: str) -> None:
        """Delete video from playlist.
        
        Args:
            uid: Video UID or position number (1-based).
        """
        uid_int = int(uid)
        
        # If uid looks like a position (small number), fetch playlist and map position to UID
        # CyTube UIDs are typically 4+ digits, positions are 1-based small numbers
        if uid_int < 1000:  # Assume this is a position, not a UID
            bucket_name = f"cytube_{self.channel.lower()}_playlist"
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
                print(f"{Colors.EMOJI_SUCCESS} {Colors.RED}Deleted{Colors.RESET} position {Colors.BOLD}{uid_int}{Colors.RESET} (UID {actual_uid}): {Colors.DIM}{title}{Colors.RESET}")
            
            except Exception as e:
                print(f"Error resolving position {uid_int}: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Large number, treat as direct UID
            await self.client.delete_media(self.channel, uid_int, domain=self.domain)
            print(f"{Colors.EMOJI_SUCCESS} {Colors.RED}Deleted{Colors.RESET} media UID {Colors.BOLD}{uid}{Colors.RESET}")
    
    async def cmd_playlist_move(self, uid: str, after: str) -> None:
        """Move video in playlist.
        
        Args:
            uid: Video UID or position to move.
            after: UID or position to place after.
        """
        uid_int = int(uid)
        after_int = int(after)
        
        # Map positions to UIDs if needed (same logic as delete)
        bucket_name = f"cytube_{self.channel.lower()}_playlist"
        
        try:
            playlist = await self.client.kv_get(bucket_name, "items", default=None, parse_json=True)
            
            if playlist is None or not isinstance(playlist, list):
                print("Cannot resolve positions: playlist not available", file=sys.stderr)
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
            print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_PLAYLIST} Moved media {Colors.BOLD}{uid}{Colors.RESET} after {Colors.BOLD}{after}{Colors.RESET}")
        
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
        print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_SKIP} Jumped to media {Colors.BOLD}{uid}{Colors.RESET}")
    
    async def cmd_playlist_clear(self) -> None:
        """Clear entire playlist."""
        await self.client.clear_playlist(self.channel, domain=self.domain)
        print(f"{Colors.EMOJI_SUCCESS} {Colors.RED}Cleared{Colors.RESET} playlist in {Colors.CYAN}{self.channel}{Colors.RESET}")
    
    async def cmd_playlist_shuffle(self) -> None:
        """Shuffle playlist."""
        await self.client.shuffle_playlist(self.channel, domain=self.domain)
        print(f"{Colors.EMOJI_SUCCESS} 🔀 Shuffled playlist in {Colors.CYAN}{self.channel}{Colors.RESET}")
    
    async def cmd_playlist_settemp(self, uid: str, temp: bool) -> None:
        """Set video temporary status.
        
        Args:
            uid: Video UID.
            temp: Temporary status (true/false).
        """
        uid_int = int(uid)
        await self.client.set_temp(self.channel, uid_int, temp, domain=self.domain)
        temp_color = Colors.YELLOW if temp else Colors.GREEN
        print(f"{Colors.EMOJI_SUCCESS} Set temp={temp_color}{temp}{Colors.RESET} for media {Colors.BOLD}{uid}{Colors.RESET}")
    
    # ========================================================================
    # Playback Commands
    # ========================================================================
    
    async def cmd_pause(self) -> None:
        """Pause playback."""
        await self.client.pause(self.channel, domain=self.domain)
        print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_PAUSE} {Colors.YELLOW}Paused{Colors.RESET} playback in {Colors.CYAN}{self.channel}{Colors.RESET}")
    
    async def cmd_play(self) -> None:
        """Resume playback."""
        await self.client.play(self.channel, domain=self.domain)
        print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_PLAY} {Colors.GREEN}Resumed{Colors.RESET} playback in {Colors.CYAN}{self.channel}{Colors.RESET}")
    
    async def cmd_seek(self, time: float) -> None:
        """Seek to timestamp.
        
        Args:
            time: Target time in seconds.
        """
        await self.client.seek(self.channel, time, domain=self.domain)
        print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_CLOCK} Seeked to {Colors.CYAN}{time}s{Colors.RESET} in {self.channel}")
    
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
        print(f"{Colors.EMOJI_SUCCESS} Kicked {Colors.BOLD}{username}{Colors.RESET} from {self.channel}")
    
    async def cmd_ban(self, username: str, reason: Optional[str] = None) -> None:
        """Ban user from channel.
        
        Args:
            username: Username to ban.
            reason: Optional ban reason.
        """
        await self.client.ban_user(self.channel, username, reason, domain=self.domain)
        print(f"{Colors.EMOJI_BAN} Banned {Colors.BOLD}{username}{Colors.RESET} from {self.channel}")
    
    async def cmd_voteskip(self) -> None:
        """Vote to skip current video."""
        await self.client.voteskip(self.channel, domain=self.domain)
        print(f"{Colors.EMOJI_SKIP} Voted to skip in {self.channel}")
    
    # ========================================================================
    # Persistent Moderator Commands (kryten-moderator service)
    # ========================================================================
    
    async def _moderator_request(self, command: str, **kwargs) -> dict:
        """Send a request to kryten-moderator and return the response.
        
        Args:
            command: Command name (e.g., "entry.add")
            **kwargs: Additional command parameters
            
        Returns:
            Response dict with success and data/error
        """
        request = {
            "service": "moderator",
            "command": command,
            "domain": self.domain,
            "channel": self.channel,
            **kwargs,
        }
        
        try:
            response = await self.client.nats_request(
                "kryten.moderator.command",
                request,
                timeout=5.0,
            )
            return response
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _format_action(self, action: str) -> str:
        """Format action with color and emoji."""
        if action == "ban":
            return f"{Colors.RED}{Colors.EMOJI_BAN} ban{Colors.RESET}"
        elif action == "smute":
            return f"{Colors.YELLOW}{Colors.EMOJI_MUTE} smute{Colors.RESET}"
        elif action == "mute":
            return f"{Colors.ORANGE}{Colors.EMOJI_MUTE} mute{Colors.RESET}"
        return action
    
    def _format_action_short(self, action: str) -> str:
        """Format action with color only (for tables)."""
        if action == "ban":
            return f"{Colors.RED}ban{Colors.RESET}"
        elif action == "smute":
            return f"{Colors.YELLOW}smute{Colors.RESET}"
        elif action == "mute":
            return f"{Colors.ORANGE}mute{Colors.RESET}"
        return action
    
    @staticmethod
    def _mask_ip(ip: str) -> str:
        """Mask IP for display privacy."""
        parts = ip.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}.x.x"
        return ip
    
    async def cmd_moderator_ban(
        self,
        username: str,
        reason: Optional[str] = None,
    ) -> None:
        """Add user to persistent ban list (kicks on join).
        
        Args:
            username: Username to ban
            reason: Optional reason for the ban
        """
        response = await self._moderator_request(
            "entry.add",
            username=username,
            action="ban",
            reason=reason,
            moderator="cli",
        )
        
        if response.get("success"):
            data = response.get("data", {})
            print(f"{Colors.EMOJI_SUCCESS} {Colors.RED}Banned{Colors.RESET} {Colors.BOLD}{data['username']}{Colors.RESET}")
            if data.get("reason"):
                print(f"   {Colors.DIM}Reason:{Colors.RESET} {data['reason']}")
        else:
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_moderator_unban(self, username: str) -> None:
        """Remove user from persistent ban list.
        
        Args:
            username: Username to unban
        """
        response = await self._moderator_request(
            "entry.remove",
            username=username,
        )
        
        if response.get("success"):
            print(f"{Colors.EMOJI_SUCCESS} Unbanned {Colors.BOLD}{username}{Colors.RESET}")
        else:
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_moderator_smute(
        self,
        username: str,
        reason: Optional[str] = None,
    ) -> None:
        """Shadow mute a user (they don't know they're muted).
        
        Args:
            username: Username to shadow mute
            reason: Optional reason
        """
        response = await self._moderator_request(
            "entry.add",
            username=username,
            action="smute",
            reason=reason,
            moderator="cli",
        )
        
        if response.get("success"):
            data = response.get("data", {})
            print(f"{Colors.EMOJI_SUCCESS} {Colors.YELLOW}Shadow muted{Colors.RESET} {Colors.BOLD}{data['username']}{Colors.RESET}")
            if data.get("reason"):
                print(f"   {Colors.DIM}Reason:{Colors.RESET} {data['reason']}")
        else:
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_moderator_unsmute(self, username: str) -> None:
        """Remove shadow mute from user.
        
        Args:
            username: Username to unshadow mute
        """
        response = await self._moderator_request(
            "entry.remove",
            username=username,
        )
        
        if response.get("success"):
            print(f"{Colors.EMOJI_SUCCESS} Removed shadow mute from {Colors.BOLD}{username}{Colors.RESET}")
        else:
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_moderator_mute(
        self,
        username: str,
        reason: Optional[str] = None,
    ) -> None:
        """Visible mute a user (they are notified).
        
        Args:
            username: Username to mute
            reason: Optional reason
        """
        response = await self._moderator_request(
            "entry.add",
            username=username,
            action="mute",
            reason=reason,
            moderator="cli",
        )
        
        if response.get("success"):
            data = response.get("data", {})
            print(f"{Colors.EMOJI_SUCCESS} {Colors.ORANGE}Muted{Colors.RESET} {Colors.BOLD}{data['username']}{Colors.RESET}")
            if data.get("reason"):
                print(f"   {Colors.DIM}Reason:{Colors.RESET} {data['reason']}")
        else:
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_moderator_unmute(self, username: str) -> None:
        """Remove visible mute from user.
        
        Args:
            username: Username to unmute
        """
        response = await self._moderator_request(
            "entry.remove",
            username=username,
        )
        
        if response.get("success"):
            print(f"{Colors.EMOJI_SUCCESS} Unmuted {Colors.BOLD}{username}{Colors.RESET}")
        else:
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_moderator_list(
        self,
        filter_action: Optional[str] = None,
        format: str = "table",
    ) -> None:
        """List all moderated users.
        
        Args:
            filter_action: Optional filter (ban, smute, mute)
            format: Output format (table or json)
        """
        response = await self._moderator_request(
            "entry.list",
            filter=filter_action,
        )
        
        if not response.get("success"):
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
            sys.exit(1)
        
        data = response.get("data", {})
        entries = data.get("entries", [])
        
        if format == "json":
            print(json.dumps(data, indent=2))
            return
        
        if not entries:
            print(f"{Colors.EMOJI_INFO} No moderation entries found.")
            return
        
        # Print header
        print(f"\n{Colors.BOLD}{Colors.EMOJI_BAN} Moderation List{Colors.RESET}")
        print(f"Total entries: {Colors.CYAN}{data.get('count', len(entries))}{Colors.RESET}")
        print(f"{Colors.DIM}{'-' * 80}{Colors.RESET}")
        print(f"{Colors.BOLD}{'Username':<20} {'Action':<12} {'Reason':<25} {'Moderator':<15}{Colors.RESET}")
        print(f"{Colors.DIM}{'-' * 80}{Colors.RESET}")
        
        for entry in entries:
            action_colored = self._format_action_short(entry["action"])
            reason = (entry.get("reason") or "")[:23]
            if len(entry.get("reason") or "") > 23:
                reason += ".."
            moderator = (entry.get("moderator") or "")[:13]
            
            # Action column needs extra space to account for ANSI codes
            print(f"{entry['username']:<20} {action_colored:<21} {reason:<25} {moderator:<15}")
        
        print(f"{Colors.DIM}{'-' * 80}{Colors.RESET}")
    
    async def cmd_moderator_check(
        self,
        username: str,
        format: str = "text",
    ) -> None:
        """Check moderation status of a user.
        
        Args:
            username: Username to check
            format: Output format (text or json)
        """
        response = await self._moderator_request(
            "entry.get",
            username=username,
        )
        
        if not response.get("success"):
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
            sys.exit(1)
        
        data = response.get("data", {})
        
        if format == "json":
            print(json.dumps(data, indent=2))
            return
        
        if not data.get("entry"):
            print(f"{Colors.EMOJI_USER} User {Colors.BOLD}{username}{Colors.RESET} is {Colors.GREEN}not moderated{Colors.RESET}")
            return
        
        entry = data["entry"]
        action_colored = self._format_action(entry["action"])
        print(f"\n{Colors.BOLD}{Colors.EMOJI_USER} Moderation Status: {entry['username']}{Colors.RESET}")
        print(f"{Colors.DIM}{'-' * 40}{Colors.RESET}")
        print(f"  {Colors.BOLD}Action:{Colors.RESET}    {action_colored}")
        print(f"  {Colors.BOLD}Reason:{Colors.RESET}    {entry.get('reason') or '(none)'}")
        print(f"  {Colors.BOLD}Moderator:{Colors.RESET} {entry.get('moderator')}")
        print(f"  {Colors.BOLD}Timestamp:{Colors.RESET} {entry.get('timestamp')}")
        
        if entry.get("ips"):
            masked = [self._mask_ip(ip) for ip in entry["ips"]]
            print(f"  {Colors.BOLD}IPs:{Colors.RESET}       {', '.join(masked)}")
        
        if entry.get("ip_correlation_source"):
            print(f"  {Colors.BOLD}Correlated from:{Colors.RESET} {Colors.YELLOW}{entry['ip_correlation_source']}{Colors.RESET}")
        
        if entry.get("pattern_match"):
            print(f"  {Colors.BOLD}Pattern match:{Colors.RESET} {Colors.MAGENTA}{entry['pattern_match']}{Colors.RESET}")
        
        print(f"{Colors.DIM}{'-' * 40}{Colors.RESET}")
    
    # ========================================================================
    # Pattern Commands (kryten-moderator service)
    # ========================================================================
    
    async def cmd_moderator_patterns_list(self, format: str = "table") -> None:
        """List all banned username patterns.
        
        Args:
            format: Output format (table or json)
        """
        response = await self._moderator_request("pattern.list")
        
        if not response.get("success"):
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
            sys.exit(1)
        
        data = response.get("data", {})
        patterns = data.get("patterns", [])
        
        if format == "json":
            print(json.dumps(data, indent=2))
            return
        
        if not patterns:
            print(f"{Colors.EMOJI_INFO} No patterns configured.")
            return
        
        print(f"\n{Colors.BOLD}{Colors.EMOJI_PATTERN} Banned Username Patterns{Colors.RESET}")
        print(f"Total patterns: {Colors.CYAN}{data.get('count', len(patterns))}{Colors.RESET}")
        print(f"{Colors.DIM}{'-' * 85}{Colors.RESET}")
        print(f"{Colors.BOLD}{'Pattern':<25} {'Type':<10} {'Action':<12} {'Description':<30}{Colors.RESET}")
        print(f"{Colors.DIM}{'-' * 85}{Colors.RESET}")
        
        for p in patterns:
            ptype = f"{Colors.MAGENTA}regex{Colors.RESET}" if p.get("is_regex") else "substring"
            action_colored = self._format_action_short(p["action"])
            desc = (p.get("description") or "")[:28]
            if len(p.get("description") or "") > 28:
                desc += ".."
            pattern_display = p["pattern"][:23]
            if len(p["pattern"]) > 23:
                pattern_display += ".."
            
            # Adjust column widths for ANSI codes
            type_width = 19 if p.get("is_regex") else 10
            print(f"{pattern_display:<25} {ptype:<{type_width}} {action_colored:<21} {desc:<30}")
        
        print(f"{Colors.DIM}{'-' * 85}{Colors.RESET}")
    
    async def cmd_moderator_patterns_add(
        self,
        pattern: str,
        is_regex: bool = False,
        action: str = "ban",
        description: Optional[str] = None,
    ) -> None:
        """Add a banned username pattern.
        
        Args:
            pattern: Pattern string (substring or regex)
            is_regex: Whether pattern is a regex
            action: Action to take on match (ban, smute, mute)
            description: Optional description
        """
        response = await self._moderator_request(
            "pattern.add",
            pattern=pattern,
            is_regex=is_regex,
            action=action,
            added_by="cli",
            description=description,
        )
        
        if response.get("success"):
            data = response.get("data", {})
            ptype = f"{Colors.MAGENTA}regex{Colors.RESET}" if data.get("is_regex") else "substring"
            action_colored = self._format_action_short(data["action"])
            print(f"{Colors.EMOJI_SUCCESS} Added pattern: {Colors.BOLD}{data['pattern']}{Colors.RESET}")
            print(f"   Type: {ptype}, Action: {action_colored}")
        else:
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_moderator_patterns_remove(self, pattern: str) -> None:
        """Remove a banned username pattern.
        
        Args:
            pattern: Pattern string to remove
        """
        response = await self._moderator_request(
            "pattern.remove",
            pattern=pattern,
        )
        
        if response.get("success"):
            print(f"{Colors.EMOJI_SUCCESS} Removed pattern: {Colors.BOLD}{pattern}{Colors.RESET}")
        else:
            print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error')}", file=sys.stderr)
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
                print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error', 'Unknown error')}")
                print(f"Is Kryten-Robot running for channel '{self.channel}'?")
                return
            
            playlist = response.get("data", {}).get("playlist", [])
            
            if not playlist:
                print(f"{Colors.EMOJI_INFO} Playlist is empty.")
                return
            
            print(f"\n{Colors.BOLD}{Colors.EMOJI_PLAYLIST} {self.channel} Playlist{Colors.RESET} ({Colors.CYAN}{len(playlist)}{Colors.RESET} items):")
            print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")
            
            for i, item in enumerate(playlist, 1):
                media = item.get("media", {})
                title = media.get("title", "Unknown")
                duration = media.get("duration", "--:--")
                media_type = media.get("type", "??")
                uid = item.get("uid", "")
                temp = f" {Colors.YELLOW}[TEMP]{Colors.RESET}" if item.get("temp") else ""
                queueby = item.get("queueby", "")
                
                print(f"{Colors.CYAN}{i:3}.{Colors.RESET} [{Colors.MAGENTA}{media_type}{Colors.RESET}] {title}")
                print(f"     {Colors.DIM}Duration:{Colors.RESET} {duration} | {Colors.DIM}UID:{Colors.RESET} {uid}{temp}")
                if queueby:
                    print(f"     {Colors.DIM}Queued by:{Colors.RESET} {Colors.BOLD}{queueby}{Colors.RESET}")
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
                print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error', 'Unknown error')}")
                print(f"Is Kryten-Robot running for channel '{self.channel}'?")
                return
            
            users = response.get("data", {}).get("userlist", [])
            
            if not users:
                print(f"{Colors.EMOJI_INFO} No users online.")
                return
            
            # Sort by rank (descending) then name
            users_sorted = sorted(users, key=lambda u: (-u.get("rank", 0), u.get("name", "").lower()))
            
            print(f"\n{Colors.BOLD}{Colors.EMOJI_USER} {self.channel} Users{Colors.RESET} ({Colors.CYAN}{len(users)}{Colors.RESET} online):")
            print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")
            
            rank_names = {
                0: ("Guest", Colors.GRAY),
                1: ("Registered", Colors.RESET),
                2: ("Moderator", Colors.GREEN),
                3: ("Channel Admin", Colors.CYAN),
                4: ("Site Admin", Colors.MAGENTA),
            }
            
            for user in users_sorted:
                name = user.get("name", "Unknown")
                rank = user.get("rank", 0)
                rank_name, rank_color = rank_names.get(rank, (f"Rank {rank}", Colors.RESET))
                afk = f" {Colors.YELLOW}[AFK]{Colors.RESET}" if user.get("meta", {}).get("afk") else ""
                
                print(f"  {rank_color}[{rank}]{Colors.RESET} {Colors.BOLD}{name}{Colors.RESET} - {rank_color}{rank_name}{Colors.RESET}{afk}")
        
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
                print(f"{Colors.EMOJI_ERROR} {Colors.RED}Error:{Colors.RESET} {response.get('error', 'Unknown error')}")
                print(f"Is Kryten-Robot running for channel '{self.channel}'?")
                return
            
            emotes = response.get("data", {}).get("emotes", [])
            
            if not emotes:
                print(f"{Colors.EMOJI_INFO} No custom emotes configured.")
                return
            
            print(f"\n{Colors.BOLD}😀 {self.channel} Custom Emotes{Colors.RESET} ({Colors.CYAN}{len(emotes)}{Colors.RESET} total):")
            print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")
            
            for emote in emotes:
                name = emote.get("name", "Unknown")
                image = emote.get("image", "")
                
                # Truncate long URLs for display
                if len(image) > 60:
                    image_display = image[:57] + "..."
                else:
                    image_display = image
                
                print(f"  {Colors.CYAN}{name:30}{Colors.RESET} {Colors.DIM}{image_display}{Colors.RESET}")
        
        except Exception as e:
            print(f"Error retrieving emotes: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_system_stats(self, format: str = "text") -> None:
        """Display Kryten-Robot runtime statistics."""
        try:
            stats = await self.client.get_stats()
            
            if format == "json":
                print(json.dumps(stats, indent=2))
                return
            
            # Text format
            uptime_hours = stats.get("uptime_seconds", 0) / 3600
            events = stats.get("events", {})
            commands = stats.get("commands", {})
            connections = stats.get("connections", {})
            state = stats.get("state", {})
            memory = stats.get("memory", {})
            
            print(f"\n{Colors.BOLD}{Colors.EMOJI_STATS} Kryten-Robot Runtime Statistics{Colors.RESET}")
            print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")
            print(f"\n{Colors.BOLD}Uptime:{Colors.RESET} {Colors.CYAN}{uptime_hours:.2f}{Colors.RESET} hours")
            
            print(f"\n{Colors.BOLD}Events:{Colors.RESET}")
            print(f"  Total Published:   {Colors.CYAN}{events.get('total_published', 0):,}{Colors.RESET}")
            print(f"  Rate (1 min):      {events.get('rate_1min', 0):.2f} events/sec")
            print(f"  Rate (5 min):      {events.get('rate_5min', 0):.2f} events/sec")
            print(f"  Last Event:        {Colors.MAGENTA}{events.get('last_event_type', 'N/A')}{Colors.RESET}")
            print(f"  Last Event Time:   {events.get('last_event_time', 'N/A')}")
            
            print(f"\n{Colors.BOLD}Commands:{Colors.RESET}")
            print(f"  Total Received:    {Colors.CYAN}{commands.get('total_received', 0):,}{Colors.RESET}")
            print(f"  Succeeded:         {Colors.GREEN}{commands.get('succeeded', 0):,}{Colors.RESET}")
            print(f"  Failed:            {Colors.RED}{commands.get('failed', 0):,}{Colors.RESET}")
            print(f"  Rate (1 min):      {commands.get('rate_1min', 0):.2f} commands/sec")
            print(f"  Rate (5 min):      {commands.get('rate_5min', 0):.2f} commands/sec")
            
            cytube = connections.get("cytube", {})
            nats = connections.get("nats", {})
            
            print(f"\n{Colors.BOLD}Connections:{Colors.RESET}")
            cytube_status = f"{Colors.GREEN}True{Colors.RESET}" if cytube.get('connected', False) else f"{Colors.RED}False{Colors.RESET}"
            nats_status = f"{Colors.GREEN}True{Colors.RESET}" if nats.get('connected', False) else f"{Colors.RED}False{Colors.RESET}"
            print(f"  {Colors.CYAN}CyTube:{Colors.RESET}")
            print(f"    Connected:       {cytube_status}")
            print(f"    Connected Since: {cytube.get('connected_since', 'N/A')}")
            print(f"    Reconnect Count: {cytube.get('reconnect_count', 0)}")
            print(f"    Last Event:      {cytube.get('last_event_time', 'N/A')}")
            print(f"  {Colors.CYAN}NATS:{Colors.RESET}")
            print(f"    Connected:       {nats_status}")
            print(f"    Connected Since: {nats.get('connected_since', 'N/A')}")
            print(f"    Reconnect Count: {nats.get('reconnect_count', 0)}")
            print(f"    Server:          {nats.get('connected_url', 'N/A')}")
            
            print(f"\n{Colors.BOLD}Channel State:{Colors.RESET}")
            print(f"  Users:             {Colors.CYAN}{state.get('users', 0)}{Colors.RESET}")
            print(f"  Playlist Items:    {Colors.CYAN}{state.get('playlist', 0)}{Colors.RESET}")
            print(f"  Emotes:            {Colors.CYAN}{state.get('emotes', 0)}{Colors.RESET}")
            
            if memory:
                print(f"\n{Colors.BOLD}Memory Usage:{Colors.RESET}")
                print(f"  RSS:               {memory.get('rss_mb', 0):.1f} MB")
                print(f"  VMS:               {memory.get('vms_mb', 0):.1f} MB")
            
        except Exception as e:
            print(f"Error retrieving stats: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_system_config(self, format: str = "text") -> None:
        """Display Kryten-Robot configuration."""
        try:
            config = await self.client.get_config()
            
            if format == "json":
                print(json.dumps(config, indent=2))
                return
            
            # Text format - display key settings
            print(f"\n{Colors.BOLD}{Colors.EMOJI_CONFIG} Kryten-Robot Configuration{Colors.RESET}")
            print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")
            
            cytube = config.get("cytube", {})
            nats = config.get("nats", {})
            commands_cfg = config.get("commands", {})
            health = config.get("health", {})
            
            print(f"\n{Colors.BOLD}CyTube:{Colors.RESET}")
            print(f"  Domain:            {Colors.CYAN}{cytube.get('domain', 'N/A')}{Colors.RESET}")
            print(f"  Channel:           {Colors.CYAN}{cytube.get('channel', 'N/A')}{Colors.RESET}")
            print(f"  Username:          {Colors.GREEN}{cytube.get('username', 'N/A')}{Colors.RESET}")
            print(f"  Password:          {Colors.DIM}********{Colors.RESET}")
            
            print(f"\n{Colors.BOLD}NATS:{Colors.RESET}")
            servers = nats.get("servers", [])
            if isinstance(servers, list):
                for i, server in enumerate(servers):
                    print(f"  Server {i+1}:          {Colors.CYAN}{server}{Colors.RESET}")
            print(f"  User:              {nats.get('user', 'N/A')}")
            print(f"  Password:          {Colors.DIM}********{Colors.RESET}")
            
            cmd_enabled = f"{Colors.GREEN}True{Colors.RESET}" if commands_cfg.get('enabled', False) else f"{Colors.RED}False{Colors.RESET}"
            health_enabled = f"{Colors.GREEN}True{Colors.RESET}" if health.get('enabled', False) else f"{Colors.RED}False{Colors.RESET}"
            
            print(f"\n{Colors.BOLD}Commands:{Colors.RESET}")
            print(f"  Enabled:           {cmd_enabled}")
            
            print(f"\n{Colors.BOLD}Health:{Colors.RESET}")
            print(f"  Enabled:           {health_enabled}")
            print(f"  Host:              {health.get('host', 'N/A')}")
            print(f"  Port:              {health.get('port', 'N/A')}")
            
            print(f"\n{Colors.BOLD}Log Level:{Colors.RESET}           {Colors.MAGENTA}{config.get('log_level', 'N/A')}{Colors.RESET}")
            
        except Exception as e:
            print(f"Error retrieving config: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_system_ping(self) -> None:
        """Check if Kryten-Robot is alive."""
        try:
            result = await self.client.ping()
            result.get("pong", False)
            timestamp = result.get("timestamp", "N/A")
            uptime = result.get("uptime_seconds", 0)
            version = result.get("version", "N/A")
            
            print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_PING} Kryten-Robot is {Colors.GREEN}alive{Colors.RESET}")
            print(f"   {Colors.DIM}Timestamp:{Colors.RESET} {timestamp}")
            print(f"   {Colors.DIM}Uptime:{Colors.RESET} {Colors.CYAN}{uptime / 3600:.2f}{Colors.RESET} hours")
            print(f"   {Colors.DIM}Version:{Colors.RESET} {Colors.MAGENTA}{version}{Colors.RESET}")
            
        except TimeoutError:
            print(f"{Colors.EMOJI_ERROR} Kryten-Robot is {Colors.RED}not responding{Colors.RESET}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"{Colors.EMOJI_ERROR} Error pinging robot: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_system_services(self, format: str = "text") -> None:
        """Display registered microservices."""
        try:
            data = await self.client.get_services()
            
            if format == "json":
                print(json.dumps(data, indent=2))
                return
            
            services = data.get("services", [])
            count = data.get("count", 0)
            active_count = data.get("active_count", 0)
            
            if not services:
                print(f"\n{Colors.EMOJI_INFO} No microservices registered.")
                print(f"{Colors.DIM}Services register when they start and send heartbeats.{Colors.RESET}")
                return
            
            print(f"\n{Colors.BOLD}🔌 Registered Microservices{Colors.RESET}")
            print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")
            print(f"Total: {Colors.CYAN}{count}{Colors.RESET} | Active: {Colors.GREEN}{active_count}{Colors.RESET} | Stale: {Colors.RED}{count - active_count}{Colors.RESET}")
            
            for svc in services:
                name = svc.get("name", "unknown")
                version = svc.get("version", "?")
                hostname = svc.get("hostname", "unknown")
                is_stale = svc.get("is_stale", False)
                seconds_since = svc.get("seconds_since_heartbeat", 0)
                last_heartbeat = svc.get("last_heartbeat", "N/A")
                health_url = svc.get("health_url")
                metrics_url = svc.get("metrics_url")
                
                # Status indicator
                if is_stale:
                    status = f"{Colors.RED}✗ STALE{Colors.RESET}"
                else:
                    status = f"{Colors.GREEN}✓ Active{Colors.RESET}"
                
                print(f"\n  {Colors.BOLD}{name}{Colors.RESET} v{Colors.CYAN}{version}{Colors.RESET} [{status}]")
                print(f"    {Colors.DIM}Hostname:{Colors.RESET}       {hostname}")
                print(f"    {Colors.DIM}Last Heartbeat:{Colors.RESET} {last_heartbeat} ({seconds_since:.0f}s ago)")
                
                if health_url:
                    print(f"    {Colors.DIM}Health:{Colors.RESET}         {Colors.BLUE}{health_url}{Colors.RESET}")
                if metrics_url:
                    print(f"    {Colors.DIM}Metrics:{Colors.RESET}        {Colors.BLUE}{metrics_url}{Colors.RESET}")
                
                if not health_url and not metrics_url:
                    print(f"    {Colors.DIM}Endpoints:{Colors.RESET}      {Colors.YELLOW}Not configured{Colors.RESET}")
            
            print()  # Final newline
            
        except Exception as e:
            print(f"Error retrieving services: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_system_reload(self, config_path: Optional[str] = None) -> None:
        """Reload Kryten-Robot configuration."""
        try:
            result = await self.client.reload_config(config_path)
            
            success = result.get("success", False)
            message = result.get("message", "")
            changes = result.get("changes", {})
            errors = result.get("errors", [])
            
            if success:
                print(f"{Colors.EMOJI_SUCCESS} {message}")
            else:
                print(f"{Colors.EMOJI_WARNING} {message}")
            
            if changes:
                print(f"\n{Colors.BOLD}Changes:{Colors.RESET}")
                for key, change in changes.items():
                    print(f"  {Colors.GREEN}•{Colors.RESET} {key}: {change}")
            else:
                print(f"\n{Colors.DIM}No changes detected.{Colors.RESET}")
            
            if errors:
                print(f"\n{Colors.EMOJI_ERROR} {Colors.RED}Errors:{Colors.RESET}")
                for error in errors:
                    print(f"  • {error}")
                sys.exit(1)
                
        except Exception as e:
            print(f"Error reloading config: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_system_shutdown(
        self,
        delay: int = 0,
        reason: str = "Remote shutdown via CLI",
        confirm: bool = True
    ) -> None:
        """Shutdown Kryten-Robot gracefully."""
        try:
            # Confirmation prompt
            if confirm:
                if delay > 0:
                    prompt = f"{Colors.EMOJI_WARNING} {Colors.YELLOW}Shutdown Kryten-Robot in {delay} seconds?{Colors.RESET} [y/N]: "
                else:
                    prompt = f"{Colors.EMOJI_WARNING} {Colors.RED}Shutdown Kryten-Robot immediately?{Colors.RESET} [y/N]: "
                
                response = input(prompt).strip().lower()
                if response not in ["y", "yes"]:
                    print(f"{Colors.DIM}Shutdown cancelled.{Colors.RESET}")
                    return
            
            result = await self.client.shutdown(delay, reason)
            
            success = result.get("success", False)
            message = result.get("message", "")
            delay_actual = result.get("delay_seconds", 0)
            shutdown_time = result.get("shutdown_time", "N/A")
            
            if success:
                print(f"{Colors.EMOJI_SUCCESS} {Colors.EMOJI_SHUTDOWN} {message}")
                if delay_actual > 0:
                    print(f"   {Colors.DIM}Shutdown scheduled:{Colors.RESET} {shutdown_time}")
                    print(f"   {Colors.DIM}Delay:{Colors.RESET} {Colors.CYAN}{delay_actual}{Colors.RESET} seconds")
                print(f"   {Colors.DIM}Reason:{Colors.RESET} {reason}")
            else:
                print(f"{Colors.EMOJI_ERROR} Shutdown failed: {message}", file=sys.stderr)
                sys.exit(1)
                
        except Exception as e:
            print(f"Error shutting down robot: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_userstats_all(
        self,
        format: str = "text",
        top_users: int = 20,
        media_history: int = 15,
        leaderboards: int = 10
    ) -> None:
        """Fetch and display all channel statistics from userstats service."""
        try:
            # Build the request - channel and domain will be auto-discovered from running service
            request = {
                "service": "userstats",
                "command": "channel.all_stats",
                # Note: channel and domain are optional, service will use first configured channel
                "limits": {
                    "top_users": top_users,
                    "media_history": media_history,
                    "leaderboards": leaderboards
                }
            }
            
            # Send request using kryten-py public API
            response = await self.client.nats_request(
                "kryten.userstats.command",
                request,
                timeout=10.0
            )
            
            # Check for errors
            if not response.get("success"):
                error = response.get("error", "Unknown error")
                print(f"{Colors.EMOJI_ERROR} Error: {error}", file=sys.stderr)
                sys.exit(1)
            
            data = response.get("data", {})
            
            # Output format
            if format == "json":
                print(json.dumps(data, indent=2))
                return
            
            # Text report format
            print(f"\n{Colors.DIM}{'=' * 80}{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.EMOJI_STATS} Kryten User Statistics - Channel Report{Colors.RESET}")
            print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")
            
            # System section
            system = data.get("system", {})
            health = system.get("health", {})
            sys_stats = system.get("stats", {})
            
            status_color = Colors.GREEN if health.get('status') == 'healthy' else Colors.YELLOW
            print(f"\n{Colors.BOLD}--- System Health ---{Colors.RESET}")
            print(f"Service:        {Colors.CYAN}{health.get('service', 'N/A')}{Colors.RESET}")
            print(f"Status:         {status_color}{health.get('status', 'N/A')}{Colors.RESET}")
            print(f"Uptime:         {Colors.CYAN}{health.get('uptime_seconds', 0) / 3600:.2f}{Colors.RESET} hours")
            print(f"Events:         {Colors.CYAN}{sys_stats.get('events_processed', 0):,}{Colors.RESET}")
            print(f"Commands:       {Colors.CYAN}{sys_stats.get('commands_processed', 0):,}{Colors.RESET}")
            
            # Leaderboards section
            leaderboards_data = data.get("leaderboards", {})
            
            print(f"\n{Colors.BOLD}--- 🏆 Kudos Leaderboard ---{Colors.RESET}")
            for i, entry in enumerate(leaderboards_data.get("kudos", []), 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2}."
                print(f"{medal} {Colors.BOLD}{entry['username']:20}{Colors.RESET} {Colors.CYAN}{entry['count']:,}{Colors.RESET} kudos")
            
            print(f"\n{Colors.BOLD}--- 😀 Emote Leaderboard ---{Colors.RESET}")
            for i, entry in enumerate(leaderboards_data.get("emotes", []), 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2}."
                print(f"{medal} {Colors.MAGENTA}{entry['emote']:20}{Colors.RESET} {Colors.CYAN}{entry['count']:,}{Colors.RESET} uses")
            
            # Channel section
            channel = data.get("channel", {})
            
            print(f"\n{Colors.BOLD}--- {Colors.EMOJI_CHAT} Top Active Users ---{Colors.RESET}")
            for i, entry in enumerate(channel.get("top_users", []), 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2}."
                print(f"{medal} {Colors.BOLD}{entry['username']:20}{Colors.RESET} {Colors.CYAN}{entry['count']:,}{Colors.RESET} messages")
            
            population = channel.get("population", {})
            current_pop = population.get("current", {})
            print(f"\n{Colors.BOLD}--- {Colors.EMOJI_USER} Channel Population ---{Colors.RESET}")
            print(f"Current Online: {Colors.GREEN}{current_pop.get('connected_count', 0):,}{Colors.RESET} users")
            print(f"Current Chat:   {Colors.GREEN}{current_pop.get('chat_count', 0):,}{Colors.RESET} users")
            print(f"Last Update:    {Colors.DIM}{current_pop.get('timestamp', 'N/A')}{Colors.RESET}")
            
            watermarks = channel.get("watermarks", {})
            high = watermarks.get("high", {})
            low = watermarks.get("low", {})
            print(f"\n{Colors.BOLD}--- 📈 Activity Watermarks ---{Colors.RESET}")
            print(f"Peak Online:    {Colors.GREEN}{high.get('total_users', 0)}{Colors.RESET} users at {Colors.DIM}{high.get('timestamp', 'N/A')}{Colors.RESET}")
            print(f"Low Online:     {Colors.YELLOW}{low.get('total_users', 0)}{Colors.RESET} users at {Colors.DIM}{low.get('timestamp', 'N/A')}{Colors.RESET}")
            
            print(f"\n{Colors.BOLD}--- {Colors.EMOJI_PLAYLIST} Recent Media ---{Colors.RESET}")
            for i, entry in enumerate(channel.get("media_history", []), 1):
                title = entry.get("media_title", "Unknown")
                media_type = entry.get("media_type", "?")
                timestamp = entry.get("timestamp", "N/A")
                # Format timestamp to be more readable
                if timestamp != "N/A" and "T" in timestamp:
                    timestamp = timestamp.split("T")[1].split("+")[0][:8]  # Just HH:MM:SS
                print(f"{Colors.CYAN}{i:2}.{Colors.RESET} [{Colors.MAGENTA}{media_type:2}{Colors.RESET}] {title[:55]:55} {Colors.DIM}{timestamp}{Colors.RESET}")
            
            movie_votes = channel.get("movie_votes", [])
            if movie_votes:
                print(f"\n{Colors.BOLD}--- 🎬 Movie Votes ---{Colors.RESET}")
                for i, entry in enumerate(movie_votes, 1):
                    title = entry.get("title", "Unknown")
                    votes = entry.get("votes", 0)
                    print(f"{Colors.CYAN}{i:2}.{Colors.RESET} {title[:55]:55} {Colors.GREEN}{votes:3}{Colors.RESET} votes")
            
            print(f"\n{Colors.DIM}{'=' * 80}{Colors.RESET}")
            
        except TimeoutError:
            print(f"{Colors.EMOJI_ERROR} Timeout: No response from userstats service", file=sys.stderr)
            print("   Is kryten-userstats running?", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"{Colors.EMOJI_ERROR} Error fetching statistics: {e}", file=sys.stderr)
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
        help="CyTube channel name (auto-discovered if not specified)"
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
        help="Path to configuration file (default: /etc/kryten/kryten-cli/config.json or ./config.json)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Chat commands
    say_parser = subparsers.add_parser("say", help="Send a chat message")
    say_parser.add_argument("message", help="Message text")
    
    pm_parser = subparsers.add_parser("pm", help="Send a private message")
    pm_parser.add_argument("username", help="Target username")
    pm_parser.add_argument("message", help="Message text")
    
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
    
    # System commands
    system_parser = subparsers.add_parser("system", help="System management commands")
    system_subparsers = system_parser.add_subparsers(dest="system_cmd")
    
    stats_parser = system_subparsers.add_parser("stats", help="Show runtime statistics")
    stats_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    
    config_parser = system_subparsers.add_parser("config", help="Show configuration")
    config_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    
    system_subparsers.add_parser("ping", help="Check if robot is alive")
    
    services_parser = system_subparsers.add_parser("services", help="Show registered microservices")
    services_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    
    reload_parser = system_subparsers.add_parser("reload", help="Reload configuration")
    reload_parser.add_argument(
        "--config",
        dest="reload_config_path",
        help="Path to config file (uses current if not specified)"
    )
    
    shutdown_parser = system_subparsers.add_parser("shutdown", help="Shutdown robot")
    shutdown_parser.add_argument(
        "--delay",
        type=int,
        default=0,
        help="Seconds to wait before shutdown (0-300, default: 0)"
    )
    shutdown_parser.add_argument(
        "--reason",
        default="Remote shutdown via CLI",
        help="Reason for shutdown (for logging)"
    )
    shutdown_parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    # Userstats commands
    userstats_parser = subparsers.add_parser("userstats", help="User statistics commands")
    userstats_subparsers = userstats_parser.add_subparsers(dest="userstats_cmd")
    
    all_stats_parser = userstats_subparsers.add_parser(
        "all",
        help="Fetch all channel statistics"
    )
    all_stats_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    all_stats_parser.add_argument(
        "--top-users",
        type=int,
        default=20,
        help="Number of top users to show (default: 20)"
    )
    all_stats_parser.add_argument(
        "--media-history",
        type=int,
        default=15,
        help="Number of recent media items to show (default: 15)"
    )
    all_stats_parser.add_argument(
        "--leaderboards",
        type=int,
        default=10,
        help="Number of leaderboard entries to show (default: 10)"
    )
    
    # ========================================================================
    # Moderator Commands (persistent moderation via kryten-moderator service)
    # ========================================================================
    
    moderator_parser = subparsers.add_parser(
        "moderator",
        aliases=["mod"],
        help="🔨 Persistent moderation (ban/mute list management)",
        description="Manage the persistent moderation list for automatic enforcement on join.",
    )
    moderator_sub = moderator_parser.add_subparsers(dest="moderator_cmd")
    
    # moderator ban
    mod_ban = moderator_sub.add_parser(
        "ban",
        help="Add user to ban list (kicks on join)",
        description="Add a user to the persistent ban list. They will be kicked whenever they try to join.",
    )
    mod_ban.add_argument("username", help="Username to ban")
    mod_ban.add_argument("reason", nargs="?", help="Reason for ban (optional)")
    
    # moderator unban
    mod_unban = moderator_sub.add_parser(
        "unban",
        help="Remove user from ban list",
    )
    mod_unban.add_argument("username", help="Username to unban")
    
    # moderator smute
    mod_smute = moderator_sub.add_parser(
        "smute",
        help="Shadow mute user (they don't know they're muted)",
        description="Shadow mute a user. Their messages will only be visible to moderators. The user is not notified.",
    )
    mod_smute.add_argument("username", help="Username to shadow mute")
    mod_smute.add_argument("reason", nargs="?", help="Reason for mute (optional)")
    
    # moderator unsmute
    mod_unsmute = moderator_sub.add_parser(
        "unsmute",
        help="Remove shadow mute from user",
    )
    mod_unsmute.add_argument("username", help="Username to unshadow mute")
    
    # moderator mute
    mod_mute = moderator_sub.add_parser(
        "mute",
        help="Visible mute user (they are notified)",
        description="Mute a user with notification. They will see they've been muted.",
    )
    mod_mute.add_argument("username", help="Username to mute")
    mod_mute.add_argument("reason", nargs="?", help="Reason for mute (optional)")
    
    # moderator unmute
    mod_unmute = moderator_sub.add_parser(
        "unmute",
        help="Remove visible mute from user",
    )
    mod_unmute.add_argument("username", help="Username to unmute")
    
    # moderator list
    mod_list = moderator_sub.add_parser(
        "list",
        help="List all moderated users",
    )
    mod_list.add_argument(
        "--filter",
        choices=["ban", "smute", "mute"],
        help="Filter by action type",
    )
    mod_list.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    
    # moderator check
    mod_check = moderator_sub.add_parser(
        "check",
        help="Check moderation status of a user",
    )
    mod_check.add_argument("username", help="Username to check")
    mod_check.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    
    # moderator patterns
    mod_patterns = moderator_sub.add_parser(
        "patterns",
        help="🎯 Manage banned username patterns",
    )
    patterns_sub = mod_patterns.add_subparsers(dest="patterns_cmd")
    
    # patterns list
    pat_list = patterns_sub.add_parser(
        "list",
        help="List all patterns",
    )
    pat_list.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format",
    )
    
    # patterns add
    pat_add = patterns_sub.add_parser(
        "add",
        help="Add a pattern",
    )
    pat_add.add_argument("pattern", help="Pattern string")
    pat_add.add_argument(
        "--regex",
        action="store_true",
        help="Treat pattern as regex (default: substring)",
    )
    pat_add.add_argument(
        "--action",
        choices=["ban", "smute", "mute"],
        default="ban",
        help="Action to take on match (default: ban)",
    )
    pat_add.add_argument(
        "--description",
        "-d",
        help="Description of pattern",
    )
    
    # patterns remove
    pat_remove = patterns_sub.add_parser(
        "remove",
        help="Remove a pattern",
    )
    pat_remove.add_argument("pattern", help="Pattern string to remove")
    
    return parser


async def main() -> None:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # System and userstats commands don't need a channel (they query services directly)
    # Skip channel discovery for these commands
    is_system_command = args.command in ["system", "userstats"]
    
    # Auto-discover channel if not specified (unless it's a system command)
    channel = args.channel
    
    if not is_system_command and not channel:
        # Connect temporarily to discover channels
        temp_cli = KrytenCLI(
            channel="_discovery",  # Placeholder channel for discovery
            domain=args.domain,
            nats_servers=args.nats_servers,
            config_path=args.config,
        )
        
        try:
            await temp_cli.connect()
            
            # Discover channels
            try:
                channels = await temp_cli.client.get_channels(timeout=2.0)
                
                if not channels:
                    print("Error: No channels found. Is Kryten-Robot running?", file=sys.stderr)
                    print("  Start Kryten-Robot or specify --channel manually.", file=sys.stderr)
                    sys.exit(1)
                
                if len(channels) == 1:
                    # Single channel - use it automatically
                    channel_info = channels[0]
                    channel = channel_info["channel"]
                    domain = channel_info["domain"]
                    print(f"Auto-discovered channel: {domain}/{channel}")
                    
                    # Update args with discovered values
                    args.domain = domain
                else:
                    # Multiple channels - user must specify
                    print("Error: Multiple channels found. Please specify --channel:", file=sys.stderr)
                    for ch in channels:
                        print(f"  {ch['domain']}/{ch['channel']}", file=sys.stderr)
                    sys.exit(1)
                
            except TimeoutError:
                print("Error: Channel discovery timed out. Is Kryten-Robot running?", file=sys.stderr)
                print("  Start Kryten-Robot or specify --channel manually.", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error: Channel discovery failed: {e}", file=sys.stderr)
                print("  Specify --channel manually.", file=sys.stderr)
                sys.exit(1)
            
        finally:
            await temp_cli.disconnect()
    
    # For system commands, use placeholder channel (not actually used)
    # For other commands, channel is required at this point
    if is_system_command and not channel:
        # System commands query robot service, not channel-specific subjects
        # Use placeholder to satisfy KrytenClient config validation
        channel = "_system"
    
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
        
        elif args.command == "system":
            if args.system_cmd == "stats":
                await cli.cmd_system_stats(args.format)
            elif args.system_cmd == "config":
                await cli.cmd_system_config(args.format)
            elif args.system_cmd == "ping":
                await cli.cmd_system_ping()
            elif args.system_cmd == "services":
                await cli.cmd_system_services(args.format)
            elif args.system_cmd == "reload":
                await cli.cmd_system_reload(args.reload_config_path)
            elif args.system_cmd == "shutdown":
                await cli.cmd_system_shutdown(
                    delay=args.delay,
                    reason=args.reason,
                    confirm=not args.no_confirm
                )
            else:
                parser.parse_args(["system", "--help"])
        
        elif args.command == "userstats":
            if args.userstats_cmd == "all":
                await cli.cmd_userstats_all(
                    format=args.format,
                    top_users=args.top_users,
                    media_history=args.media_history,
                    leaderboards=args.leaderboards
                )
            else:
                parser.parse_args(["userstats", "--help"])
        
        elif args.command in ("moderator", "mod"):
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
                await cli.cmd_moderator_list(
                    filter_action=args.filter,
                    format=args.format,
                )
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
