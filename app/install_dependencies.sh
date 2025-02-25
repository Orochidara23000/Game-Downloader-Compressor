#!/bin/bash
set -euo pipefail

echo "Starting install_dependencies.sh script."

# Check if 7z is installed (should be provided by p7zip-full)
if ! command -v 7z >/dev/null 2>&1; then
  echo "Error: 7z not found. It should have been installed via the Dockerfile."
  exit 1
else
  echo "7z is installed."
fi

# Install SteamCMD if not found
if [ ! -d "./steamcmd" ]; then
  echo "Downloading SteamCMD..."
  mkdir -p steamcmd
  wget -O steamcmd/steamcmd_linux.tar.gz https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz || { echo "Failed to download SteamCMD"; exit 2; }
  echo "Extracting SteamCMD..."
  tar -xvzf steamcmd/steamcmd_linux.tar.gz -C steamcmd || { echo "Failed to extract SteamCMD"; exit 2; }
  rm steamcmd/steamcmd_linux.tar.gz
  
  # Initial SteamCMD update to ensure it's working
  ./steamcmd/steamcmd.sh +quit || { echo "Failed to run initial SteamCMD update"; exit 3; }
else
  echo "SteamCMD already exists."
fi

# Verify LocalXpose (loclx) installation - but don't reinstall as it's done in Dockerfile
if ! command -v loclx >/dev/null 2>&1; then
  echo "LocalXpose (loclx) not found in PATH. It should have been installed via Dockerfile."
  # Check if it exists in the npm global bin directory
  NPM_BIN=$(npm bin -g)
  if [ -f "$NPM_BIN/loclx" ]; then
    echo "LocalXpose found at $NPM_BIN/loclx. Please ensure this path is in your PATH environment variable."
    echo "Current PATH: $PATH"
  else
    echo "Warning: LocalXpose (loclx) not found. The application may not function correctly."
  fi
else
  echo "LocalXpose (loclx) is properly installed."
fi

# Create required directories
mkdir -p logs output
echo "Created required directories."

echo "All dependencies installed successfully."
