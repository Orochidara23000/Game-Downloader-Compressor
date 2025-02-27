#!/bin/bash
set -e

echo "Current directory: $(pwd)"
echo "Directory listing:"
ls -la

# Check if running in Railway environment
if [ -n "${RAILWAY_ENVIRONMENT:-}" ]; then
    echo "Starting application in Railway environment"
else
    echo "Starting application in development environment"
fi

# Ensure directories exist with proper permissions
mkdir -p logs output game
chmod 755 logs output game

# Check for steamcmd and 7z before proceeding
echo "Checking for steamcmd:"
if [ -f "./steamcmd/steamcmd.sh" ]; then
    echo "steamcmd found at ./steamcmd/steamcmd.sh"
    chmod +x ./steamcmd/steamcmd.sh
else
    echo "ERROR: steamcmd not found at ./steamcmd/steamcmd.sh"
    ls -la ./steamcmd 2>/dev/null || echo "steamcmd directory does not exist"
fi

echo "Checking for 7zip:"
if command -v 7z &>/dev/null; then
    echo "7zip found at $(which 7z)"
else
    echo "ERROR: 7zip not found in PATH"
    apt-get update && apt-get install -y p7zip-full
    if command -v 7z &>/dev/null; then
        echo "7zip installed successfully at $(which 7z)"
    else
        echo "ERROR: Failed to install 7zip"
    fi
fi

# Skip dependency installation when running in a Docker container
if [ -f "/.dockerenv" ]; then
    echo "Running in Docker container - dependencies should already be installed"
else
    # Only run installation script in non-Docker environments
    echo "Running install_dependencies.sh..."
    bash install_dependencies.sh
fi

# Run the setup script
echo "Running setup.py..."
python setup.py

# Start the main application
echo "Starting main application..."
python main.py