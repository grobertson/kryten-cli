# Release v2.6.3 - Command Sections Restored and Version Consistency

## Summary

This patch restores missing CLI command sections and enforces a single source of truth for project versioning.

## What's Changed

### Restored command sections

- Restored `userstats` command group and routing
- Restored `moderator` (`mod`) command group and routing
- Re-added associated command handlers in `kryten_cli.py`

### Version single source of truth

- `pyproject.toml` is now the canonical version source (`2.6.3`)
- `setup.py` now reads version from `pyproject.toml`
- `__init__.py` now reads `__version__` from `pyproject.toml`

## Version

- `kryten-cli` version: `2.6.3`
