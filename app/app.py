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
import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("__main__")

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
        # Use a secure way to pass credentials - don't include password in script
        script_content += f"login {username}\n"
    
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

# Add this new function to parse download progress from SteamCMD output
def parse_download_progress(line):
    """Parse SteamCMD download progress from output line"""
    try:
        # Match the common progress pattern: progress: 28.27 (13623313183 / 48195266730)
        progress_match = re.search(r'progress: ([0-9.]+) \((\d+) / (\d+)\)', line)
        if progress_match:
            percentage = float(progress_match.group(1))
            downloaded = int(progress_match.group(2))
            total_size = int(progress_match.group(3))
            return {
                'percentage': percentage,
                'downloaded': downloaded,
                'total_size': total_size,
                'valid': True
            }
        return {'valid': False}
    except Exception as e:
        logger.error(f"Error parsing progress: {str(e)}")
        return {'valid': False}

# Format size for human reading
def format_size(size_bytes):
    """Format bytes into human-readable size"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.2f} MB"
    else:
        return f"{size_bytes/1024**3:.2f} GB"

# Format time for human reading
def format_time(seconds):
    """Format seconds into human-readable time"""
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        minutes = (seconds % 3600) / 60
        return f"{hours:.1f} hours {minutes:.0f} minutes"

def run_steamcmd_with_auth(app_id, username="anonymous", password="", steam_guard="", platform="windows", validate=True, max_downloads=16):
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
            logger.info("Using anonymous login")
            yield f"ℹ️ Using anonymous login. Only free-to-play games can be downloaded this way.\n"
        else:
            logger.info(f"Attempting to login as {username}")
            yield f"ℹ️ Attempting to login as {username}. Please wait...\n"
            
        # Create output directory
        output_dir = "/app/game"
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Download directory: {output_dir}")
        
        # For non-anonymous login, we'll use direct command line arguments
        if is_anonymous:
            # Create a script file for anonymous login with optimized settings
            script_content = f"""@ShutdownOnFailedCommand 1
