FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (removed 7zip and other compression tools)
RUN apt-get update && apt-get install -y \
    lib32gcc-s1 \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/logs /app/downloads /app/steamcmd && \
    chmod -R 755 /app/logs /app/downloads /app/steamcmd

# Expose the application port
EXPOSE 7860

# Set a healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:7860/ || exit 1

# Start the application
CMD ["python", "app.py"]
