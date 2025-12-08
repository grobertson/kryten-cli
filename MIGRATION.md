# Migration Guide: kryten-cli v1.x to v2.0

This guide helps you migrate from kryten-cli v1.x (direct NATS) to v2.0 (using kryten-py library).

## What Changed

### Architecture
- **v1.x**: Direct NATS client with manual message publishing
- **v2.0**: Uses `kryten-py` library for high-level API access

### Dependencies
- **Removed**: `nats-py>=2.9.0`
- **Added**: `kryten-py>=1.0.0` (which includes nats-py internally)

### Configuration Format

#### New Format (Recommended)
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

#### Legacy Format (Still Supported)
```json
{
  "nats": {
    "servers": ["nats://localhost:4222"]
  },
  "cytube": {
    "channel": "your-channel-name",
    "domain": "cytu.be"
  }
}
```

The CLI automatically converts legacy format internally.

## Breaking Changes

### 1. Removed Features
- **--temp flag**: The `--temp` flag for playlist add commands has been removed as it was not fully implemented in the underlying API.
  - **Before**: `kryten playlist add VIDEO_URL --temp`
  - **After**: `kryten playlist add VIDEO_URL`
  - Use `settemp` command to change temporary status after adding

### 2. Entry Point
- **Before**: `console_scripts = ["kryten=cli.kryten_cli:run"]`
- **After**: `console_scripts = ["kryten=kryten_cli:run"]`
- No namespace package, simpler structure

## Installation

### Uninstall Old Version
```bash
pip uninstall kryten-cli
```

### Install New Version
```bash
cd kryten-cli
pip install -e .
```

This will automatically install `kryten-py` as a dependency.

## New Features

### URL Parsing
The CLI now automatically parses media URLs:
- YouTube: `https://youtube.com/watch?v=VIDEO_ID` or `https://youtu.be/VIDEO_ID`
- Vimeo: `https://vimeo.com/VIDEO_ID`
- Dailymotion: `https://dailymotion.com/video/VIDEO_ID`
- Direct IDs also work: `dQw4w9WgXcQ`

### Better Error Messages
All commands now show clear success/failure messages:
```
✓ Sent chat message to your-channel
✓ Added yt:dQw4w9WgXcQ to end of playlist in your-channel
✓ Kicked spammer from your-channel
```

## Command Compatibility

All commands work exactly the same:

### Chat
```bash
kryten say "Hello"
kryten pm UserName "Hi"
```

### Playlist
```bash
kryten playlist add https://youtube.com/watch?v=xyz
kryten playlist addnext VIDEO_ID
kryten playlist del 5
kryten playlist move 3 after 7
kryten playlist jump 5
kryten playlist clear
kryten playlist shuffle
kryten playlist settemp 5 true
```

### Playback
```bash
kryten pause
kryten play
kryten seek 120.5
```

### Moderation
```bash
kryten kick UserName "Reason"
kryten ban UserName "Reason"
kryten voteskip
```

## Benefits of Migration

1. **Cleaner Code**: Uses high-level API instead of low-level NATS
2. **Type Safety**: Leverages kryten-py's typed interfaces
3. **Better Maintenance**: Shares code with other kryten projects
4. **Automatic Updates**: Benefits from improvements in kryten-py
5. **Consistent Behavior**: Same command format across all kryten tools

## Troubleshooting

### Import Error: `ModuleNotFoundError: No module named 'kryten'`
**Solution**: Install kryten-py library:
```bash
pip install -e ../kryten-py
```

### Connection Failed
**Solution**: Check that kryten-py configuration is correct and NATS server is running:
```bash
# Test NATS connection
nc -zv localhost 4222
```

### Config File Errors
**Solution**: Use `config.example.json` as template:
```bash
cp config.example.json config.json
# Edit config.json with your settings
```

## Getting Help

- Check `kryten --help` for command list
- Check `kryten playlist --help` for subcommands
- See `README.md` for full documentation
- Review `CHANGELOG.md` for detailed changes
