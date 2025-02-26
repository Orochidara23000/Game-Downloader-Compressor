FROM python:3.11-slim

WORKDIR /app

# Add support for 32-bit libraries
RUN dpkg --add-architecture i386

# Install essential dependencies including SteamCMD requirements
RUN apt-get update && apt-get install -y \
    p7zip-full \
    wget \
    curl \
    lib32gcc-s1 \
    lib32stdc++6 \
    libsdl2-2.0-0:i386 \
    libtinfo5:i386 \
    && apt-get clean

# Install only the required Python packages
RUN pip install --no-cache-dir gradio

# Create required directories
RUN mkdir -p /app/logs /app/output /app/game

# Copy only the essential app file
COPY app.py /app/

# Expose the Gradio port
EXPOSE 7860

# Use a simple, direct command to run the app
CMD ["python", "app.py"]
