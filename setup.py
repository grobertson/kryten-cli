"""Setup script for Kryten CLI."""

from setuptools import setup, find_packages

setup(
    name="kryten-cli",
    version="2.0.0",
    description="Command-line client for CyTube via kryten-py library",
    author="Kryten Robot Team",
    packages=find_packages(),
    install_requires=[
        "kryten-py>=0.4.0",
    ],
    entry_points={
        "console_scripts": [
            "kryten=kryten_cli:run",
        ],
    },
    python_requires=">=3.11",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
