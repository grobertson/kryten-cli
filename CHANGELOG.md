# Changelog

All notable changes to kryten-cli will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
