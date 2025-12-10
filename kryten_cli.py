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
import re
import sys
from pathlib import Path
from typing import Optional

from kryten import KrytenClient


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
    
    async def cmd_playlist_add(self, url: str) -> None:
        """Add video to end of playlist.
        
        Args:
            url: Video URL or ID.
        """
        media_type, media_id = self._parse_media_url(url)
        await self.client.add_media(
            self.channel, media_type, media_id, position="end", domain=self.domain
        )
        print(f"✓ Added {media_type}:{media_id} to end of playlist in {self.channel}")
    
    async def cmd_playlist_addnext(self, url: str) -> None:
        """Add video to play next.
        
        Args:
            url: Video URL or ID.
        """
        media_type, media_id = self._parse_media_url(url)
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
        bucket_name = f"cytube_{self.channel.lower()}_playlist"
        
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
    
    async def cmd_system_stats(self, format: str = "text") -> None:
        """Display Kryten-Robot runtime statistics."""
        try:
            stats = await self.client.get_stats()
            
            if format == "json":
                print(json.dumps(stats, indent=2))
                return
            
            # Text format
            uptime_hours = stats.get("uptime", 0) / 3600
            events = stats.get("events", {})
            commands = stats.get("commands", {})
            connections = stats.get("connections", {})
            state = stats.get("state", {})
            memory = stats.get("memory", {})
            
            print("\nKryten-Robot Runtime Statistics")
            print("=" * 80)
            print(f"\nUptime: {uptime_hours:.2f} hours")
            
            print(f"\nEvents:")
            print(f"  Total Published:   {events.get('total_published', 0):,}")
            print(f"  Rate (1 min):      {events.get('rate_1min', 0):.2f} events/sec")
            print(f"  Rate (5 min):      {events.get('rate_5min', 0):.2f} events/sec")
            print(f"  Last Event:        {events.get('last_event_type', 'N/A')}")
            print(f"  Last Event Time:   {events.get('last_event_time', 'N/A')}")
            
            print(f"\nCommands:")
            print(f"  Total Received:    {commands.get('total_received', 0):,}")
            print(f"  Succeeded:         {commands.get('succeeded', 0):,}")
            print(f"  Failed:            {commands.get('failed', 0):,}")
            print(f"  Rate (1 min):      {commands.get('rate_1min', 0):.2f} commands/sec")
            print(f"  Rate (5 min):      {commands.get('rate_5min', 0):.2f} commands/sec")
            
            cytube = connections.get("cytube", {})
            nats = connections.get("nats", {})
            
            print(f"\nConnections:")
            print(f"  CyTube:")
            print(f"    Connected:       {cytube.get('connected', False)}")
            print(f"    Connected Since: {cytube.get('connected_since', 'N/A')}")
            print(f"    Reconnect Count: {cytube.get('reconnect_count', 0)}")
            print(f"    Last Event:      {cytube.get('last_event_time', 'N/A')}")
            print(f"  NATS:")
            print(f"    Connected:       {nats.get('connected', False)}")
            print(f"    Connected Since: {nats.get('connected_since', 'N/A')}")
            print(f"    Reconnect Count: {nats.get('reconnect_count', 0)}")
            print(f"    Server:          {nats.get('connected_url', 'N/A')}")
            
            print(f"\nChannel State:")
            print(f"  Users:             {state.get('users', 0)}")
            print(f"  Playlist Items:    {state.get('playlist', 0)}")
            print(f"  Emotes:            {state.get('emotes', 0)}")
            
            if memory:
                print(f"\nMemory Usage:")
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
            print("\nKryten-Robot Configuration")
            print("=" * 80)
            
            cytube = config.get("cytube", {})
            nats = config.get("nats", {})
            commands_cfg = config.get("commands", {})
            health = config.get("health", {})
            
            print(f"\nCyTube:")
            print(f"  Domain:            {cytube.get('domain', 'N/A')}")
            print(f"  Channel:           {cytube.get('channel', 'N/A')}")
            print(f"  Username:          {cytube.get('username', 'N/A')}")
            print(f"  Password:          {cytube.get('password', 'N/A')}")
            
            print(f"\nNATS:")
            servers = nats.get("servers", [])
            if isinstance(servers, list):
                for i, server in enumerate(servers):
                    print(f"  Server {i+1}:          {server}")
            print(f"  User:              {nats.get('user', 'N/A')}")
            print(f"  Password:          {nats.get('password', 'N/A')}")
            
            print(f"\nCommands:")
            print(f"  Enabled:           {commands_cfg.get('enabled', False)}")
            
            print(f"\nHealth:")
            print(f"  Enabled:           {health.get('enabled', False)}")
            print(f"  Host:              {health.get('host', 'N/A')}")
            print(f"  Port:              {health.get('port', 'N/A')}")
            
            print(f"\nLog Level:           {config.get('log_level', 'N/A')}")
            
        except Exception as e:
            print(f"Error retrieving config: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_system_ping(self) -> None:
        """Check if Kryten-Robot is alive."""
        try:
            result = await self.client.ping()
            status = result.get("status", "unknown")
            timestamp = result.get("timestamp", "N/A")
            
            print(f"✅ Kryten-Robot is {status}")
            print(f"   Timestamp: {timestamp}")
            
        except TimeoutError:
            print("❌ Kryten-Robot is not responding", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error pinging robot: {e}", file=sys.stderr)
            sys.exit(1)
    
    async def cmd_system_reload(self, config_path: Optional[str] = None) -> None:
        """Reload Kryten-Robot configuration."""
        try:
            result = await self.client.reload_config(config_path)
            
            success = result.get("success", False)
            message = result.get("message", "")
            changes = result.get("changes_applied", [])
            unsafe = result.get("unsafe_changes", [])
            errors = result.get("errors", [])
            
            if success:
                print(f"✅ {message}")
            else:
                print(f"⚠️  {message}")
            
            if changes:
                print(f"\nChanges applied:")
                for change in changes:
                    print(f"  • {change}")
            else:
                print("\nNo changes detected.")
            
            if unsafe:
                print(f"\n⚠️  Unsafe changes detected (restart required):")
                for change in unsafe:
                    print(f"  • {change}")
            
            if errors:
                print(f"\n❌ Errors:")
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
                    prompt = f"Shutdown Kryten-Robot in {delay} seconds? [y/N]: "
                else:
                    prompt = "Shutdown Kryten-Robot immediately? [y/N]: "
                
                response = input(prompt).strip().lower()
                if response not in ["y", "yes"]:
                    print("Shutdown cancelled.")
                    return
            
            result = await self.client.shutdown(delay, reason)
            
            success = result.get("success", False)
            message = result.get("message", "")
            delay_actual = result.get("delay_seconds", 0)
            shutdown_time = result.get("shutdown_time", "N/A")
            
            if success:
                print(f"✅ {message}")
                if delay_actual > 0:
                    print(f"   Shutdown scheduled: {shutdown_time}")
                    print(f"   Delay: {delay_actual} seconds")
                print(f"   Reason: {reason}")
            else:
                print(f"❌ Shutdown failed: {message}", file=sys.stderr)
                sys.exit(1)
                
        except Exception as e:
            print(f"Error shutting down robot: {e}", file=sys.stderr)
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
        help="Path to configuration file (overrides other options if present)"
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
    
    return parser


async def main() -> None:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Auto-discover channel if not specified
    channel = args.channel
    
    if not channel:
        # Connect temporarily to discover channels
        temp_cli = KrytenCLI(
            channel="",  # Dummy channel for discovery
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
