"""Setup script for Kryten CLI."""

from setuptools import setup, find_packages
from pathlib import Path
import sys

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read version from pyproject.toml (single source of truth)
# Use tomllib for Python 3.11+, tomli for Python 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        # Fallback: parse version manually if tomli not available during setup
        import re
        pyproject_text = (this_directory / "pyproject.toml").read_text(encoding="utf-8")
        version_match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', pyproject_text, re.MULTILINE)
        version = version_match.group(1) if version_match else "0.0.0"
        tomllib = None

if tomllib:
    with open(this_directory / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
        version = pyproject["project"]["version"]

setup(
    name="kryten-cli",
    version=version,
    description="Command-line client for CyTube via kryten-py library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Kryten Robot Team",
    author_email="kryten@example.com",
    url="https://github.com/grobertson/kryten-cli",
    project_urls={
        "Bug Tracker": "https://github.com/grobertson/kryten-cli/issues",
        "Source Code": "https://github.com/grobertson/kryten-cli",
        "Documentation": "https://github.com/grobertson/kryten-cli/blob/main/README.md",
    },
    license="MIT",
    packages=find_packages(),
    py_modules=["kryten_cli"],
    install_requires=[
        "kryten-py>=0.5.8",
    ],
    entry_points={
        "console_scripts": [
            "kryten=kryten_cli:run",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Chat",
        "Topic :: Utilities",
    ],
    keywords="cytube nats cli command-line microservices bot",
)
