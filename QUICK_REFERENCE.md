# Kryten CLI Quick Reference

## Installation

```bash
# Install as command-line tool
pip install -e cli/

# Or run directly
python -m cli.kryten_cli --help
```

## Quick Examples

```bash
# Chat
kryten say "Hello world"
kryten pm UserName "Private message"

# Playlist
kryten playlist add https://youtube.com/watch?v=xyz
kryten playlist addnext yt:abc123
kryten playlist del video-uid-5
kryten playlist clear

# Playback
kryten pause
kryten play
kryten seek 120.5

# Moderation
kryten kick UserName "Reason here"
kryten ban UserName "Reason here"
kryten voteskip
```

## All Commands

### Chat
- `say <message>` - Send chat message
- `pm <user> <message>` - Send private message

### Playlist
- `playlist add <url>` - Add to end
- `playlist addnext <url>` - Add next
- `playlist add --temp <url>` - Add temporary
- `playlist del <uid>` - Delete video
- `playlist move <uid> after <uid>` - Move video
- `playlist jump <uid>` - Jump to video
- `playlist clear` - Clear all
- `playlist shuffle` - Shuffle
- `playlist settemp <uid> true|false` - Set temp status

### Playback
- `pause` - Pause playback
- `play` - Resume playback
- `seek <seconds>` - Seek to time

### Moderation
- `kick <user> [reason]` - Kick user
- `ban <user> [reason]` - Ban user
- `voteskip` - Vote skip

## Configuration

Create `config.json`:

```json
{
  "cytube": {
    "channel": "your-channel"
  },
  "nats": {
    "servers": ["nats://localhost:4222"]
  }
}
```

## Options

- `--config <path>` - Use different config file
- `--channel <name>` - Override channel
- `--help` - Show help

## How It Works

1. CLI reads config.json for NATS connection
2. Connects to NATS server
3. Publishes command to `cytube.commands.{channel}.{action}`
4. Kryten bridge receives and executes on CyTube

## Message Format

```json
{
  "action": "chat",
  "data": {"message": "Hello"}
}
```

Published to: `cytube.commands.mychannel.chat`

## Troubleshooting

**"Config not found"** - Create config.json in current directory

**"Connection refused"** - Check NATS server is running

**"Command not executing"** - Ensure Kryten bridge is running with `commands.enabled = true`
