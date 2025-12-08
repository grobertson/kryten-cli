#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start kryten-cli with automatic environment management
.DESCRIPTION
    This script ensures a working Python virtual environment exists and is properly
    configured before running kryten-cli. It will create or repair the environment
    if needed, providing clear error messages when issues occur.
.PARAMETER Command
    The kryten-cli command and arguments to execute
.EXAMPLE
    .\start-kryten-cli.ps1 say "Hello world"
.EXAMPLE
    .\start-kryten-cli.ps1 pm UserName "Private message"
#>

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Command
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Configuration
$VenvPath = Join-Path $ScriptDir "venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$VenvPip = Join-Path $VenvPath "Scripts\pip.exe"
$RequirementsFile = Join-Path $ScriptDir "requirements.txt"
$AppScript = Join-Path $ScriptDir "kryten_cli.py"

# Color output functions
function Write-Success { param($Message) Write-Host "✓ $Message" -ForegroundColor Green }
function Write-Info { param($Message) Write-Host "ℹ $Message" -ForegroundColor Cyan }
function Write-Warning { param($Message) Write-Host "⚠ $Message" -ForegroundColor Yellow }
function Write-ErrorMsg { param($Message) Write-Host "✗ $Message" -ForegroundColor Red }

# Check if Python is available
function Test-PythonAvailable {
    try {
        $pythonCmd = Get-Command python -ErrorAction Stop
        $version = & python --version 2>&1
        if ($version -match "Python 3\.(1[1-9]|[2-9]\d)") {
            Write-Success "Found $version at $($pythonCmd.Source)"
            return $true
        } else {
            Write-ErrorMsg "Python 3.11+ required, found: $version"
            return $false
        }
    } catch {
        Write-ErrorMsg "Python not found in PATH"
        Write-Info "Install Python 3.11+ from https://www.python.org/"
        return $false
    }
}

# Check if venv is valid
function Test-VenvValid {
    param($Path)
    
    if (-not (Test-Path $Path)) {
        return $false
    }
    
    $pythonExe = Join-Path $Path "Scripts\python.exe"
    $pipExe = Join-Path $Path "Scripts\pip.exe"
    
    if (-not (Test-Path $pythonExe) -or -not (Test-Path $pipExe)) {
        Write-Warning "Virtual environment incomplete or corrupted"
        return $false
    }
    
    # Test if python actually works
    try {
        $null = & $pythonExe -c "import sys" 2>&1
        return $true
    } catch {
        Write-Warning "Virtual environment Python is not functional"
        return $false
    }
}

# Create virtual environment
function New-VirtualEnvironment {
    param($Path)
    
    Write-Info "Creating virtual environment at $Path"
    
    try {
        & python -m venv $Path
        
        if (-not (Test-VenvValid $Path)) {
            throw "Failed to create valid virtual environment"
        }
        
        Write-Success "Virtual environment created successfully"
        return $true
    } catch {
        Write-ErrorMsg "Failed to create virtual environment: $_"
        return $false
    }
}

# Install or update requirements
function Install-Requirements {
    param($PipExe, $RequirementsPath)
    
    if (-not (Test-Path $RequirementsPath)) {
        Write-ErrorMsg "Requirements file not found: $RequirementsPath"
        return $false
    }
    
    Write-Info "Installing/updating dependencies from requirements.txt"
    
    try {
        & $PipExe install --upgrade pip --quiet
        & $PipExe install -r $RequirementsPath --upgrade
        
        if ($LASTEXITCODE -ne 0) {
            throw "pip install failed with exit code $LASTEXITCODE"
        }
        
        Write-Success "Dependencies installed successfully"
        return $true
    } catch {
        Write-ErrorMsg "Failed to install dependencies: $_"
        Write-Info "Try manually: $PipExe install -r $RequirementsPath"
        return $false
    }
}

# Verify kryten-py is installed with correct version
function Test-KrytenPyInstalled {
    param($PythonExe)
    
    try {
        $version = & $PythonExe -c "import kryten; print(kryten.__version__)" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "kryten-py version $version is installed"
            return $true
        }
    } catch {}
    
    Write-Warning "kryten-py not found or not importable"
    return $false
}

# Main execution
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Kryten CLI Startup" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Python
if (-not (Test-PythonAvailable)) {
    exit 1
}

# Step 2: Check/Create venv
if (-not (Test-VenvValid $VenvPath)) {
    Write-Warning "Virtual environment needs to be created or repaired"
    
    # Remove corrupted venv if it exists
    if (Test-Path $VenvPath) {
        Write-Info "Removing corrupted virtual environment"
        try {
            Remove-Item -Recurse -Force $VenvPath -ErrorAction Stop
        } catch {
            Write-ErrorMsg "Could not remove corrupted venv (may be in use)"
            Write-Info "Please close all terminals/processes using: $VenvPath"
            Write-Info "Then delete manually or restart your computer"
            exit 1
        }
    }
    
    if (-not (New-VirtualEnvironment $VenvPath)) {
        exit 1
    }
}

# Step 3: Install/verify dependencies
if (-not (Test-KrytenPyInstalled $VenvPython)) {
    Write-Info "Installing dependencies for first run"
    if (-not (Install-Requirements $VenvPip $RequirementsFile)) {
        exit 1
    }
}

# Step 4: Verify application script exists
if (-not (Test-Path $AppScript)) {
    Write-ErrorMsg "Application script not found: $AppScript"
    exit 1
}

# Step 5: Run the application
Write-Host ""
Write-Host "Starting kryten-cli..." -ForegroundColor Green
Write-Host ""

try {
    if ($Command.Count -eq 0) {
        # No command provided, show help
        & $VenvPython $AppScript --help
    } else {
        # Execute the command
        & $VenvPython $AppScript @Command
    }
    
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Host ""
        Write-Success "Command completed successfully"
    } else {
        Write-Host ""
        Write-ErrorMsg "Command failed with exit code: $exitCode"
    }
    
    exit $exitCode
} catch {
    Write-Host ""
    Write-ErrorMsg "Failed to execute kryten-cli: $_"
    exit 1
}
