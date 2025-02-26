import os
import sys
import gradio as gr
import time
import logging
import subprocess
import traceback
import threading
import shutil
import re
import tempfile
import glob
import json

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

# Global variables to track download state
DOWNLOAD_STATE = {
    "app_id": None,
    "username": "anonymous",
    "platform": "windows",
    "in_progress": False,
    "completed": False,
    "last_progress": 0
}

# Define list of free games that work with anonymous login
FREE_GAMES = [
    {"name": "Team Fortress 2", "app_id": "440", "platform": "windows/linux"},
    {"name": "Dota 2", "app_id": "570", "platform": "windows/linux/macos"},
    {"name": "Counter-Strike 2", "app_id": "730", "platform": "windows/linux"},
    {"name": "Path of Exile", "app_id": "238960", "platform": "windows"},
    {"name": "Warframe", "app_id": "230410", "platform": "windows"},
    {"name": "Destiny 2", "app_id": "1085660", "platform": "windows"},
    {"name": "Apex Legends", "app_id": "1172470", "platform": "windows"},
    {"name": "War Thunder", "app_id": "236390", "platform": "windows/linux/macos"}
]

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

def extract_app_id(input_text):
    """Extract app ID from text or URL"""
    # Look for app ID in URLs
    url_match = re.search(r'store\.steampowered\.com/app/(\d+)', input_text)
    if url_match:
        return url_match.group(1)
    
    # Look for just numbers
    num_match = re.search(r'^\s*(\d+)\s*$', input_text)
    if num_match:
        return num_match.group(1)
    
    # Return None if no app ID found
    return None

def create_steam_script(username, password, app_id, output_dir, platform="windows"):
    """Create a SteamCMD script file to handle login and download"""
    script_content = f"""@ShutdownOnFailedCommand 1
@NoPromptForPassword 1
force_install_dir {output_dir}
"""
    
    # Handle login based on whether it's anonymous or not
    if username.lower() == "anonymous":
        script_content += "login anonymous\n"
    else:
        script_content += f"login {username} {password}\n"
    
    # Set platform override if needed
    if platform.lower() != "linux":
        script_content += f"@sSteamCmdForcePlatformType {platform}\n"
    
    # Add the app update command
    script_content += f"app_update {app_id} validate\n"
    script_content += "quit\n"
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w') as f:
        f.write(script_content)
        return f.name

