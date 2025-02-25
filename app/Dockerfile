FROM python:3.11-slim

# Install system dependencies including Node.js and npm
RUN apt-get update && apt-get install -y \
      lib32stdc++6 \
      wget \
      unzip \
      tar \
      ca-certificates \
      p7zip-full \
      nodejs \
      npm

# Install loclx globally via npm - centralize this installation here only
RUN npm install -g loclx

# Add the global npm bin directory to PATH explicitly
ENV PATH="/usr/local/bin:$PATH"

# Create non-root user for better security
RUN useradd -m appuser

# Set up working directory and permissions
WORKDIR /app
COPY . /app
RUN chown -R appuser:appuser /app

# Install dependencies
RUN chmod +x install_dependencies.sh && bash install_dependencies.sh

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Switch to non-root user
USER appuser

# Create required directories with proper permissions
RUN mkdir -p /app/logs /app/output /app/game && \
    chmod 755 /app/logs /app/output /app/game

# Expose the application port
EXPOSE 7860

# Use a proper entrypoint script for startup
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
