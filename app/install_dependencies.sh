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
    echo "7zip is already installed at $(which 7z)."
else
    echo "Installing 7zip..."
    apt-get update && apt-get install -y p7zip-full
    
    # Verify installation
    if command -v 7z &> /dev/null; then
        echo "7zip installed successfully at $(which 7z)."
    else
        echo "ERROR: 7zip installation failed!"
        exit 1
    fi
fi

# Check for steamcmd directory
STEAMCMD_DIR="${APP_DIR}/steamcmd"
if [ -d "$STEAMCMD_DIR" ] && [ -f "${STEAMCMD_DIR}/steamcmd.sh" ]; then
    echo "SteamCMD is already installed at ${STEAMCMD_DIR}/steamcmd.sh."
    
    # Verify executable permissions
    if [ -x "${STEAMCMD_DIR}/steamcmd.sh" ]; then
        echo "SteamCMD has correct permissions."
    else
        echo "Setting executable permissions for SteamCMD..."
        chmod +x "${STEAMCMD_DIR}/steamcmd.sh"
    fi
else
    echo "Installing SteamCMD to ${STEAMCMD_DIR}..."
    mkdir -p "$STEAMCMD_DIR"
    cd "$STEAMCMD_DIR"
    
    # Download and extract SteamCMD
    echo "Downloading SteamCMD..."
    if wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz; then
        echo "SteamCMD download successful."
    else
        echo "ERROR: Failed to download SteamCMD!"
        exit 1
    fi
    
    echo "Extracting SteamCMD..."
    if tar -xzf steamcmd_linux.tar.gz; then
        echo "SteamCMD extraction successful."
    else
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
    
    echo "SteamCMD installed successfully."
    cd "$APP_DIR"
fi

# Create symlinks in standard paths
echo "Creating symlinks..."
if [ -f "${STEAMCMD_DIR}/steamcmd.sh" ]; then
    # Create symlink for SteamCMD if needed
    if [ ! -e "/usr/local/bin/steamcmd" ]; then
        ln -sf "${STEAMCMD_DIR}/steamcmd.sh" "/usr/local/bin/steamcmd" || echo "Warning: Failed to create steamcmd symlink, but continuing anyway."
        echo "Created symlink for steamcmd in /usr/local/bin/"
    fi
fi

# Verify all installations and permissions as a final check
echo "Performing final verification checks..."

if ! command -v 7z &> /dev/null; then
    echo "ERROR: 7zip installation verification failed!"
    exit 1
else
    echo "7zip verified at $(which 7z)"
fi

if [ ! -x "${STEAMCMD_DIR}/steamcmd.sh" ]; then
    echo "ERROR: SteamCMD verification failed!"
    exit 1
else
    echo "SteamCMD verified at ${STEAMCMD_DIR}/steamcmd.sh"
fi

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