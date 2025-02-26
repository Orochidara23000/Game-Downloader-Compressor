#!/bin/bash
set -euo pipefail

echo "Starting install_dependencies.sh script."

# Function to install wget using the appropriate package manager
install_wget() {
    if command -v nix-env &> /dev/null; then
        echo "Installing wget using nix-env..."
        nix-env -iA nixpkgs.wget
    elif command -v apt-get &> /dev/null; then
        echo "Installing wget using apt-get..."
        apt-get update && apt-get install -y wget
    elif command -v yum &> /dev/null; then
        echo "Installing wget using yum..."
        yum install -y wget
    else
        echo "No supported package manager found. Please install wget manually."
        return 1
    fi
}

# Check for wget and install if not present
if ! command -v wget &> /dev/null; then
    echo "wget not found. Installing..."
    install_wget
fi

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

# Create steamcmd directory
STEAMCMD_DIR="/app/steamcmd"
echo "Installing SteamCMD to ${STEAMCMD_DIR}..."
mkdir -p "$STEAMCMD_DIR"
cd "$STEAMCMD_DIR"

# Download and extract SteamCMD
echo "Downloading SteamCMD..."
if ! wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz; then
    # Try using curl if wget fails
    if ! curl -sLO https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz; then
        echo "ERROR: Failed to download SteamCMD using both wget and curl!"
        exit 1
    fi
fi

echo "Extracting SteamCMD..."
if ! tar -xzf steamcmd_linux.tar.gz; then
    echo "ERROR: Failed to extract SteamCMD!"
    exit 1
fi

rm steamcmd_linux.tar.gz

# Make executable
echo "Setting permissions..."
chmod +x steamcmd.sh

# Run SteamCMD to update itself
echo "Running SteamCMD initial update..."
./steamcmd.sh +quit || {
    echo "WARNING: SteamCMD initial update failed, but continuing anyway."
}

# Create symlink
if [ ! -e "/usr/local/bin/steamcmd" ]; then
    ln -sf "${STEAMCMD_DIR}/steamcmd.sh" "/usr/local/bin/steamcmd" || \
        echo "Warning: Failed to create steamcmd symlink, but continuing anyway."
fi

echo "SteamCMD installed successfully."

# Verify steamcmd installation
if [ -x "${STEAMCMD_DIR}/steamcmd.sh" ]; then
    echo "✅ steamcmd is installed and executable"
else
    echo "❌ steamcmd is not properly installed"
fi

# Verify all installations and permissions as a final check
echo "Performing final verification checks..."

# Test write permissions to required directories
for dir in "${APP_DIR}/logs" "${APP_DIR}/output" "${APP_DIR}/game"; do
    if ! touch "${dir}/.write_test" 2>/dev/null; then
        echo "ERROR: Cannot write to directory ${dir}!"
        exit 1
    else
        rm "${dir}/.write_test"
        echo "Write permissions verified for ${dir}"
    fi
done

echo "All dependencies installed and verified successfully."
exit 0
