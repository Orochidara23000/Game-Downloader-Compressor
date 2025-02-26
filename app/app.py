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

# List of free games that work with anonymous login
FREE_GAMES = [
    {"name": "Team Fortress 2", "app_id": "440", "platform": "windows,linux,macos"},
    {"name": "Dota 2", "app_id": "570", "platform": "windows,linux,macos"},
    {"name": "Counter-Strike 2", "app_id": "730", "platform": "windows,linux,macos"},
    {"name": "Unturned", "app_id": "304930", "platform": "windows,linux,macos"}, 
    {"name": "War Thunder", "app_id": "236390", "platform": "windows,linux,macos"},
    {"name": "Path of Exile", "app_id": "238960", "platform": "windows"},
    {"name": "Destiny 2", "app_id": "1085660", "platform": "windows"},
    {"name": "PUBG: BATTLEGROUNDS", "app_id": "578080", "platform": "windows"}
]

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

def run_steamcmd_with_auth(app_id, username="anonymous", password="", steam_guard="", platform="windows"):
    """Run SteamCMD with authentication to download a game"""
    try:
        # Extract app ID if needed
        clean_app_id = extract_app_id(app_id)
        if not clean_app_id:
            yield "⚠️ Invalid app ID. Please enter a numeric Steam app ID or Steam store URL."
            return
            
        app_id = clean_app_id
        logger.info(f"Starting download for App ID: {app_id} on platform: {platform}")
        
        # Check if anonymous login is being used
        is_anonymous = username.lower() == "anonymous"
        if is_anonymous:
            yield f"ℹ️ Using anonymous login. Only free-to-play games can be downloaded this way.\n"
        else:
            yield f"ℹ️ Attempting to login as {username}. Please wait...\n"
            
            # Redact password for security
            if password:
                logger.info(f"Using password (redacted) for user {username}")
            else:
                yield f"⚠️ No password provided for user {username}. Authentication may fail.\n"
        
        # Create output directory
        output_dir = "/app/game"
        os.makedirs(output_dir, exist_ok=True)
            
        # Create the script file
        script_file = create_steam_script(username, password, app_id, output_dir, platform)
        yield f"ℹ️ Created SteamCMD script with platform set to {platform}.\n"
        
        try:
            # Execute SteamCMD with the script
            cmd = ["/app/steamcmd/steamcmd.sh", "+runscript", script_file]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Variables to track Steam Guard request
            needs_steam_guard = False
            
            # Collect output
            output_lines = []
            for line in iter(process.stdout.readline, ''):
                output_lines.append(line.strip())
                if len(output_lines) > 100:  # Keep only last 100 lines
                    output_lines.pop(0)
                logger.info(f"STEAMCMD: {line.strip()}")
                
                # Check for Steam Guard request
                if "Steam Guard code:" in line or "Two-factor code:" in line:
                    needs_steam_guard = True
                    if steam_guard:
                        # Send the provided Steam Guard code
                        process.stdin.write(f"{steam_guard}\n")
                        process.stdin.flush()
                        output_lines.append(f"Submitted Steam Guard code: {steam_guard}")
                    else:
                        output_lines.append("⚠️ Steam Guard code required but not provided!")
                
                # Check for platform error and provide helpful message
                if "Invalid platform" in line:
                    output_lines.append("⚠️ This game doesn't support the selected platform.")
                    output_lines.append("Try changing the platform to 'windows' in the advanced settings.")
                
                yield "\n".join(output_lines)
            
            # Get final exit code
            process.stdout.close()
            return_code = process.wait()
            
            # Check result
            if return_code != 0:
                if "Invalid platform" in "\n".join(output_lines):
                    yield "\n\n⚠️ Download failed: Game not available for the selected platform."
                    yield "Please try again with platform set to 'windows'."
                else:
                    yield f"\n\n⚠️ Download failed with exit code {return_code}"
            else:
                yield "\n\n✅ Download completed successfully!"
                
        finally:
            # Clean up the temporary script file
            if os.path.exists(script_file):
                os.unlink(script_file)
                
    except Exception as e:
        error_msg = f"Error during download: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        yield error_msg

