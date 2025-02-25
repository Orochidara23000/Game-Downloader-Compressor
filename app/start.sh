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

# Run installation script to ensure dependencies are set up
echo "Running install_dependencies.sh..."
bash install_dependencies.sh

# Run the setup script
echo "Running setup.py..."
python setup.py

# Start the main application
echo "Starting main application..."
python main.py