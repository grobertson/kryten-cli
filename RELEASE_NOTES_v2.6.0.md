# Release v2.6.0 - Dropsugar URL Support and Batch Playlist Operations

## What's New

### 🎵 Dropsugar URL Support

The `playlist add` and `playlist addnext` commands now automatically handle dropsugar.co/io URLs:

- Accepts URLs in either **view format** or **manifest format**
- Automatically converts view URLs (e.g., `https://www.dropsugar.co/view?m=Q2PRZmXxm`) to CyTube-compatible manifest URLs
- Works seamlessly with both dropsugar.co and dropsugar.io domains

**Example:**
```bash
kryten playlist add https://www.dropsugar.co/view?m=Q2PRZmXxm
```

### 📝 Batch Playlist Operations

Both `playlist add` and `playlist addnext` can now accept text files containing multiple URLs:

- Create a text file with one URL per line
- `playlist add` adds videos in file order to the end of the playlist
- `playlist addnext` inserts videos in the correct order (automatically reverses for proper playback sequence)
- Visual progress indicator for each video added

**Example:**
```bash
# Create a playlist file
echo "https://youtube.com/watch?v=abc123" > playlist.txt
echo "https://www.dropsugar.co/view?m=Q2PRZmXxm" >> playlist.txt
echo "https://vimeo.com/123456789" >> playlist.txt

# Add all videos
kryten playlist add playlist.txt
# or
kryten playlist addnext playlist.txt
```

### 🔧 Technical Improvements

- **Single Source of Truth**: Version number is now managed only in `pyproject.toml`
- `setup.py` dynamically reads the version to ensure consistency
- No more version mismatches across the project

## Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for complete details.
