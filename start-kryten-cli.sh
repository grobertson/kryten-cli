#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
VENV_PATH="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_PATH/bin/python"
VENV_PIP="$VENV_PATH/bin/pip"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

# Color output functions
print_success() { echo -e "\033[32m✓ $1\033[0m"; }
print_info() { echo -e "\033[36mℹ $1\033[0m"; }
print_warning() { echo -e "\033[33m⚠ $1\033[0m"; }
print_error() { echo -e "\033[31m✗ $1\033[0m"; }

# Check if Python is available
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found in PATH"
        print_info "Install Python 3.11+ from your package manager"
        return 1
    fi
    
    local version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
    local major=$(echo "$version" | cut -d. -f1)
    local minor=$(echo "$version" | cut -d. -f2)
    
    if [[ $major -eq 3 && $minor -ge 11 ]] || [[ $major -gt 3 ]]; then
        print_success "Found Python $version"
        return 0
    else
        print_error "Python 3.11+ required, found: $version"
        return 1
    fi
}

# Check if venv is valid
check_venv() {
    local path=$1
    
    if [[ ! -d "$path" ]]; then
        return 1
    fi
    
    if [[ ! -f "$path/bin/python" ]] || [[ ! -f "$path/bin/pip" ]]; then
        print_warning "Virtual environment incomplete or corrupted"
        return 1
    fi
    
    # Test if python actually works
    if ! "$path/bin/python" -c "import sys" &> /dev/null; then
        print_warning "Virtual environment Python is not functional"
        return 1
    fi
    
    return 0
}

# Create virtual environment
create_venv() {
    local path=$1
    
    print_info "Creating virtual environment at $path"
    
    if ! python3 -m venv "$path"; then
        print_error "Failed to create virtual environment"
        return 1
    fi
    
    if ! check_venv "$path"; then
        print_error "Created venv is not valid"
        return 1
    fi
    
    print_success "Virtual environment created successfully"
    return 0
}

# Install or update requirements
install_requirements() {
    local pip_exe=$1
    local requirements_path=$2
    
    if [[ ! -f "$requirements_path" ]]; then
        print_error "Requirements file not found: $requirements_path"
        return 1
    fi
    
    print_info "Installing/updating dependencies from requirements.txt"
    
    if ! "$pip_exe" install --upgrade pip --quiet; then
        print_error "Failed to upgrade pip"
        return 1
    fi
    
    if ! "$pip_exe" install -r "$requirements_path" --upgrade; then
        print_error "Failed to install dependencies"
        print_info "Try manually: $pip_exe install -r $requirements_path"
        return 1
    fi
    
    print_success "Dependencies installed successfully"
    return 0
}

# Verify kryten-py is installed
check_kryten_py() {
    local python_exe=$1
    
    if "$python_exe" -c "import kryten" &> /dev/null; then
        print_success "kryten-py package is installed"
        return 0
    else
        print_warning "kryten-py package not found"
        return 1
    fi
}

# Main execution
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Kryten CLI (Command Tool) Startup"
echo "═══════════════════════════════════════════════════════"
echo ""

# Step 1: Check Python
if ! check_python; then
    exit 1
fi

# Step 2: Check/Create venv
if ! check_venv "$VENV_PATH"; then
    print_warning "Virtual environment needs to be created or repaired"
    
    # Remove corrupted venv if it exists
    if [[ -d "$VENV_PATH" ]]; then
        print_info "Removing corrupted virtual environment"
        if ! rm -rf "$VENV_PATH"; then
            print_error "Could not remove corrupted venv"
            print_info "Delete manually: rm -rf $VENV_PATH"
            exit 1
        fi
    fi
    
    if ! create_venv "$VENV_PATH"; then
        exit 1
    fi
fi

# Step 3: Install/verify dependencies
if ! check_kryten_py "$VENV_PYTHON"; then
    print_info "Installing dependencies"
    if ! install_requirements "$VENV_PIP" "$REQUIREMENTS_FILE"; then
        exit 1
    fi
    
    # Verify again after installation
    if ! check_kryten_py "$VENV_PYTHON"; then
        print_error "kryten-py still missing after installation"
        exit 1
    fi
fi

# Step 4: Run kryten-cli with all arguments
echo ""
print_success "Environment ready"
echo ""

exec "$VENV_PYTHON" "$SCRIPT_DIR/kryten_cli.py" "$@"
