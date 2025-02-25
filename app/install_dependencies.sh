#!/bin/bash
set -euxo pipefail

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
else
  echo "SteamCMD already exists."
fi

# Install LocalXpose using npm (now the package is "loclx")
if ! command -v loclx >/dev/null 2>&1; then
  echo "Installing LocalXpose (loclx) via npm..."
  npm install -g loclx || { echo "Failed to install LocalXpose (loclx)"; exit 2; }
else
  echo "LocalXpose (loclx) is already installed."
fi

echo "All dependencies installed successfully."