@NoPromptForPassword 1
force_install_dir {output_dir}
login anonymous
"""
            # Add download optimization commands
            script_content += f"@MaxDownloads {max_downloads}\n"  # Increase max concurrent downloads
            script_content += f"@MaxServersPerDomain 10\n"       # Increase max servers per domain
            script_content += f"@LowViolence 0\n"                # Ensure no content restrictions
            script_content += f"@AllowDownloadDuringPlay 1\n"    # Allow background downloads
            
            if platform.lower() != "linux":
                script_content += f"@sSteamCmdForcePlatformType {platform}\n"
                
            # Add app update command with or without validation
            validate_param = "validate" if validate else ""
            script_content += f"app_update {app_id} {validate_param}\n"
            script_content += "quit\n"
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w') as f:
                f.write(script_content)
                script_file = f.name
                
            logger.info(f"Created optimized SteamCMD script file: {script_file}")
            yield f"ℹ️ Created optimized download script with {'validation' if validate else 'faster downloads (no validation)'}.\n"
            
            # Execute SteamCMD with the script
            cmd = ["/app/steamcmd/steamcmd.sh", "+runscript", script_file]
        else:
            # For authenticated login, pass credentials directly with optimized settings
            cmd = [
                "/app/steamcmd/steamcmd.sh",
                "+force_install_dir", output_dir,
                "+@MaxDownloads", str(max_downloads),
                "+@MaxServersPerDomain", "10",
                "+@LowViolence", "0",
                "+@AllowDownloadDuringPlay", "1"
            ]
            
            # Add platform setting if needed
            if platform.lower() != "linux":
                cmd.extend(["+@sSteamCmdForcePlatformType", platform])
                
            # Add login credentials
            if steam_guard:
                cmd.extend(["+login", username, password, steam_guard])
            else:
                cmd.extend(["+login", username, password])
                
            # Add app update command and quit
            validate_param = "validate" if validate else ""
            if validate_param:
                cmd.extend(["+app_update", app_id, validate_param, "+quit"])
            else:
                cmd.extend(["+app_update", app_id, "+quit"])
            
            logger.info(f"Using optimized direct command line for authenticated login")
            yield f"ℹ️ Using optimized download settings with {'validation' if validate else 'faster downloads (no validation)'}.\n"
        
        # Log the command being executed (without credentials for security)
        sanitized_cmd = cmd.copy()
        if not is_anonymous and len(sanitized_cmd) > 5:
            # Redact password in logs
            password_index = sanitized_cmd.index("+login") + 2
            if password_index < len(sanitized_cmd):
                sanitized_cmd[password_index] = "******"
        
        logger.info(f"Executing SteamCMD command: {' '.join(str(c) for c in sanitized_cmd)}")
        
        try:
            # Add periodic status updates
            download_start_time = time.time()
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Variables to track progress
            download_history = []
            last_download_bytes = 0
            last_download_time = time.time()
            current_speed = 0
            
            # Create a visual progress indicator
            progress_indicator = "\n[" + " " * 50 + "] 0%"
            eta_text = ""
            
            # Collect output
            output_lines = []
            line_count = 0
            for line in iter(process.stdout.readline, ''):
                # Skip lines that might contain credentials
                if username.lower() != "anonymous" and username in line and "password" in line.lower():
                    continue
                    
                line_count += 1
                
                # Process the line for download progress
                progress_data = parse_download_progress(line)
                if progress_data['valid']:
                    current_time = time.time()
                    current_bytes = progress_data['downloaded']
                    total_bytes = progress_data['total_size']
                    percentage = progress_data['percentage']
                    
                    # Calculate download speed
                    time_diff = current_time - last_download_time
                    if time_diff >= 1.0:  # Update speed calculation at least once per second
                        bytes_diff = current_bytes - last_download_bytes
                        if bytes_diff > 0:
                            current_speed = bytes_diff / time_diff
                            
                            # Add to download history (keep last 10 readings)
                            download_history.append(current_speed)
                            if len(download_history) > 10:
                                download_history.pop(0)
                                
                            # Calculate average speed over the last few readings
                            avg_speed = sum(download_history) / len(download_history)
                            
                            # Calculate ETA
                            remaining_bytes = total_bytes - current_bytes
                            if avg_speed > 0:
                                eta_seconds = remaining_bytes / avg_speed
                                eta_text = f"ETA: {format_time(eta_seconds)}"
                            
                            # Update for next calculation
                            last_download_bytes = current_bytes
                            last_download_time = current_time
                    
                    # Create a visual progress bar (50 characters wide)
                    progress_chars = int(percentage / 2)
                    progress_bar = "[" + "=" * progress_chars + " " * (50 - progress_chars) + f"] {percentage:.2f}%"
                    
                    # Create a detailed progress line
                    progress_details = f"Downloaded: {format_size(current_bytes)} of {format_size(total_bytes)}"
                    speed_text = f"Speed: {format_size(current_speed)}/s"
                    
                    # Combine into a progress indicator with multiple lines
                    progress_indicator = f"\n{progress_bar}\n{progress_details}\n{speed_text}\n{eta_text}"
                    
                    # Log progress occasionally
                    elapsed_time = time.time() - download_start_time
                    if line_count % 20 == 0:
                        logger.info(
                            f"Download progress: {percentage:.2f}% - "
                            f"{format_size(current_bytes)}/{format_size(total_bytes)} - "
                            f"Speed: {format_size(current_speed)}/s - {eta_text}"
                        )
                
                # Add the line to output, but keep the length manageable
                output_lines.append(line.strip())
                if len(output_lines) > 20:  # Keep fewer lines to make room for progress indicator
                    output_lines.pop(0)
                
                # Log progress indicators
                if "Update state" in line or "%" in line:
                    logger.info(f"Download progress update: {line.strip()}")
                
                # Yield the combined output with progress indicator
                yield "\n".join(output_lines) + progress_indicator
            
            # Get final exit code
            process.stdout.close()
            return_code = process.wait()
            
            # Log completion
            download_duration = time.time() - download_start_time
            logger.info(f"Download process completed with code {return_code} after {download_duration:.1f} seconds")
            
            # Check result
            if return_code != 0:
                if return_code == 5:
                    logger.error(f"Authentication failed for user: {username} (Exit code 5)")
                    yield "\n\n⚠️ Authentication failed. Please check your username and password."
                    yield "If you're using Steam Guard, make sure to enter the correct code."
                elif "Invalid platform" in "\n".join(output_lines):
                    logger.error(f"Download failed: Game not available for platform: {platform}")
                    yield "\n\n⚠️ Download failed: Game not available for the selected platform."
                    yield "Please try again with platform set to 'windows'."
                else:
                    logger.error(f"Download failed with exit code {return_code}")
                    yield f"\n\n⚠️ Download failed with exit code {return_code}"
            else:
                logger.info(f"Download successful for App ID: {app_id}")
                
                # Show download stats in success message
                download_time_formatted = format_time(download_duration)
                completed_msg = (
                    f"\n\n✅ Download completed successfully!\n"
                    f"Total download time: {download_time_formatted}\n"
                    f"Average speed: {format_size(last_download_bytes / max(1, download_duration))}/s"
                )
                yield completed_msg
                
        finally:
            # Clean up the temporary script file if it exists
            if not is_anonymous:
                logger.info("No script file to clean up (using direct authentication)")
            elif 'script_file' in locals() and os.path.exists(script_file):
                os.unlink(script_file)
                logger.info(f"Cleaned up script file: {script_file}")
                
    except Exception as e:
        error_msg = f"Error during download: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        yield error_msg

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

def list_files_for_download():
    output_dir = '/app/output'
    files = os.listdir(output_dir)
    base_url = "http://your-railway-app-url/download/"  # Replace with your actual Railway app URL
    links = [f"{base_url}{file}" for file in files]
    return "\n".join(links)

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
                    
                    validate = gr.Checkbox(
                        label="Validate Files", 
                        value=True,
                        info="Uncheck for faster downloads but less reliability"
                    )
                    
                    max_downloads = gr.Slider(
                        label="Max Concurrent Downloads",
                        minimum=4,
                        maximum=32,
                        value=16,
                        step=4,
                        info="Higher values may increase download speed"
                    )
            
            download_btn = gr.Button("⬇️ Download Game")
            download_output = gr.Textbox(label="Download Progress", lines=15)
            
            download_btn.click(
                fn=run_steamcmd_with_auth,
                inputs=[app_id, username, password, steam_guard, platform, validate, max_downloads],
                outputs=download_output
            )
        
        with gr.Tab("File Browser"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Downloaded Game Files")
                    game_files_output = gr.Textbox(label="Game Files", lines=20)
                    list_game_btn = gr.Button("📂 List Downloaded Game Files")
                    list_game_btn.click(fn=list_downloaded_files, inputs=None, outputs=game_files_output)
                
                # Remove or comment out the File Browser tab related to compressed files
                # with gr.Column():
                #     gr.Markdown("### Compressed Output Files")
                #     compressed_files_output = gr.Textbox(label="Compressed Files", lines=20)
                #     list_compressed_btn = gr.Button("📂 List Compressed Files")
                #     list_compressed_btn.click(fn=list_compressed_files, inputs=None, outputs=compressed_files_output)
        
        with gr.Tab("Download Links"):
            download_links_output = gr.Textbox(label="Download Links", lines=10)
            list_files_btn = gr.Button("List Download Links")
            list_files_btn.click(fn=list_files_for_download, inputs=None, outputs=download_links_output)
        
        # Remove or comment out the Download Files tab
        # with gr.Tab("Download Files"):
        #     gr.Markdown("""
        #     ## 💾 Download Compressed Files
        #     
        #     Select and download the compressed game files you've created.
        #     Files are listed in order of creation with the newest first.
        #     """)
        #     
        #     file_list = get_compressed_file_list()
        #     
        #     if file_list:
        #         file_dropdown = gr.Dropdown(
        #             label="Select File to Download",
        #             choices=file_list,
        #             value=file_list[0] if file_list else None
        #         )
        #         
        #         refresh_files_btn = gr.Button("Refresh File List")
        #         download_file_btn = gr.Button("Download Selected File")
        #         
        #         file_info = gr.Markdown(get_download_links())
        #         
        #         file_output = gr.File(label="Download File")
        #         
        #         # Functions for the download tab
        #         refresh_files_btn.click(
        #             fn=lambda: gr.Dropdown(choices=get_compressed_file_list()),
        #             inputs=None,
        #             outputs=file_dropdown
        #         )
        #         
        #         refresh_files_btn.click(
        #             fn=get_download_links,
        #             inputs=None,
        #             outputs=file_info
        #         )
        #         
        #         download_file_btn.click(
        #             fn=get_file_for_download,
        #             inputs=file_dropdown,
        #             outputs=file_output
        #         )
        #     else:
        #         gr.Markdown("### No compressed files available yet")
        #         gr.Markdown("Use the Download Game tab to download a game, then compress it in the Compress Files tab.")
    
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
