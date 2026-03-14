# Release v2.6.2 - Restored Batch Pacing and Metadata Alignment

## Summary

This patch restores behavior and packaging metadata that were missing after conflict-resolution during the 2.6.1 cherry-pick.

## What's Changed

### Playlist batch pacing restored

For file-based playlist operations:

- `playlist add <file>`
- `playlist addnext <file>`

A 1-second delay between each add is now restored to reduce command bursts.

### Packaging metadata restored

`pyproject.toml` now restores the richer 2.6.x layout:

- Hatchling build backend
- `kryten-py>=0.9.8`
- Ruff and Mypy tool configuration
- Dev dependency group metadata

## Version

- `kryten-cli` version: `2.6.2`
