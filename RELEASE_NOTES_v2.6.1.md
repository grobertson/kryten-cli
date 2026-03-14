# Release v2.6.1 - Playlist Comment Line Support

## Summary

This patch release improves playlist file handling by supporting comment lines.

## What's Changed

### Playlist file parsing

When using `playlist add <file>` or `playlist addnext <file>`:

- Blank lines are ignored
- Lines starting with `#` are treated as comments and ignored
- Leading whitespace before `#` is allowed (still treated as comment)

This makes it easier to maintain annotated playlist files in `./playlists`.

## Example

Playlist file:

```text
# Friday mix
https://youtube.com/watch?v=abc123def45

  # Optional note
yt:xyz987uvw65
```

Command:

```bash
kryten --channel lounge playlist add .\\playlists\\friday20.txt
```

Only valid media lines are sent to CyTube.

## Version

- `kryten-cli` version: `2.6.1`
