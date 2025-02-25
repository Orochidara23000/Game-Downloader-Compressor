FROM python:3.11-slim

# Install required packages including nodejs and npm
RUN apt-get update && apt-get install -y \
      lib32stdc++6 \
      wget \
      unzip \
      tar \
      ca-certificates \
      p7zip-full \
      nodejs \
      npm

WORKDIR /app
COPY . /app

# Run the installation script to install SteamCMD and LocalXpose (via npm)
RUN chmod +x install_dependencies.sh && bash install_dependencies.sh

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7860
CMD ["python", "main.py"]
