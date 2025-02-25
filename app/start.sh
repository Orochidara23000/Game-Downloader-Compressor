#!/bin/bash
set -e

# Check if running in Railway environment
if [ -n "${RAILWAY_ENVIRONMENT:-}" ]; then
    echo "Starting application in Railway environment"
else
    echo "Starting application in development environment"
fi

# Ensure directories exist with proper permissions
mkdir -p logs output game
chmod 755 logs output game

# Skip dependency installation when running in a Docker container
if [ -f "/.dockerenv" ]; then
    echo "Running in Docker container - dependencies already installed"
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