def compress_game_files():
    """Compress downloaded game files using 7zip"""
    try:
        yield "Starting compression of game files..."
        
        # Check if game directory exists and has files
        game_dir = "/app/game"
        if not os.path.exists(game_dir):
            yield "Error: Game directory doesn't exist. Download a game first."
            return
            
        # Check if there are files to compress
        file_count = sum(len(files) for _, _, files in os.walk(game_dir))
        if file_count == 0:
            yield "No files found to compress. Download a game first."
            return
            
        # Create output directory
        output_dir = "/app/output"
        os.makedirs(output_dir, exist_ok=True)
        
        # Get app ID or name from directory if possible
        app_id = "game"
        steamapps_path = os.path.join(game_dir, "steamapps", "appmanifest_*.acf")
        import glob
        manifest_files = glob.glob(steamapps_path)
        if manifest_files:
            # Extract app ID from manifest filename
            manifest_file = os.path.basename(manifest_files[0])
            app_id_match = re.search(r'appmanifest_(\d+).acf', manifest_file)
            if app_id_match:
                app_id = app_id_match.group(1)
        
        # Create timestamp
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_file = os.path.join(output_dir, f"steam_game_{app_id}_{timestamp}.7z")
        
        yield f"Compressing game files from {game_dir}\nOutput file: {output_file}\nThis may take some time..."
        
        # Run 7zip to compress the files
        cmd = [
            "7z", "a",          # Add to archive
            "-t7z",             # 7z format
            "-m0=lzma2",        # LZMA2 method
            "-mx=9",            # Ultra compression
            "-aoa",             # Overwrite all existing files
            output_file,        # Output file
            f"{game_dir}/*"     # Input files
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Show progress
        progress_output = []
        for line in iter(process.stdout.readline, ''):
            progress_output.append(line.strip())
            if len(progress_output) > 20:  # Keep only last 20 lines
                progress_output.pop(0)
            yield "\n".join(progress_output)
        
        # Get result
        process.stdout.close()
        return_code = process.wait()
        
        if return_code != 0:
            yield f"Error: Compression failed with code {return_code}"
            return
            
        # Report success
        size_bytes = os.path.getsize(output_file)
        size_mb = size_bytes / (1024 * 1024)
            
        yield f"Compression completed successfully!\nOutput file: {output_file}\nSize: {size_mb:.2f} MB"
    
    except Exception as e:
        error_msg = f"Error during compression: {str(e)}\n{traceback.format_exc()}"
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
        gr.Markdown("# Steam Game Downloader & Compressor")
        gr.Markdown("Download games from Steam and compress them for easy transfer")
        
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
            gr.Markdown("""
            ## Steam Login & Download
            
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
            
            download_btn = gr.Button("Download Game")
            download_output = gr.Textbox(label="Download Progress", lines=15)
            
            download_btn.click(
                fn=run_steamcmd_with_auth,
                inputs=[app_id, username, password, steam_guard, platform],
                outputs=download_output
            )
        
        with gr.Tab("Compress Files"):
            gr.Markdown("""
            ## Compress Downloaded Game Files
            
            Use this tab to compress downloaded game files using 7zip with maximum compression.
            The compressed file will be stored in the /app/output directory.
            """)
            
            compress_btn = gr.Button("Compress Game Files")
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
                    list_game_btn = gr.Button("List Downloaded Game Files")
                    list_game_btn.click(fn=list_downloaded_files, inputs=None, outputs=game_files_output)
                
                with gr.Column():
                    gr.Markdown("### Compressed Output Files")
                    compressed_files_output = gr.Textbox(label="Compressed Files", lines=20)
                    list_compressed_btn = gr.Button("List Compressed Files")
                    list_compressed_btn.click(fn=list_compressed_files, inputs=None, outputs=compressed_files_output)
    
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
