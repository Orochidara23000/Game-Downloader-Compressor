#!/bin/bash
set -euxo pipefail

echo "Starting install_dependencies.sh script."

# Check if 7z is installed
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

# Install LocalXpose if not found
if [ ! -d "./localxpose" ]; then
  echo "Downloading LocalXpose..."
  mkdir -p localxpose
  wget -O localxpose/localxpose.zip https://github.com/localxpose/localxpose/releases/latest/download/localxpose-linux-amd64.zip || { echo "Failed to download LocalXpose"; exit 2; }
  echo "Extracting LocalXpose..."
  unzip localxpose/localxpose.zip -d localxpose || { echo "Failed to unzip LocalXpose"; exit 2; }
  rm localxpose/localxpose.zip
  chmod +x localxpose/localxpose
else
  echo "LocalXpose already exists."
fi

echo "All dependencies installed successfully."
