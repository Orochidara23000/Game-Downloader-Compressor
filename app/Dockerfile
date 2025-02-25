FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
      lib32stdc++6 \
      wget \
      unzip \
      tar \
      ca-certificates \
      p7zip-full

WORKDIR /app
COPY . /app

# Modified approach: Install dependencies directly in Dockerfile 
# instead of using the install_dependencies.sh script
RUN mkdir -p /app/logs /app/output /app/game /app/steamcmd && \
    chmod 755 /app/logs /app/output /app/game && \
    cd /app/steamcmd && \
    wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz && \
    tar -xzf steamcmd_linux.tar.gz && \
    rm steamcmd_linux.tar.gz && \
    chmod +x steamcmd.sh && \
    ./steamcmd.sh +quit || echo "SteamCMD initial setup completed with warnings"

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for better security
RUN useradd -m appuser && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 7860

# Use a proper entrypoint script for startup
COPY --chmod=0755 start.sh /app/start.sh
CMD ["/app/start.sh"]
