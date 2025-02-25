#!/bin/bash
set -ex
set -e

echo "Installing dependencies..."

# Install 7z if not available
if ! command -v 7z &> /dev/null; then
    echo "7z not found. Installing p7zip-full..."
    apt-get update && apt-get install -y p7zip-full
else
    echo "7z is already installed."
fi

# Install SteamCMD if not found
if [ ! -d "./steamcmd" ]; then
    echo "Downloading SteamCMD..."
    mkdir -p steamcmd
    wget -O steamcmd/steamcmd_linux.tar.gz https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz
    echo "Extracting SteamCMD..."
    tar -xvzf steamcmd/steamcmd_linux.tar.gz -C steamcmd
    rm steamcmd/steamcmd_linux.tar.gz
else
    echo "SteamCMD already exists."
fi

# Install LocalXpose if not found
if [ ! -d "./localxpose" ]; then
    echo "Downloading LocalXpose..."
    mkdir -p localxpose
    wget -O localxpose/localxpose.zip https://github.com/localxpose/localxpose/releases/latest/download/localxpose-linux-amd64.zip
    echo "Extracting LocalXpose..."
    unzip localxpose/localxpose.zip -d localxpose
    rm localxpose/localxpose.zip
    chmod +x localxpose/localxpose
else
    echo "LocalXpose already exists."
fi

echo "All dependencies installed."