def run_steamcmd_with_auth(app_id, username, password, steam_guard, platform, auto_compress, clean_after_compress):
    """Run SteamCMD with proper authentication and platform selection"""
    global DOWNLOAD_STATE
    
    try:
        # Reset download state
        DOWNLOAD_STATE = {
            "app_id": None,
            "username": username,
            "platform": platform,
            "in_progress": False,
            "completed": False,
            "last_progress": 0,
            "auto_compress": auto_compress,
            "clean_after_compress": clean_after_compress
        }
        
        # Extract app ID if provided as URL
        app_id = extract_app_id(app_id)
        
        if not app_id:
            return "Invalid App ID. Please provide a valid Steam App ID or URL.", "No active download"
            
        DOWNLOAD_STATE["app_id"] = app_id
            
        # Validate input
        if username != "anonymous" and not password:
            return "Password is required for non-anonymous login.", "No active download"
            
        logger.info(f"Starting download for App ID: {app_id}")
        
        # Create output directories if they don't exist
        os.makedirs("/app/game", exist_ok=True)
        os.makedirs("/app/output", exist_ok=True)
        
        # Create a temporary script file for SteamCMD
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as script_file:
            script_content = [
                "@ShutdownOnFailedCommand 1",
                "@NoPromptForPassword 1",
                f"force_install_dir /app/game",
                "login"
            ]
            
            # Add authentication details
            if username != "anonymous":
                script_content.append(f"{username} {password}")
                if steam_guard:
                    script_content.append(steam_guard)
            else:
                script_content.append("anonymous")
                
            # Add platform override for Windows games
            if platform == "windows":
                script_content.append("@sSteamCmdForcePlatformType windows")
            elif platform == "macos":
                script_content.append("@sSteamCmdForcePlatformType macos")
                
            # Add the app download command with validation
            script_content.append(f"app_update {app_id} validate")
            script_content.append("quit")
            
            # Write the script content
            script_file.write("\n".join(script_content).encode())
            script_file_path = script_file.name
        
        # Start download in a separate thread to not block the UI
        def download_thread():
            try:
                DOWNLOAD_STATE["in_progress"] = True
                DOWNLOAD_STATE["completed"] = False
                DOWNLOAD_STATE["last_progress"] = 0
                
                # Run SteamCMD with the script
                process = subprocess.Popen(
                    ["/app/steamcmd/steamcmd.sh", "+runscript", script_file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                output_lines = []
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                        
                    logger.info(f"STEAMCMD: {line.strip()}")
                    output_lines.append(line.strip())
                    
                    # Extract progress information
                    progress_match = re.search(r'progress: ([0-9.]+)', line)
                    if progress_match:
                        try:
                            progress = float(progress_match.group(1))
                            DOWNLOAD_STATE["last_progress"] = progress
                        except:
                            pass
                            
                # Wait for process to finish
                process.wait()
                
                # Clean up the script file
                try:
                    os.unlink(script_file_path)
                except:
                    pass
                    
                # Check if download completed successfully
                if process.returncode == 0:
                    DOWNLOAD_STATE["completed"] = True
                    DOWNLOAD_STATE["in_progress"] = False
                    output_lines.append("Download completed successfully!")
                    
                    # Auto-compress if enabled
                    if DOWNLOAD_STATE["auto_compress"]:
                        output_lines.append("Auto-compression enabled. Starting compression...")
                        compress_result = compress_game_files(DOWNLOAD_STATE["clean_after_compress"])[0]
                        output_lines.append("Compression result:")
                        output_lines.append(compress_result)
                else:
                    DOWNLOAD_STATE["in_progress"] = False
                    output_lines.append(f"Download failed with exit code {process.returncode}")
                
                return "\n".join(output_lines)
            except Exception as e:
                DOWNLOAD_STATE["in_progress"] = False
                error_msg = f"Error during download: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                return error_msg
        
        # Start the download thread
        threading.Thread(target=lambda: download_thread(), daemon=True).start()
        
        # Return initial message immediately
        return f"Starting download for App ID: {app_id}\nDownload is running in the background. This log will update periodically.", "⏳ Download starting..."
        
    except Exception as e:
        DOWNLOAD_STATE["in_progress"] = False
        error_msg = f"Error starting download: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg, "Error during download"

def resume_download(platform, auto_compress, clean_after_compress):
    """Resume an interrupted download"""
    global DOWNLOAD_STATE
    
    try:
        # Check if there's a download to resume
        if not DOWNLOAD_STATE["app_id"]:
            return "No download to resume. Please start a new download.", "No active download"
            
        # If download is already in progress, don't restart
        if DOWNLOAD_STATE["in_progress"]:
            return "Download is already in progress.", "⏳ Download in progress"
            
        app_id = DOWNLOAD_STATE["app_id"]
        username = DOWNLOAD_STATE["username"]
        
        # Update state with new options
        DOWNLOAD_STATE["platform"] = platform
        DOWNLOAD_STATE["auto_compress"] = auto_compress
        DOWNLOAD_STATE["clean_after_compress"] = clean_after_compress
        
        logger.info(f"Resuming download for App ID: {app_id}")
        
        # Create output directories if they don't exist
        os.makedirs("/app/game", exist_ok=True)
        os.makedirs("/app/output", exist_ok=True)
        
        # Create a temporary script file for SteamCMD
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as script_file:
            script_content = [
                "@ShutdownOnFailedCommand 1",
                "@NoPromptForPassword 1",
                f"force_install_dir /app/game",
                "login"
            ]
            
            # Add authentication details - for resume, just use anonymous or stored username
            if username and username != "anonymous":
                script_content.append(f"{username}")
                # For resume we can't include password/guard code since it might timeout
            else:
                script_content.append("anonymous")
                
            # Add platform override
            if platform == "windows":
                script_content.append("@sSteamCmdForcePlatformType windows")
            elif platform == "macos":
                script_content.append("@sSteamCmdForcePlatformType macos")
                
            # Add the app download command with validation
            script_content.append(f"app_update {app_id} validate")
            script_content.append("quit")
            
            # Write the script content
            script_file.write("\n".join(script_content).encode())
            script_file_path = script_file.name
        
        # Start download in a separate thread
        def resume_thread():
            try:
                DOWNLOAD_STATE["in_progress"] = True
                DOWNLOAD_STATE["completed"] = False
                
                # Run SteamCMD with the script
                process = subprocess.Popen(
                    ["/app/steamcmd/steamcmd.sh", "+runscript", script_file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                output_lines = []
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                        
                    logger.info(f"STEAMCMD: {line.strip()}")
                    output_lines.append(line.strip())
                    
                    # Extract progress information
                    progress_match = re.search(r'progress: ([0-9.]+)', line)
                    if progress_match:
                        try:
                            progress = float(progress_match.group(1))
                            DOWNLOAD_STATE["last_progress"] = progress
                        except:
                            pass
                
                # Wait for process to finish
                process.wait()
                
                # Clean up the script file
                try:
                    os.unlink(script_file_path)
                except:
                    pass
                    
                # Check if download completed successfully
                if process.returncode == 0:
                    DOWNLOAD_STATE["completed"] = True
                    DOWNLOAD_STATE["in_progress"] = False
                    output_lines.append("Download completed successfully!")
                    
                    # Auto-compress if enabled
                    if DOWNLOAD_STATE["auto_compress"]:
                        output_lines.append("Auto-compression enabled. Starting compression...")
                        compress_result = compress_game_files(DOWNLOAD_STATE["clean_after_compress"])[0]
                        output_lines.append("Compression result:")
                        output_lines.append(compress_result)
                else:
                    DOWNLOAD_STATE["in_progress"] = False
                    output_lines.append(f"Download failed with exit code {process.returncode}")
                
                return "\n".join(output_lines)
            except Exception as e:
                DOWNLOAD_STATE["in_progress"] = False
                error_msg = f"Error during resume: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                return error_msg
        
        # Start the resume thread
        threading.Thread(target=lambda: resume_thread(), daemon=True).start()
        
        # Return initial message immediately
        return f"Resuming download for App ID: {app_id}\nDownload is running in the background. This log will update periodically.", "⏳ Resuming download..."
        
    except Exception as e:
        DOWNLOAD_STATE["in_progress"] = False
        error_msg = f"Error resuming download: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg, "Error during resume"

def cancel_download():
    """Cancel an active download"""
    global DOWNLOAD_STATE
    
    try:
        # Check if there's a download to cancel
        if not DOWNLOAD_STATE["in_progress"]:
            return "No active download to cancel.", "No active download"
            
        # Find and kill SteamCMD processes
        try:
            subprocess.run(["pkill", "-f", "steamcmd"], check=False)
        except:
            pass
            
        # Update state
        DOWNLOAD_STATE["in_progress"] = False
        
        return "Download cancelled. You can resume it later with the Resume button.", "⚠️ Download cancelled"
    except Exception as e:
        error_msg = f"Error cancelling download: {str(e)}"
        logger.error(error_msg)
        return error_msg, "Error during cancellation"

def compress_game_files(clean_after_compress=False):
    """Compress game files with 7zip maximum compression"""
    try:
        game_dir = "/app/game"
        output_dir = "/app/output"
        
        # Check if game directory exists and has files
        if not os.path.exists(game_dir):
            return "No game files found to compress.", "No files to compress"
            
        # Find the app ID from the manifest
        app_id = DOWNLOAD_STATE.get("app_id", "unknown")
        manifest_files = glob.glob(f"{game_dir}/appmanifest_*.acf")
        if manifest_files:
            try:
                manifest_file = manifest_files[0]
                with open(manifest_file, 'r') as f:
                    content = f.read()
                    app_id_match = re.search(r'"appid"\s+"(\d+)"', content)
                    name_match = re.search(r'"name"\s+"([^"]+)"', content)
                    
                    if app_id_match:
                        app_id = app_id_match.group(1)
                    
                    if name_match:
                        game_name = name_match.group(1)
                        # Sanitize game name for filenames
                        game_name = re.sub(r'[^\w\-\.]', '_', game_name)
                    else:
                        game_name = f"game_{app_id}"
            except:
                game_name = f"game_{app_id}"
        else:
            game_name = f"game_{app_id}"
            
        # Create timestamp for the filename
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_file = f"{output_dir}/{game_name}_{timestamp}.7z"
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Start compression
        logger.info(f"Starting compression of game files to {output_file}")
        
        def compress_thread():
            try:
                # Create 7zip command with maximum compression
                process = subprocess.Popen(
                    ["7z", "a", "-mx=9", output_file, f"{game_dir}/*"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                output_lines = []
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                        
                    logger.info(f"7ZIP: {line.strip()}")
                    output_lines.append(line.strip())
                
                # Wait for process to finish
                process.wait()
                
                if process.returncode == 0:
                    output_lines.append(f"Compression completed successfully: {output_file}")
                    
                    # Clean up original files if requested
                    if clean_after_compress:
                        output_lines.append("Cleaning up original files...")
                        clean_result = clean_game_files()[0]
                        output_lines.append(clean_result)
                        
                    return "\n".join(output_lines)
                else:
                    return f"Compression failed with exit code {process.returncode}\n" + "\n".join(output_lines)
            except Exception as e:
                error_msg = f"Error during compression: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                return error_msg
        
        # Start compression thread
        thread = threading.Thread(target=lambda: compress_thread(), daemon=True)
        thread.start()
        
        return f"Starting compression of game files to {output_file}\nCompression is running in the background. This may take a while...", "Compressing game files..."
    except Exception as e:
        error_msg = f"Error setting up compression: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg, "Error during compression setup"

def clean_game_files():
    """Clean up original game files after compression"""
    try:
        game_dir = "/app/game"
        
        # Check if game directory exists
        if not os.path.exists(game_dir):
            return "No game files found to clean.", "No files to clean"
            
        # Get size before cleaning
        size_before = 0
        for root, dirs, files in os.walk(game_dir):
            for file in files:
                file_path = os.path.join(root, file)
                size_before += os.path.getsize(file_path)
                
        # Remove all files and subdirectories
        for item in os.listdir(game_dir):
            item_path = os.path.join(game_dir, item)
            if os.path.isfile(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
                
        # Reset download state
        global DOWNLOAD_STATE
        DOWNLOAD_STATE["completed"] = False
        DOWNLOAD_STATE["in_progress"] = False
        
        return f"Successfully cleaned {size_before/1024**3:.2f} GB of game files.", "Game files cleaned"
    except Exception as e:
        error_msg = f"Error cleaning game files: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg, "Error during cleanup"

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

def list_compressed_files():
    """List compressed output files"""
    try:
        output_dir = "/app/output"
        if not os.path.exists(output_dir):
            return "No compressed files exist yet."
            
        file_list = []
        total_size = 0
        
        for file in os.listdir(output_dir):
            if file.endswith('.7z'):
                file_path = os.path.join(output_dir, file)
                size = os.path.getsize(file_path)
                total_size += size
                file_list.append(f"{file} - {size/1024**2:.2f} MB")
        
        if not file_list:
            return "No compressed files found."
            
        return f"Total compressed files: {len(file_list)}\nTotal size: {total_size/1024**3:.2f} GB\n\n" + "\n".join(file_list)
    except Exception as e:
        error_msg = f"Error listing compressed files: {str(e)}"
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
    
    with gr.Blocks(title="Steam Game Downloader & Compressor") as demo:
        gr.Markdown("# 🎮 Steam Game Downloader & Compressor")
        gr.Markdown("Download games from Steam, compress them for easy transfer, and download the compressed files")
        
        # Download status display at the top - define it here so it's available to all tabs
        download_status = gr.Textbox(
            value=get_download_progress(),
            label="Download Status",
            interactive=False
        )
        
        # Download status auto-refresh
        download_status.change(fn=get_download_progress, inputs=None, outputs=download_status, every=5)
        
        with gr.Tab("System Status"):
            status_output = gr.Textbox(
                value=system_health_check(),
                label="System Status",
                lines=12,
                interactive=False
            )
            refresh_btn = gr.Button("🔄 Refresh Status")
            refresh_btn.click(fn=system_health_check, inputs=None, outputs=status_output)
            
            install_btn = gr.Button("🛠️ Install/Repair SteamCMD")
            install_output = gr.Textbox(label="Installation Output", lines=10)
            install_btn.click(fn=install_steamcmd, inputs=None, outputs=install_output)
        
        with gr.Tab("Download Game"):
            gr.Markdown("""
            ## 🚀 Steam Login & Download
            
            You can download games in two ways:
            1. **Anonymous login** - Only works for free-to-play games
            2. **Steam account login** - Required for games you own
            
            > ⚠️ **Security Notice**: Your credentials are only used for this download session and are not stored. 
            > For maximum security, consider using this tool only for free games with anonymous login.
            
            > ℹ️ **Platform Note**: Many games are Windows-only. If you get "Invalid platform" errors, make sure 
            > the platform is set to "windows" in the advanced settings below.
            """)
            
            # Create a markdown table of free games
            free_games_md = "### Free Games That Work With Anonymous Login:\n\n"
            free_games_md += "| Game | App ID | Platforms |\n|------|--------|----------|\n"
            for game in FREE_GAMES:
                free_games_md += f"| {game['name']} | {game['app_id']} | {game['platform']} |\n"
            
            gr.Markdown(free_games_md)
            
            with gr.Row():
                app_id = gr.Textbox(
                    label="Steam App ID or URL", 
                    value="",
                    placeholder="e.g. 440 or https://store.steampowered.com/app/440/Team_Fortress_2/"
                )
            
            with gr.Group():
                gr.Markdown("### Steam Authentication")
                with gr.Row():
                    username = gr.Textbox(
                        label="Steam Username", 
                        value="anonymous",
                        placeholder="Your Steam username or anonymous"
                    )
                    password = gr.Textbox(
                        label="Steam Password", 
                        value="",
                        placeholder="Required for non-anonymous login",
                        type="password"
                    )
                    steam_guard = gr.Textbox(
                        label="Steam Guard Code", 
                        value="",
                        placeholder="If 2FA is enabled"
                    )
                
                with gr.Accordion("Advanced Settings", open=False):
                    with gr.Row():
                        platform = gr.Dropdown(
                            label="Platform",
                            choices=["windows", "linux", "macos"],
                            value="windows",
                            info="Most games require Windows platform"
                        )
                        auto_compress = gr.Checkbox(
                            label="Auto-compress after download",
                            value=True,
                            info="Automatically compress game after download completes"
                        )
                        clean_after_compress = gr.Checkbox(
                            label="Clean after compression",
                            value=True,
                            info="Delete original files after successful compression"
                        )
            
            with gr.Row():
                download_btn = gr.Button("⬇️ Download Game")
                resume_btn = gr.Button("▶️ Resume Download")
                cancel_btn = gr.Button("⏹️ Cancel Download")
            
            download_output = gr.Textbox(label="Download Progress", lines=15)
            
            download_btn.click(
                fn=run_steamcmd_with_auth,
                inputs=[app_id, username, password, steam_guard, platform, auto_compress, clean_after_compress],
                outputs=[download_output, download_status]
            )
            
            resume_btn.click(
                fn=resume_download,
                inputs=[platform, auto_compress, clean_after_compress],
                outputs=[download_output, download_status]
            )
            
            cancel_btn.click(
                fn=cancel_download,
                inputs=None,
                outputs=[download_output, download_status]
            )
        
        with gr.Tab("Compress Files"):
            gr.Markdown("""
            ## 📦 Compress Downloaded Game Files
            
            Use this tab to compress downloaded game files using 7zip with maximum compression.
            The compressed file will be stored in the /app/output directory.
            
            After successful compression, you can optionally clean up the original files to save space.
            """)
            
            with gr.Row():
                compress_btn = gr.Button("🗜️ Compress Game Files")
                clean_btn = gr.Button("🧹 Clean Original Files")
            
            compress_output = gr.Textbox(label="Compression Progress", lines=15)
            
            compress_btn.click(
                fn=compress_game_files,
                inputs=[clean_after_compress],
                outputs=[compress_output, download_status]
            )
            
            clean_btn.click(
                fn=clean_game_files,
                inputs=None,
                outputs=[compress_output, download_status]
            )
        
        with gr.Tab("File Browser"):
            gr.Markdown("""
            ## 🔍 File Browser
            
            Use this tab to browse downloaded game files and compressed archives.
            You can monitor disk usage and see what files are currently on the system.
            """)
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Downloaded Game Files")
                    game_files_output = gr.Textbox(label="Game Files", lines=20)
                    list_game_btn = gr.Button("📂 List Downloaded Game Files")
                    list_game_btn.click(fn=list_downloaded_files, inputs=None, outputs=game_files_output)
                
                with gr.Column():
                    gr.Markdown("### Compressed Output Files")
                    compressed_files_output = gr.Textbox(label="Compressed Files", lines=20)
                    list_compressed_btn = gr.Button("📂 List Compressed Files")
                    list_compressed_btn.click(fn=list_compressed_files, inputs=None, outputs=compressed_files_output)
        
        with gr.Tab("Download Files"):
            gr.Markdown("""
            ## 💾 Download Compressed Files
            
            Select and download the compressed game files you've created.
            Files are listed in order of creation with the newest first.
            """)
            
            file_list = get_compressed_file_list()
            
            if file_list:
                file_dropdown = gr.Dropdown(
                    label="Select File to Download",
                    choices=file_list,
                    value=file_list[0] if file_list else None
                )
                
                refresh_files_btn = gr.Button("🔄 Refresh File List")
                download_file_btn = gr.Button("💾 Download Selected File")
                
                file_info = gr.Markdown(get_download_links())
                
                file_output = gr.File(label="Download File")
                
                # Functions for the download tab
                refresh_files_btn.click(
                    fn=lambda: gr.Dropdown(choices=get_compressed_file_list()),
                    inputs=None,
                    outputs=file_dropdown
                )
                
                refresh_files_btn.click(
                    fn=get_download_links,
                    inputs=None,
                    outputs=file_info
                )
                
                download_file_btn.click(
                    fn=get_file_for_download,
                    inputs=file_dropdown,
                    outputs=file_output
                )
            else:
                gr.Markdown("### No compressed files available yet")
                gr.Markdown("Use the Download Game tab to download a game, then compress it in the Compress Files tab.")
    
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
