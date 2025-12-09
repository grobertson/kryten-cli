# Changelog

All notable changes to kryten-cli will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0] - 2025-12-09

### Added

- **Automatic Channel Discovery**: `--channel` is now optional
  - CLI automatically queries running Kryten-Robot instances for available channels
  - If only one channel is found, it's used automatically without specifying `--channel`
  - If multiple channels exist, displays list and prompts user to specify one
  - Falls back gracefully with helpful error messages if discovery fails
- Enhanced user experience with informative messages during auto-discovery

### Changed

- Updated dependency to kryten-py>=0.5.8 (adds `get_channels()` method)
- `--channel` argument is now optional instead of required
- Improved help text and documentation to explain auto-discovery feature

## [2.2.0] - 2025-12-09

### Changed

- **BREAKING**: Configuration file is now optional - all settings can be provided via command-line
- **BREAKING**: `--channel` is now a required command-line argument
- Improved command-line interface with better defaults:
  - `--domain` defaults to `cytu.be` (optional)
  - `--nats` defaults to `nats://localhost:4222` (optional, can be specified multiple times)
  - `--config` is now optional and overrides command-line options when present
- Enhanced usage examples in help text and documentation

### Added

- Command-line options: `--channel` (required), `--domain`, `--nats` (repeatable)
- More flexible deployment: works without config file for quick commands
- Better default values for common use cases

## [2.1.1] - 2025-12-09

### Changed

- Version bump to trigger PyPI release after project name reservation
- All changes from v2.1.0 included

## [2.1.0] - 2025-12-09

### Changed

- **Compatibility**: Lowered minimum Python version requirement from 3.11 to 3.10
  - Updated dependency to kryten-py>=0.5.7 which supports Python 3.10
  - Added Python 3.10 classifier
  - Enhanced PyPI packaging with proper metadata and README

### Added

- **PyPI Publishing**: Added GitHub Actions workflow for automated PyPI releases
- Enhanced setup.py with comprehensive metadata for PyPI
- MANIFEST.in for proper file inclusion in distribution
- MIT License file

## [2.0.0] - 2025-12-08

### Changed
- **BREAKING**: Complete rewrite to use `kryten-py` library instead of direct NATS calls
- Replaced all direct NATS publish operations with high-level KrytenClient methods
- Updated configuration format to support `channels` array (maintains backward compatibility with legacy `cytube.channel` format)
- Improved error handling and user feedback messages
- Added URL parsing for media commands (YouTube, Vimeo, Dailymotion)
- Updated dependency from `nats-py` to `kryten-py>=1.0.0`

### Added
- Media URL parsing for automatic type detection (YouTube, Vimeo, Dailymotion)
- Support for new kryten-py configuration format
- Better success messages showing channel and action details
- `config.example.json` template file

### Improved
- Code is now cleaner and more maintainable
- Type safety through kryten-py's typed API
- Better separation of concerns
- Consistent error handling

### Removed
- Direct NATS client usage
- Manual subject construction
- Manual message encoding/decoding

## [1.0.0] - 2024

### Added
- Initial release with direct NATS implementation
- Chat commands (say, pm)
- Playlist commands (add, addnext, del, move, jump, clear, shuffle, settemp)
- Playback commands (pause, play, seek)
- Moderation commands (kick, ban, voteskip)
