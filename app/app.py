import os
import sys
import gradio as gr
import time
import logging
import subprocess
import traceback
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Let's log Gradio version
try:
    logger.info(f"Gradio version: {gr.__version__}")
except:
    logger.info("Could not determine Gradio version")

def system_health_check():
    """Basic system health check that runs on startup"""
    try:
        # Check disk space
        logger.info("Checking disk space...")
        disk_usage = os.statvfs('/')
        free_space_gb = (disk_usage.f_bavail * disk_usage.f_frsize) / (1024**3)
        
        # Check for 7zip
        logger.info("Checking for 7zip...")
        has_7zip = subprocess.run(["which", "7z"], capture_output=True).returncode == 0
        
        # Check for steamcmd
        logger.info("Checking for steamcmd...")
        steamcmd_path = "/app/steamcmd/steamcmd.sh"
        has_steamcmd = os.path.exists(steamcmd_path)
        
        # Build health report
        report = [
            f"Available disk space: {free_space_gb:.2f} GB",
            f"7zip installed: {'Yes' if has_7zip else 'No'}",
            f"SteamCMD installed: {'Yes' if has_steamcmd else 'No'}"
        ]
        
        logger.info("Health check complete: %s", ", ".join(report))
        return "\n".join(report)
    except Exception as e:
        error_msg = f"Error during health check: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg

def update_status():
    """Function to manually update the status box"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    health_status = system_health_check()
    return f"Server running at {timestamp}\n\n{health_status}"

def greet(name):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Greeting user: {name}")
    return f"Hello, {name}! Server is up and running at {timestamp}."

# Function to keep the container alive in a separate thread
def keep_alive_thread():
    while True:
        logger.info("Keep-alive thread running...")
        time.sleep(60)

# Start the keep-alive thread
threading.Thread(target=keep_alive_thread, daemon=True).start()

# Launch the app - using the simplest interface possible for maximum compatibility
try:
    logger.info("Creating simple Gradio interface...")
    
    # Create a much simpler interface
    iface = gr.Interface(
        fn=greet,
        inputs="text",
        outputs="text",
        title="Railway App - Running",
        description="This app is running successfully in Railway! SteamCMD and 7zip are installed."
    )
    
    logger.info("Launching Gradio app...")
    port = int(os.getenv("PORT", 7860))
    
    # Use minimal launch parameters
    iface.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=True
    )
    
except Exception as e:
    logger.critical(f"Fatal error: {str(e)}\n{traceback.format_exc()}")
    # Just keep the container alive
    while True:
        logger.error("Application crashed but keeping container alive")
        time.sleep(300) 
