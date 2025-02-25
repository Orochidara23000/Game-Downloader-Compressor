FROM python:3.11-slim

WORKDIR /app
COPY . /app

# Install system dependencies - 7zip
RUN apt-get update && apt-get install -y \
      lib32stdc++6 \
      wget \
      unzip \
      tar \
      ca-certificates \
      p7zip-full \
      findutils && \
    apt-get clean && \
    # Verify 7zip installation
    which 7z && \
    7z --help

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create steamcmd directory and install SteamCMD in the correct location
RUN mkdir -p /app/steamcmd && \
    cd /app/steamcmd && \
    wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz && \
    tar -xzf steamcmd_linux.tar.gz && \
    rm steamcmd_linux.tar.gz && \
    chmod +x steamcmd.sh && \
    # Verify steamcmd installation
    ls -la /app/steamcmd/steamcmd.sh && \
    cd /app && \
    # Create other required directories
    mkdir -p /app/logs /app/output /app/game && \
    chmod -R 755 /app/logs /app/output /app/game /app/steamcmd && \
    # Make start.sh executable
    chmod +x /app/start.sh

# Create non-root user
RUN useradd -m appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 7860

# Debug the environment before starting
CMD ["bash", "-c", "echo 'Content of app directory:' && ls -la /app && echo 'SteamCMD exists:' && test -f /app/steamcmd/steamcmd.sh && echo 'Yes' || echo 'No' && echo '7z location:' && which 7z || echo '7z not found' && echo 'Starting app...' && /app/start.sh"]
