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

# Install dependencies using our script
RUN chmod +x install_dependencies.sh && bash install_dependencies.sh

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for better security
RUN useradd -m appuser && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Create required directories with proper permissions
RUN mkdir -p /app/logs /app/output /app/game && chmod 755 /app/logs /app/output /app/game

# Expose the application port
EXPOSE 7860

# Use a proper entrypoint script for startup
COPY --chmod=0755 start.sh /app/start.sh
CMD ["/app/start.sh"]
