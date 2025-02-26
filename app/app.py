import os
import sys
import gradio as gr
import time
import logging
import subprocess
import traceback
from common import verify_steam_login, download_game, logger

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

def extract_app_id(steam_url):
    """Extract app ID from Steam URL."""
    try:
        # Handle URLs like https://store.steampowered.com/app/440/Team_Fortress_2/
        if '/app/' in steam_url:
            return steam_url.split('/app/')[1].split('/')[0]
        return None
    except:
        return None

def download_handler(steam_url, username, password, steam_guard_code, use_anonymous):
    """Handle the game download process."""
    app_id = extract_app_id(steam_url)
    if not app_id:
        return "Error: Invalid Steam URL. Please provide a valid Steam store URL."
    
    # Verify login first
    login_result = verify_steam_login(username, password, steam_guard_code, use_anonymous)
    if "successfully" not in login_result:
        return f"Login failed: {login_result}"
    
    # Start download
    success, message, download_path = download_game(
        app_id, username, password, steam_guard_code, use_anonymous
    )
    
    if success:
        return f"Success! Files downloaded to: {download_path}"
    else:
        return f"Download failed: {message}"

# Create Gradio interface
with gr.Blocks(title="Steam Game Downloader") as demo:
    gr.Markdown("# Steam Game Downloader")
    gr.Markdown("Download Steam game files for later compression in Google Colab")
    
    with gr.Row():
        steam_url = gr.Textbox(
            label="Steam Store URL",
            placeholder="https://store.steampowered.com/app/440/Team_Fortress_2/"
        )
    
    with gr.Row():
        use_anonymous = gr.Checkbox(label="Use Anonymous Login (for free games)", value=True)
    
    with gr.Group() as login_group:
        username = gr.Textbox(label="Steam Username", visible=False)
        password = gr.Textbox(label="Steam Password", type="password", visible=False)
        steam_guard = gr.Textbox(label="Steam Guard Code (if required)", visible=False)
    
    def toggle_login_fields(anonymous):
        return {
            username: gr.update(visible=not anonymous),
            password: gr.update(visible=not anonymous),
            steam_guard: gr.update(visible=not anonymous)
        }
    
    use_anonymous.change(toggle_login_fields, use_anonymous, [username, password, steam_guard])
    
    download_btn = gr.Button("Start Download")
    status_output = gr.Textbox(label="Status", lines=5)
    
    download_btn.click(
        fn=download_handler,
        inputs=[steam_url, username, password, steam_guard, use_anonymous],
        outputs=status_output
    )

# Launch the app
if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=True
    )

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
