# Release v2.7.0 - Compatibility Cleanup

## Summary

This minor release removes remaining backward-compatibility paths ahead of v3, fixes file-based playlist commands under `uv run`, and cleans tracked local environment artifacts out of the repository.

## What's Changed

### Removed legacy compatibility behavior

- Removed legacy `cytube` config conversion; config files must now include `channels`
- Removed implicit channel auto-discovery; network commands now require `--channel`
- Removed the deprecated `mod` alias; use `moderator`

### Fixed playlist file handling

- Restored the missing `os` import used by `playlist add <file>` and `playlist addnext <file>`
- Prevents `Error: name 'os' is not defined` when running via `uv run`

### Cleaned repository artifacts

- Removed tracked `venv/`, `venv_clean/`, and `__pycache__/` artifacts from source control
- Extended ignore rules for local environment directories and tool caches

## Version

- `kryten-cli` version: `2.7.0`