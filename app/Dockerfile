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
    && apt-get clean

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
    chmod +x /app/start.sh

# We'll run as root for now to eliminate permission issues
# USER root

# Expose the application port
EXPOSE 7860

# Create helpful symlinks to ensure tools are in expected locations
RUN if [ ! -e /usr/local/bin/7z ] && [ -e /usr/bin/7z ]; then ln -sf /usr/bin/7z /usr/local/bin/7z; fi && \
    if [ ! -e /usr/local/bin/steamcmd ] && [ -e /app/steamcmd/steamcmd.sh ]; then ln -sf /app/steamcmd/steamcmd.sh /usr/local/bin/steamcmd; fi

# Use bash as entrypoint with enhanced debugging
ENTRYPOINT ["/bin/bash", "-c"]

# Debug and start application
CMD ["echo 'PATH:' && echo $PATH && \
     echo 'Installed packages:' && dpkg -l | grep p7zip && \
     echo '7z exists:' && which 7z && \
     echo 'SteamCMD exists:' && ls -la /app/steamcmd/steamcmd.sh && \
     echo 'Starting app with additional debugging...' && \
     export DEBUG=true && \
     bash /app/start.sh"]
