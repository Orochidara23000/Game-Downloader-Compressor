FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
      lib32stdc++6 \
      wget \
      unzip \
      tar \
      ca-certificates \
      p7zip-full

WORKDIR /app
COPY . /app

RUN chmod +x install_dependencies.sh && bash install_dependencies.sh

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7860
CMD ["python", "main.py"]
