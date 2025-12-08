# Kryten CLI

Command-line client for sending CyTube commands via the kryten-py library.

## Overview

This CLI provides a simple command-line interface to control CyTube channels through the Kryten bridge. It uses the high-level `kryten-py` library for all communication, making it a clean and maintainable reference implementation.

## Installation

Install the CLI tool:

```bash
pip install -e .
```

This will automatically install the `kryten-py` dependency.

Or run directly:

```bash
python kryten_cli.py --help
```

## Configuration

The CLI reads connection settings from `config.json` in the current directory. Create one with your NATS server and CyTube channel:

```json
{
  "nats": {
    "servers": ["nats://localhost:4222"]
  },
  "channels": [
    {
      "domain": "cytu.be",
      "channel": "your-channel-name"
    }
  ]
}
```

**Legacy Format Support:** The CLI also supports the older config format with `cytube.channel` for backward compatibility.

You can also specify a different config file:

```bash
kryten --config /path/to/config.json say "Hello"
```

## Usage Examples

### Chat Commands

Send a chat message:
```bash
kryten say "Hello world"
```

Send a private message:
```bash
kryten pm UserName "Hi there!"
```

### Playlist Commands

Add video to end of playlist:
```bash
kryten playlist add https://youtube.com/watch?v=xyz
kryten playlist add yt:abc123
```

Add video to play next:
```bash
kryten playlist addnext https://youtube.com/watch?v=abc
```

Add as temporary (auto-deleted after playing):
```bash
kryten playlist add --temp https://youtube.com/watch?v=xyz
```

Delete video from playlist:
```bash
kryten playlist del video-uid-123
```

Move video in playlist:
```bash
kryten playlist move video-uid-5 after video-uid-3
```

Jump to specific video:
```bash
kryten playlist jump video-uid-7
```

Clear entire playlist:
```bash
kryten playlist clear
```

Shuffle playlist:
```bash
kryten playlist shuffle
```

Set video temporary status:
```bash
kryten playlist settemp video-uid-5 true
kryten playlist settemp video-uid-5 false
```

### Playback Commands

Pause current video:
```bash
kryten pause
```

Resume playback:
```bash
kryten play
```

Seek to timestamp (in seconds):
```bash
kryten seek 120.5
```

### Moderation Commands

Kick user:
```bash
kryten kick UserName
kryten kick UserName "Stop spamming"
```

Ban user:
```bash
kryten ban UserName
kryten ban UserName "Banned for harassment"
```

Vote to skip current video:
```bash
kryten voteskip
```

## Command Reference

| Command | Description |
|---------|-------------|
| `say <message>` | Send a chat message |
| `pm <user> <message>` | Send a private message |
| `playlist add <url>` | Add video to end of playlist |
| `playlist addnext <url>` | Add video to play next |
| `playlist del <uid>` | Delete video from playlist |
| `playlist move <uid> after <uid>` | Move video in playlist |
| `playlist jump <uid>` | Jump to specific video |
| `playlist clear` | Clear entire playlist |
| `playlist shuffle` | Shuffle playlist |
| `playlist settemp <uid> <true\|false>` | Set temporary status |
| `pause` | Pause playback |
| `play` | Resume playback |
| `seek <seconds>` | Seek to timestamp |
| `kick <user> [reason]` | Kick user from channel |
| `ban <user> [reason]` | Ban user from channel |
| `voteskip` | Vote to skip current video |

## Options

| Option | Description |
|--------|-------------|
| `--config <path>` | Path to config file (default: config.json) |
| `--channel <name>` | Override channel from config |
| `--help` | Show help message |

## NATS Message Format

All commands are published to NATS subjects following this pattern:

```
cytube.commands.{channel}.{action}
```

Message payload:
```json
{
  "action": "chat",
  "data": {
    "message": "Hello world"
  }
}
```

This format is compatible with the Kryten bidirectional bridge's `CommandSubscriber`.

## Requirements

- Python 3.11+
- nats-py >= 2.9.0
- Kryten bidirectional bridge running with `commands.enabled = true`

## Examples

### Automated DJ

Add a list of videos:
```bash
for url in $(cat playlist.txt); do
  kryten playlist add "$url"
  sleep 1
done
```

### Bot Integration

Use in scripts to respond to events:
```bash
#!/bin/bash
# Greet new users
kryten say "Welcome to the channel!"
```

### Remote Moderation

Quick moderation commands:
```bash
kryten kick TrollUser "Please follow the rules"
kryten ban SpamBot "Automated spam detected"
```

## Troubleshooting

### Connection refused

Make sure NATS server is running:
```bash
# Start NATS server
nats-server
```

### Command not found

Make sure the CLI is installed:
```bash
pip install -e .
```

Or use the module directly:
```bash
python kryten_cli.py say "Hello"
```

### Commands not executing

1. Check that Kryten bridge is running
2. Verify `commands.enabled = true` in Kryten's config
3. Check NATS connection settings match between CLI and Kryten
4. Verify channel name is correct

## Version 2.0 - Using kryten-py Library

**Version 2.0** is a complete rewrite that uses the `kryten-py` library instead of direct NATS calls. This provides:

- **Cleaner code**: High-level API instead of low-level NATS
- **Type safety**: Typed interfaces and better IDE support
- **Better maintenance**: Shares code with other kryten projects
- **New features**: Automatic URL parsing for media commands

For migration information from v1.x, see [MIGRATION.md](MIGRATION.md).

For complete details about the refactor, see [REFACTOR_SUMMARY.md](REFACTOR_SUMMARY.md).

## Contributing

This project serves as a reference implementation for using kryten-py. Contributions are welcome!

## License

See LICENSE file for details.
