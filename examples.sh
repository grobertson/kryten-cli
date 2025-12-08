#!/bin/bash
# Kryten CLI Examples
# Run these commands to test the CLI (requires Kryten bridge running)

echo "=== Chat Examples ==="
kryten say "Hello from the CLI!"
kryten pm BotMaster "Testing PM functionality"

echo ""
echo "=== Playlist Examples ==="
kryten playlist add "https://youtube.com/watch?v=dQw4w9WgXcQ"
kryten playlist addnext "yt:jNQXAC9IVRw"
kryten playlist add --temp "https://youtube.com/watch?v=9bZkp7q19f0"

# Wait a moment for videos to be added
sleep 2

# Playlist management
kryten playlist shuffle
kryten playlist jump 2
kryten playlist settemp 1 true

echo ""
echo "=== Playback Examples ==="
kryten pause
sleep 2
kryten play
sleep 2
kryten seek 30.0

echo ""
echo "=== Moderation Examples ==="
# Note: These will actually kick/ban users if they exist!
# kryten kick TestUser "This is a test kick"
# kryten ban TestUser "This is a test ban"
kryten voteskip

echo ""
echo "All examples completed!"
