#!/bin/bash
set -euo pipefail

echo "Starting install_dependencies.sh script."

# Check if running in Railway environment
if [ -n "${RAILWAY_ENVIRONMENT:-}" ]; then
    echo "Running in Railway environment"
    # Railway specific setup if needed
    APP_DIR="${APP_DIR:-/app}"
else
    echo "Running in development environment"
    APP_DIR="${APP_DIR:-.}"
fi

# Create required directories with proper permissions
mkdir -p "${APP_DIR}/logs" "${APP_DIR}/output" "${APP_DIR}/game" 
chmod 755 "${APP_DIR}/logs" "${APP_DIR}/output" "${APP_DIR}/game"
echo "Created required directories with proper permissions."

# Check if 7z is installed
if command -v 7z &> /dev/null; then
    echo "7zip is already installed."
else
    echo "Installing 7zip..."
    apt-get update && apt-get install -y p7zip-full
    echo "7zip installed successfully."
fi

# Check for steamcmd directory
STEAMCMD_DIR="${APP_DIR}/steamcmd"
if [ -d "$STEAMCMD_DIR" ] && [ -f "${STEAMCMD_DIR}/steamcmd.sh" ]; then
    echo "SteamCMD is already installed."
else
    echo "Installing SteamCMD..."
    mkdir -p "$STEAMCMD_DIR"
    cd "$STEAMCMD_DIR"
    
    # Download and extract SteamCMD
    wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz
    tar -xzf steamcmd_linux.tar.gz
    rm steamcmd_linux.tar.gz
    
    # Make executable
    chmod +x steamcmd.sh
    
    # Run SteamCMD to update itself
    ./steamcmd.sh +quit || true
    
    echo "SteamCMD installed successfully."
    cd "$APP_DIR"
fi

echo "All dependencies installed successfully."
