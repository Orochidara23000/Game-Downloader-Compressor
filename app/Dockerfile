FROM python:3.11-slim

WORKDIR /app
COPY . /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    lib32stdc++6 \
    wget \
    unzip \
    tar \
    ca-certificates \
    p7zip-full \
    findutils \
    procps \
    dos2unix \
    && apt-get clean

# Convert Windows line endings to Unix for all shell scripts
RUN find /app -type f -name "*.sh" -exec dos2unix {} \; || echo "No shell scripts found or dos2unix failed"

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Explicitly install SteamCMD and 7zip
RUN echo "Installing 7zip..." && \
    apt-get update && apt-get install -y p7zip-full && \
    echo "7zip installed at:" && which 7z && \
    echo "Installing SteamCMD..." && \
    mkdir -p /app/steamcmd && \
    cd /app/steamcmd && \
    wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz && \
    tar -xzf steamcmd_linux.tar.gz && \
    rm steamcmd_linux.tar.gz && \
    chmod +x steamcmd.sh && \
    echo "SteamCMD installed at:" && \
    ls -la /app/steamcmd/steamcmd.sh && \
    # Create directories and set permissions
    mkdir -p /app/logs /app/output /app/game && \
    chmod -R 755 /app/logs /app/output /app/game /app/steamcmd && \
    chmod +x /app/start.sh /app/install_dependencies.sh

# Expose the application port
EXPOSE 7860

# Create helpful symlinks to ensure tools are in expected locations
RUN if [ ! -e /usr/local/bin/7z ] && [ -e /usr/bin/7z ]; then ln -sf /usr/bin/7z /usr/local/bin/7z; fi && \
    if [ ! -e /usr/local/bin/steamcmd ] && [ -e /app/steamcmd/steamcmd.sh ]; then ln -sf /app/steamcmd/steamcmd.sh /usr/local/bin/steamcmd; fi

# Set a healthcheck to restart if server is down
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:7860/ || exit 1

# Use a simplified command that directly runs Python (avoiding start.sh issues)
CMD ["python", "setup.py"]
