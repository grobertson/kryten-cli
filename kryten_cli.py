#!/usr/bin/env python3
"""Kryten CLI - Send CyTube commands via NATS.

This command-line tool sends commands to a CyTube channel through NATS messaging.
It provides a simple interface to all outbound commands supported by the Kryten
bidirectional bridge.

Examples:
    Send a chat message:
        $ kryten say "Hello world"
    
    Send a private message:
        $ kryten pm UserName "Hi there!"
    
    Add video to playlist:
        $ kryten playlist add https://youtube.com/watch?v=xyz
        $ kryten playlist addnext https://youtube.com/watch?v=abc
    
    Delete from playlist:
        $ kryten playlist del 5
    
    Playlist management:
        $ kryten playlist move 3 after 7
        $ kryten playlist jump 5
        $ kryten playlist clear
        $ kryten playlist shuffle
        $ kryten playlist settemp 5 true
    
    Playback control:
        $ kryten pause
        $ kryten play
        $ kryten seek 120.5
    
    Moderation:
        $ kryten kick UserName "Stop spamming"
        $ kryten ban UserName "Banned for harassment"
        $ kryten voteskip

Configuration:
    The CLI reads NATS connection settings from config.json in the current
    directory or from a path specified with --config.
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
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize CLI with configuration.
        
        Args:
            config_path: Path to configuration file.
        """
        self.config_path = Path(config_path)
        self.config_dict = self._load_config()
        self.client: Optional[KrytenClient] = None
        
        # Extract channel and domain from config
        channels = self.config_dict.get("channels", [])
        if not channels:
            # Legacy config format support
            cytube = self.config_dict.get("cytube", {})
            self.channel = cytube.get("channel", "")
            self.domain = cytube.get("domain", "cytu.be")
        else:
            self.channel = channels[0]["channel"]
            self.domain = channels[0].get("domain", "cytu.be")
    
    def _load_config(self) -> dict:
        """Load configuration from JSON file.
        
        Returns:
            Configuration dictionary.
        
        Raises:
            SystemExit: If config file not found or invalid.
        """
        if not self.config_path.exists():
            print(f"Error: Configuration file not found: {self.config_path}", file=sys.stderr)
            print("Create a config.json file with NATS and CyTube settings.", file=sys.stderr)
            sys.exit(1)
        
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
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
            uid: Video UID or position number.
        """
        uid_int = int(uid)
        await self.client.delete_media(self.channel, uid_int, domain=self.domain)
        print(f"✓ Deleted media {uid} from {self.channel}")
    
    async def cmd_playlist_move(self, uid: str, after: str) -> None:
        """Move video in playlist.
        
        Args:
            uid: Video UID to move.
            after: UID to place after.
        """
        uid_int = int(uid)
        after_int = int(after)
        await self.client.move_media(self.channel, uid_int, after_int, domain=self.domain)
        print(f"✓ Moved media {uid} after {after} in {self.channel}")
    
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
    
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to configuration file (default: config.json)"
    )
    
    parser.add_argument(
        "--channel",
        help="Override channel from config"
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
    
    return parser


async def main() -> None:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize CLI
    cli = KrytenCLI(args.config)
    
    # Override channel if specified
    if args.channel:
        cli.channel = args.channel
    
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
