FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    lib32gcc-s1 \
    dos2unix \
    p7zip-full \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . .

# Convert Windows line endings to Unix for shell scripts
RUN find /app -type f -name "*.sh" -exec dos2unix {} \; || echo "No shell scripts found or dos2unix failed"

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Make scripts executable
RUN chmod +x /app/start.sh /app/install_dependencies.sh

# Create necessary directories
RUN mkdir -p /app/logs /app/downloads /app/steamcmd && \
    chmod -R 755 /app/logs /app/downloads /app/steamcmd

# Install SteamCMD
RUN ./install_dependencies.sh

# Create symlinks for convenience
RUN if [ ! -e /usr/local/bin/steamcmd ] && [ -e /app/steamcmd/steamcmd.sh ]; then \
    ln -sf /app/steamcmd/steamcmd.sh /usr/local/bin/steamcmd; \
    fi

# Expose the application port
EXPOSE 7860

# Set a healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:7860/ || exit 1

# Start the application
CMD ["python", "app.py"]
