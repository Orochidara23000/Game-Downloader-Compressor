# Use a lightweight Python image
FROM python:3.11-slim

# Set the working directory to /app
WORKDIR /app

# Copy the project files from the app folder
COPY . /app

# Make sure our installation script is executable
RUN chmod +x install_dependencies.sh && ./install_dependencies.sh

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port your app will run on
EXPOSE 7860

# Define the command to run your app
CMD ["python", "main.py"]
