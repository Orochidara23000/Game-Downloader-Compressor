import os
import sys
import gradio as gr
import time
import logging
import subprocess
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

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

# Create a very simple Gradio app
logger.info("Initializing Gradio app")
with gr.Blocks(title="Railway App") as demo:
    gr.Markdown("# Railway App - Minimal Demo")
    
    status_box = gr.Textbox(
        label="System Status",
        value="Starting...",
        lines=10,
        interactive=False
    )
    
    def keep_alive():
        while True:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            health_status = system_health_check()
            yield f"Server running at {timestamp}\n\n{health_status}"
            time.sleep(30)
    
    demo.load(keep_alive, None, status_box, every=30)
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("## Test Connection")
            name_input = gr.Textbox(label="Your Name", value="User")
            greet_output = gr.Textbox(label="Response")
            
            def greet(name):
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Greeting user: {name}")
                return f"Hello, {name}! Server is up and running at {timestamp}."
            
            gr.Button("Test Connection").click(
                fn=greet, 
                inputs=[name_input], 
                outputs=[greet_output]
            )

# Launch the app
try:
    logger.info("Launching Gradio app...")
    port = int(os.getenv("PORT", 7860))
    demo.queue(max_size=10)
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=True,
        debug=True,
        show_error=True,
        prevent_thread_lock=True
    )
    
    # This code should never be reached in normal operation
    # since demo.launch() should block indefinitely
    logger.warning("Gradio launch exited unexpectedly, entering backup loop")
    while True:
        time.sleep(60)
        logger.info("Backup keep-alive loop running")

except Exception as e:
    logger.critical(f"Fatal error: {str(e)}\n{traceback.format_exc()}")
    # Still try to keep the container alive
    while True:
        logger.error("Application crashed but keeping container alive")
        time.sleep(300) 
