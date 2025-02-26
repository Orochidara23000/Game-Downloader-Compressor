#!/bin/bash
set -e

echo "Current directory: $(pwd)"
echo "Directory listing:"
ls -la

# Ensure directories exist with proper permissions
mkdir -p logs downloads steamcmd
chmod 755 logs downloads steamcmd

# Check for steamcmd
echo "Checking for steamcmd:"
if [ -f "./steamcmd/steamcmd.sh" ]; then
    echo "steamcmd found at ./steamcmd/steamcmd.sh"
    chmod +x ./steamcmd/steamcmd.sh
else
    echo "ERROR: steamcmd not found at ./steamcmd/steamcmd.sh"
    echo "Running install_dependencies.sh..."
    bash install_dependencies.sh
fi

# Start the application
echo "Starting application..."
python app.py
