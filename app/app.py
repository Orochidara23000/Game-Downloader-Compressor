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
        
        return f"Available disk space: {free_space_gb:.2f} GB, 7zip installed: {'Yes' if has_7zip else 'No'}, SteamCMD installed: {'Yes' if has_steamcmd else 'No'}, SteamCMD working: {'Yes' if steamcmd_working else 'No'}"
    
    except Exception as e:
        error_msg = f"Error during health check: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg

def extract_app_id(input_text):
    """Extract app ID from URL or direct input"""
    # Check if input is directly an app ID
    if input_text.isdigit():
        return input_text
    
    # Try to extract app ID from URL
    app_id_match = re.search(r'app/(\d+)', input_text)
    if app_id_match:
        return app_id_match.group(1)
    
    return None

def run_steamcmd_with_auth(app_id, username, password, steam_guard, platform):
    """Run SteamCMD with proper authentication and platform selection"""
    try:
        # Extract app ID if provided as URL
        app_id = extract_app_id(app_id)
        
        if not app_id:
            return "Invalid App ID. Please provide a valid Steam App ID or URL."
            
        # Validate input
        if username != "anonymous" and not password:
            return "Password is required for non-anonymous login."
            
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
                
                # Wait for process to finish
                process.wait()
                
                # Clean up the script file
                try:
                    os.unlink(script_file_path)
                except:
                    pass
                
                if process.returncode == 0:
                    output_lines.append(f"Download completed successfully!")
                    return "\n".join(output_lines)
                else:
                    return f"Download failed with exit code {process.returncode}\n" + "\n".join(output_lines)
            except Exception as e:
                error_msg = f"Error during download: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                return error_msg
        
        # Start download thread
        thread = threading.Thread(target=lambda: download_thread(), daemon=True)
        thread.start()
        
        return f"Starting download for App ID: {app_id}\nDownload is running in the background. This may take a while..."
    except Exception as e:
        error_msg = f"Error setting up download: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg

def list_downloaded_files():
    """List downloaded game files"""
    try:
        game_dir = "/app/game"
        
        if not os.path.exists(game_dir):
            return "No downloaded files found."
            
        # Get total size
        total_size = 0
        file_list = []
        
        for root, dirs, files in os.walk(game_dir):
            for file in files:
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                total_size += file_size
                rel_path = os.path.relpath(file_path, game_dir)
                file_list.append(f"{rel_path} ({file_size/1024**2:.2f} MB)")
                
                if len(file_list) > 1000:  # Limit to 1000 files to avoid UI issues
                    file_list.append(f"... and more (showing first 1000 files)")
                    break
            
            if len(file_list) > 1000:
                break
                
        if not file_list:
            return "No files found in download directory."
            
        return f"Total size: {total_size/1024**3:.2f} GB\n\n" + "\n".join(file_list[:1000])
    except Exception as e:
        error_msg = f"Error listing files: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg

def list_compressed_files():
    """List compressed output files"""
    try:
        output_dir = "/app/output"
        
        if not os.path.exists(output_dir):
            return "No compressed files found."
            
        # Get file list with sizes
        file_list = []
        total_size = 0
        
        for file in os.listdir(output_dir):
            file_path = os.path.join(output_dir, file)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                total_size += file_size
                file_list.append(f"{file} ({file_size/1024**3:.2f} GB)")
                
        if not file_list:
            return "No compressed files found."
            
        return f"Total size: {total_size/1024**3:.2f} GB\n\n" + "\n".join(file_list)
    except Exception as e:
        error_msg = f"Error listing files: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg

def compress_game_files():
    """Compress downloaded game files using 7zip"""
    try:
        game_dir = "/app/game"
        output_dir = "/app/output"
        
        # Check if game directory exists and is not empty
        if not os.path.exists(game_dir):
            return "No downloaded game files found to compress."
            
        # Check if directory is empty
        if not os.listdir(game_dir):
            return "Game directory is empty. Nothing to compress."
            
        # Try to extract app ID from manifest files
        app_id = None
        manifest_file = None
        
        for file in os.listdir(game_dir):
            if file.startswith("appmanifest_") and file.endswith(".acf"):
                manifest_file = os.path.join(game_dir, file)
                app_id_match = re.search(r'appmanifest_(\d+).acf', file)
                if app_id_match:
                    app_id = app_id_match.group(1)
                    break
        
        # Extract game name from manifest
        game_name = None
        if manifest_file and os.path.exists(manifest_file):
            try:
                with open(manifest_file, 'r') as f:
                    content = f.read()
                    name_match = re.search(r'"name"\s+"([^"]+)"', content)
                    if name_match:
                        game_name = name_match.group(1)
                        # Sanitize the name for filename
                        game_name = re.sub(r'[^\w\-_]', '_', game_name)
            except:
                game_name = None
                
        # Use app_id if we have it, otherwise generic name
        if app_id:
            if game_name:
                output_filename = f"{game_name}_{app_id}"
            else:
                output_filename = f"game_{app_id}"
        else:
            output_filename = "game_files"
            
        # Create timestamp for the filename
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_file = f"{output_dir}/{output_filename}_{timestamp}.7z"
        
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
        
        return f"Starting compression of game files to {output_file}\nCompression is running in the background. This may take a while..."
    except Exception as e:
        error_msg = f"Error setting up compression: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg

def get_compressed_file_list():
    """Get a list of compressed files in the output directory"""
    output_dir = "/app/output"
    if not os.path.exists(output_dir):
        return []
    
    files = glob.glob(os.path.join(output_dir, "*.7z"))
    files.sort(key=os.path.getmtime, reverse=True)  # Sort by modification time, newest first
    return [os.path.basename(f) for f in files]

def get_file_for_download(filename):
    """Return the file path for the selected file"""
    if not filename:
        return None
    
    file_path = os.path.join("/app/output", filename)
    if os.path.exists(file_path):
        return file_path
    return None

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
                    platform = gr.Dropdown(
                        label="Platform",
                        choices=["windows", "linux", "macos"],
                        value="windows",
                        info="Most games require Windows platform"
                    )
            
            download_btn = gr.Button("⬇️ Download Game")
            download_output = gr.Textbox(label="Download Progress", lines=15)
            
            download_btn.click(
                fn=run_steamcmd_with_auth,
                inputs=[app_id, username, password, steam_guard, platform],
                outputs=download_output
            )
        
        with gr.Tab("Compress Files"):
            gr.Markdown("""
            ## 📦 Compress Downloaded Game Files
            
            Use this tab to compress downloaded game files using 7zip with maximum compression.
            The compressed file will be stored in the /app/output directory.
            """)
            
            compress_btn = gr.Button("🗜️ Compress Game Files")
            compress_output = gr.Textbox(label="Compression Progress", lines=15)
            
            compress_btn.click(
                fn=compress_game_files,
                inputs=None,
                outputs=compress_output
            )
        
        with gr.Tab("File Browser"):
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
        
        # Add the new download tab
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
                
                file_output = gr.File(label="Download File")
                
                # Functions for the download tab
                refresh_files_btn.click(
                    fn=lambda: gr.update(choices=get_compressed_file_list()),
                    inputs=None,
                    outputs=file_dropdown
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
