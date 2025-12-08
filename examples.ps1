# Kryten CLI Examples (PowerShell)
# Run these commands to test the CLI (requires Kryten bridge running)

Write-Host "=== Chat Examples ===" -ForegroundColor Cyan
kryten say "Hello from the CLI!"
kryten pm BotMaster "Testing PM functionality"

Write-Host ""
Write-Host "=== Playlist Examples ===" -ForegroundColor Cyan
kryten playlist add "https://youtube.com/watch?v=dQw4w9WgXcQ"
kryten playlist addnext "yt:jNQXAC9IVRw"
kryten playlist add --temp "https://youtube.com/watch?v=9bZkp7q19f0"

# Wait a moment for videos to be added
Start-Sleep -Seconds 2

# Playlist management
kryten playlist shuffle
kryten playlist jump 2
kryten playlist settemp 1 true

Write-Host ""
Write-Host "=== Playback Examples ===" -ForegroundColor Cyan
kryten pause
Start-Sleep -Seconds 2
kryten play
Start-Sleep -Seconds 2
kryten seek 30.0

Write-Host ""
Write-Host "=== Moderation Examples ===" -ForegroundColor Cyan
# Note: These will actually kick/ban users if they exist!
# kryten kick TestUser "This is a test kick"
# kryten ban TestUser "This is a test ban"
kryten voteskip

Write-Host ""
Write-Host "All examples completed!" -ForegroundColor Green
