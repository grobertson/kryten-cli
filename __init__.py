"""Kryten CLI - Command-line client for sending CyTube commands via NATS."""

from pathlib import Path
import re


def _read_version_from_pyproject() -> str:
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise RuntimeError("Unable to find version in pyproject.toml")
    return match.group(1)


__version__ = _read_version_from_pyproject()
