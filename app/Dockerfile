FROM python:3.11-slim

WORKDIR /app

# Install essential dependencies
RUN apt-get update && apt-get install -y \
    p7zip-full \
    wget \
    curl \
    && apt-get clean

# Install only the required Python packages
RUN pip install --no-cache-dir gradio

# Create required directories and setup steamcmd
RUN mkdir -p /app/steamcmd && \
    mkdir -p /app/logs /app/output /app/game && \
    cd /app/steamcmd && \
    wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz && \
    tar -xzf steamcmd_linux.tar.gz && \
    rm steamcmd_linux.tar.gz && \
    chmod +x steamcmd.sh

# Copy only the essential app file
COPY app.py /app/

# Expose the Gradio port
EXPOSE 7860

# Use a simple, direct command to run the app
CMD ["python", "app.py"]