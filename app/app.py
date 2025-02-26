import os
import sys
import gradio as gr
import time
import logging
import subprocess
import traceback
import threading
import shutil

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

def install_steamcmd():
    """Install SteamCMD properly with all required dependencies"""
    try:
        logger.info("Installing SteamCMD and dependencies...")
        
        # Install required 32-bit libraries
        subprocess.run(["apt-get", "update"], check=True)
        subprocess.run([
            "apt-get", "install", "-y",
            "lib32gcc-s1",  # Updated package name for newer Debian/Ubuntu
            "lib32stdc++6",
            "libsdl2-2.0-0:i386",
            "libtinfo5:i386"
        ], check=True)
        
        # Clean and reinstall SteamCMD properly
        if os.path.exists("/app/steamcmd"):
            shutil.rmtree("/app/steamcmd")
        
        os.makedirs("/app/steamcmd", exist_ok=True)
        os.chdir("/app/steamcmd")
        
        # Download SteamCMD
        subprocess.run(["wget", "-q", "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz"], check=True)
        subprocess.run(["tar", "-xzf", "steamcmd_linux.tar.gz"], check=True)
        subprocess.run(["rm", "steamcmd_linux.tar.gz"], check=True)
        
        # Set executable permissions
        subprocess.run(["chmod", "+x", "steamcmd.sh"], check=True)
        
        # Run steamcmd once to update and install itself properly
        logger.info("Running initial SteamCMD setup...")
        process = subprocess.run(
            ["./steamcmd.sh", "+quit"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        logger.info(f"SteamCMD output: {process.stdout}")
        
        if process.returncode != 0:
            return f"SteamCMD installation failed with code {process.returncode}\n{process.stdout}"
        
        return "SteamCMD installed successfully!"
    
    except Exception as e:
        error_msg = f"Error during SteamCMD installation: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg

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
        
        # Test steamcmd
        steamcmd_working = False
        if has_steamcmd:
            try:
                # Run a simple test command
                test_result = subprocess.run(
                    [steamcmd_path, "+quit"], 
                    capture_output=True, 
                    text=True,
                    timeout=10
                )
                steamcmd_working = test_result.returncode == 0
            except:
                steamcmd_working = False
        
        # Build health report
        report = [
            f"Available disk space: {free_space_gb:.2f} GB",
            f"7zip installed: {'Yes' if has_7zip else 'No'}",
            f"SteamCMD installed: {'Yes' if has_steamcmd else 'No'}",
            f"SteamCMD working: {'Yes' if steamcmd_working else 'No'}"
        ]
        
        logger.info("Health check complete: %s", ", ".join(report))
        return "\n".join(report)
    except Exception as e:
        error_msg = f"Error during health check: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg

def run_steamcmd_command(app_id, username="anonymous"):
    """Run SteamCMD to download a game by app_id"""
    try:
        # First make sure we have numbers only for app_id
        # Strip any URLs or other text to get just the app ID number
        import re
        app_id_match = re.search(r'(\d+)', app_id)
        if app_id_match:
            app_id = app_id_match.group(1)
        else:
            yield "Invalid app ID. Please enter a numeric Steam app ID."
            return
            
        logger.info(f"Starting download for App ID: {app_id}")
        
        # Create command
        output_dir = "/app/game"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        # Check if SteamCMD is working
        steamcmd_path = "/app/steamcmd/steamcmd.sh"
        if not os.path.exists(steamcmd_path):
            yield "SteamCMD not installed. Installing now..."
            result = install_steamcmd()
            yield result
            
            if "failed" in result.lower():
                yield "Cannot proceed with download as SteamCMD installation failed."
                return
        
        # Build SteamCMD command
        cmd = [
            "/app/steamcmd/steamcmd.sh",
            "+login", username,
            "+force_install_dir", output_dir,
            "+app_update", str(app_id),
            "+quit"
        ]
        
        # Execute command with real-time output capture
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Collect output
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            output_lines.append(line.strip())
            if len(output_lines) > 100:  # Keep only last 100 lines
                output_lines.pop(0)
            logger.info(f"STEAMCMD: {line.strip()}")
            yield "\n".join(output_lines)
        
        # Get final exit code
        process.stdout.close()
        return_code = process.wait()
        
        # Check result
        if return_code != 0:
            yield f"\n\nDownload failed with exit code {return_code}"
        else:
            yield "\n\nDownload completed successfully!"
            
    except Exception as e:
        error_msg = f"Error during download: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        yield error_msg

def list_downloaded_files():
    """List files in the download directory"""
    try:
        game_dir = "/app/game"
        if not os.path.exists(game_dir):
            return "No files downloaded yet."
            
        file_list = []
        total_size = 0
        
        for root, dirs, files in os.walk(game_dir):
            for file in files:
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                total_size += size
                file_list.append(f"{file_path.replace(game_dir, '')} - {size/1024**2:.2f} MB")
        
        if not file_list:
            return "No files found in download directory."
            
        return f"Total size: {total_size/1024**3:.2f} GB\n\n" + "\n".join(file_list)
    except Exception as e:
        error_msg = f"Error listing files: {str(e)}"
        logger.error(error_msg)
        return error_msg

# Function to keep the container alive in a separate thread
def keep_alive_thread():
    while True:
        logger.info("Keep-alive thread running...")
        time.sleep(60)

# Start the keep-alive thread
threading.Thread(target=keep_alive_thread, daemon=True).start()

# Launch the app with the custom UI
try:
    logger.info("Creating Gradio interface...")
    
    with gr.Blocks(title="Steam Game Downloader") as demo:
        gr.Markdown("# Steam Game Downloader")
        gr.Markdown("Download games from Steam using SteamCMD")
        
        with gr.Tab("System Status"):
            status_output = gr.Textbox(
                value=system_health_check(),
                label="System Status",
                lines=8,
                interactive=False
            )
            refresh_btn = gr.Button("Refresh Status")
            refresh_btn.click(fn=system_health_check, inputs=None, outputs=status_output)
            
            install_btn = gr.Button("Install/Repair SteamCMD")
            install_output = gr.Textbox(label="Installation Output", lines=10)
            install_btn.click(fn=install_steamcmd, inputs=None, outputs=install_output)
        
        with gr.Tab("Download Game"):
            with gr.Row():
                app_id = gr.Textbox(
                    label="Steam App ID (e.g. 230410 for Warframe)", 
                    value="",
                    placeholder="Enter numeric App ID or paste Steam store URL"
                )
                username = gr.Textbox(label="Steam Username (or anonymous)", value="anonymous")
            
            gr.Markdown("""
            ## How to find the App ID
            1. Go to the Steam store page for the game
            2. The App ID is the number in the URL: https://store.steampowered.com/app/XXXXXX/
            3. Free games can be downloaded with the anonymous account
            4. Paid games require a valid Steam login
            """)
            
            download_btn = gr.Button("Download Game")
            download_output = gr.Textbox(label="Download Progress", lines=15)
            
            download_btn.click(
                fn=run_steamcmd_command,
                inputs=[app_id, username],
                outputs=download_output
            )
        
        with gr.Tab("File Browser"):
            file_output = gr.Textbox(label="Downloaded Files", lines=20)
            list_btn = gr.Button("List Downloaded Files")
            list_btn.click(fn=list_downloaded_files, inputs=None, outputs=file_output)
    
    # Launch the demo
    logger.info("Launching Gradio app...")
    port = int(os.getenv("PORT", 7860))
    
    demo.launch(
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
