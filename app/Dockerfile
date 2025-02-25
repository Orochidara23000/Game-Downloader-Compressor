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

# Install loclx globally via npm
RUN npm install -g loclx

# Add the global npm bin directory to PATH.
# This makes sure that the 'loclx' binary can be found.
ENV PATH="$(npm bin -g):$PATH"

WORKDIR /app
COPY . /app

RUN chmod +x install_dependencies.sh && bash install_dependencies.sh

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7860
CMD ["python", "main.py"]
