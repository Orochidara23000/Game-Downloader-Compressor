import os
import subprocess
import time
import re
import logging
import shutil
import signal
import json
import hashlib
from logging.handlers import RotatingFileHandler
from datetime import datetime
from queue import Queue
import threading
import secrets
import dotenv

# Load environment variables from .env file if it exists
dotenv.load_dotenv()

# === Logging Setup with Rotation and Stream Handler ===
log_dir = os.path.join(os.getcwd(), "logs")
try:
    os.makedirs(log_dir, exist_ok=True)
except PermissionError:
    print(f"Warning: Cannot create log directory at {log_dir} - permission denied. Using current directory.")
    log_dir = os.getcwd()

log_filename = os.path.join(log_dir, f'process_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logger = logging.getLogger("SteamCMDLogger")
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()

# Rotating file handler (writes logs to file)
file_handler = RotatingFileHandler(log_filename, maxBytes=10*1024*1024, backupCount=5, delay=False)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Stream handler (writes logs to stdout)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

def log_flush():
    """Flush all log handlers."""
    for h in logger.handlers:
        h.flush()

# === Process Management ===
active_processes = {}

def register_process(process, name):
    """Register a subprocess for proper cleanup during shutdown."""
    process_id = str(process.pid)
    active_processes[process_id] = {
        'process': process,
        'name': name
    }
    return process_id

def cleanup_processes():
    """Terminate all registered processes gracefully."""
    for process_id, process_info in active_processes.items():
        try:
            process = process_info['process']
            if process.poll() is None:  # Process is still running
                logger.info(f"Terminating process: {process_info['name']} (PID: {process_id})")
                process.terminate()
                time.sleep(2)
                if process.poll() is None:  # Still running
                    process.kill()
                    logger.info(f"Force killed process: {process_info['name']}")
        except Exception as e:
            logger.error(f"Error cleaning up process {process_id}: {str(e)}")
    active_processes.clear()

# Register cleanup on exit
def signal_handler(sig, frame):
    logger.info("Shutdown signal received, cleaning up...")
    cleanup_processes()
    log_flush()
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# === Utility Functions ===

def get_available_space(path):
    """Get available disk space in bytes for the given path."""
    try:
        result = subprocess.run(['df', '-k', path], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        if len(lines) > 1:
            return int(lines[1].split()[3]) * 1024
    except Exception as e:
        logger.error(f"Error checking disk space: {str(e)}")
        return 0
    return 0

def verify_output_path(output_path):
    """Verify that the output path is valid and writable."""
    logger.info(f"Verifying output path: {output_path}")
    if not os.path.isabs(output_path):
        msg = "Error: Output path must be absolute."
        logger.error(msg)
        log_flush()
        return msg
    
    parent_dir = os.path.dirname(output_path)
    try:
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            logger.info(f"Created directory: {parent_dir}")
        
        # Check write permissions by creating a test file
        test_file = os.path.join(parent_dir, f'.test_write_{secrets.token_hex(4)}')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        
    except PermissionError:
        msg = f"Error: No write permission for directory: {parent_dir}"
        logger.error(msg)
        log_flush()
        return msg
    except Exception as e:
        msg = f"Error: Could not create or write to directory: {str(e)}"
        logger.error(msg)
        log_flush()
        return msg
    
    msg = "Output path verified successfully."
    logger.info(msg)
    log_flush()
    return msg

def verify_disk_space(min_required_gb=10):
    """Verify that there is sufficient disk space available."""
    logger.info("Verifying disk space...")
    local_available = get_available_space(os.getcwd())
    local_available_gb = local_available/1024**3
    
    msg = f"Available Disk Space: {local_available_gb:.2f} GB"
    if local_available_gb < min_required_gb:
        msg += f" - WARNING: Less than {min_required_gb}GB available, downloads may fail!"
    
    logger.info(msg)
    log_flush()
    return msg

def hash_credentials(username, password):
    """Create a secure hash of credentials for logging purposes."""
    if not username:
        return "anonymous"
    combined = f"{username}:{password}"
    return hashlib.sha256(combined.encode()).hexdigest()[:8]

def verify_steam_login(username, password, steam_guard_code, anonymous=False):
    """Verify Steam login credentials."""
    logger.info(f"Verifying Steam login for {'anonymous' if anonymous else hash_credentials(username, password)}")
    
    steamcmd_path = os.path.join(os.getcwd(), "steamcmd", "steamcmd.sh")
    if not os.path.exists(steamcmd_path):
        msg = "Error: SteamCMD not found. Please install dependencies first."
        logger.error(msg)
        log_flush()
        return msg
    
    if anonymous:
        cmd_login = [steamcmd_path, '+login', 'anonymous', '+quit']
        logger.info("Using anonymous login.")
    else:
        cmd_login = [steamcmd_path]
        if steam_guard_code:
            cmd_login += ['+set_steam_guard_code', steam_guard_code]
        cmd_login += ['+login', username, password, '+quit']
    
    retries = 3
    for attempt in range(retries):
        logger.info(f"Login attempt {attempt+1}")
        try:
            login_process = subprocess.Popen(
                cmd_login, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            register_process(login_process, "steam_login_verification")
            
            try:
                output, error = login_process.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                login_process.kill()
                output, error = login_process.communicate()
                logger.error("Login process timed out after 60 seconds")
                msg = "Error: Login process timed out. Steam servers may be busy."
                continue
                
            if "Waiting for user info...OK" in output:
                time.sleep(5)
                msg = "Steam login verified successfully."
                logger.info(msg)
                log_flush()
                return msg
            else:
                if "Steam Guard" in output or "Two-factor code" in output:
                    msg = "Error: Steam Guard code required or invalid."
                elif "Invalid Password" in output or "Login Failure" in output:
                    msg = "Error: Invalid username or password."
                else:
                    msg = f"Error: Login failed: {output.strip()}"
                logger.error(msg)
                if error:
                    logger.error(f"Error output: {error}")
                log_flush()
                
                if attempt < retries - 1:
                    logger.info("Retrying login...")
                    time.sleep(10)
                else:
                    return msg
        except Exception as e:
            logger.error(f"Exception during login attempt: {str(e)}")
            if attempt < retries - 1:
                logger.info("Retrying login...")
                time.sleep(10)
            else:
                return f"Error: Exception during login: {str(e)}"
    
    return "Error: Failed to verify login after multiple attempts."

def system_check():
    """Perform system checks and return status."""
    messages = []
    messages.append("System Check:")
    
    # Check disk space
    local_space = get_available_space(os.getcwd())
    messages.append(f"Available Disk Space: {local_space/1024**3:.2f} GB")
    if local_space < 10*1024**3:
        messages.append("WARNING: Less than 10GB available disk space!")
    
    # Check steamcmd
    steamcmd_path = os.path.join(os.getcwd(), "steamcmd", "steamcmd.sh")
    if os.path.exists(steamcmd_path):
        messages.append("steamcmd found.")
        if os.access(steamcmd_path, os.X_OK):
            messages.append("steamcmd is executable.")
        else:
            messages.append("WARNING: steamcmd is not executable! Run: chmod +x ./steamcmd/steamcmd.sh")
    else:
        messages.append("ERROR: steamcmd not found in ./steamcmd")
    
    # Check 7z
    if shutil.which("7z"):
        messages.append("7z found.")
        try:
            result = subprocess.run(['7z', '--help'], capture_output=True, text=True)
            if result.returncode == 0:
                messages.append("7z is working correctly.")
            else:
                messages.append("WARNING: 7z installation may have issues.")
        except Exception:
            messages.append("WARNING: 7z is installed but may not be working correctly.")
    else:
        messages.append("ERROR: 7z not found.")
    
    # Check for write permissions
    try:
        test_dirs = ["./logs", "./output", "./game"]
        for d in test_dirs:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
            test_file = os.path.join(d, f".write_test_{secrets.token_hex(4)}")
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        messages.append("Write permissions verified for all required directories.")
    except Exception as e:
        messages.append(f"ERROR: Write permission issue: {str(e)}")
    
    return "\n".join(messages)

def estimate_game_size(app_id, steamcmd_path):
    """Estimate the size of a game before downloading."""
    logger.info(f"Estimating game size for app id {app_id}")
    if not os.path.exists(steamcmd_path):
        msg = "Error: SteamCMD not found."
        logger.error(msg)
        return msg, None
    
    try:
        cmd = [steamcmd_path, '+app_info_update', '1', '+app_info_print', app_id, '+quit']
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        register_process(process, f"estimate_size_{app_id}")
        
        try:
            output, error = process.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            process.kill()
            output, error = process.communicate()
            msg = "Error: SteamCMD timed out while retrieving app info."
            logger.error(msg)
            return msg, None
            
        match = re.search(r'"SizeOnDisk"\s+"(\d+)"', output)
        if not match:
            match = re.search(r'"size"\s+"(\d+)"', output)
            
        if match:
            size_bytes = int(match.group(1))
            estimated_gb = size_bytes / 1024**3
            msg = f"Estimated game size: {estimated_gb:.2f} GB"
            logger.info(msg)
            
            available_space = get_available_space(os.getcwd())
            if available_space < size_bytes * 1.5:
                warning = f"WARNING: Available space ({available_space/1024**3:.2f} GB) may not be sufficient for this game ({estimated_gb:.2f} GB) plus overhead."
                logger.warning(warning)
                msg += f"\n{warning}"
                
            return msg, size_bytes
        else:
            msg = "Could not determine game size. Proceeding without size estimation."
            logger.warning(msg)
            return msg, None
    except Exception as e:
        msg = f"Error estimating game size: {str(e)}"
        logger.error(msg)
        return msg, None

def download_and_compress(username, password, steam_guard_code, app_id, output_path, anonymous=False, resume=False):
    """Download and compress a game using SteamCMD."""
    credentials_hash = "anonymous" if anonymous else hash_credentials(username, password)
    logger.info(f"Starting download and compression process for user {credentials_hash}, App ID: {app_id}, Output: {output_path}")
    log_flush()

    # Verify output path
    msg = verify_output_path(output_path)
    if "Error" in msg:
        return "", msg

    # Check disk space
    local_available = get_available_space(os.getcwd())
    if local_available < 10*1024**3:
        warning = "Warning: Less than 10GB available on disk. Download may fail."
        logger.warning(warning)
        
    # Prepare game directory
    if not resume:
        if os.path.exists("./game"):
            try:
                shutil.rmtree("./game")
            except Exception as e:
                error_msg = f"Error cleaning up game directory: {str(e)}"
                logger.error(error_msg)
                return "", error_msg
    
    try:
        if not os.path.exists("./game"):
            os.makedirs("./game")
    except Exception as e:
        error_msg = f"Error creating game directory: {str(e)}"
        logger.error(error_msg)
        return "", error_msg

    # Locate steamcmd
    steamcmd_path = os.path.join(os.getcwd(), "steamcmd", "steamcmd.sh")
    if not os.path.exists(steamcmd_path):
        error_msg = "Error: SteamCMD not found."
        logger.error(error_msg)
        return "", error_msg

    # Login to Steam
    if anonymous:
        cmd_login = [steamcmd_path, '+login', 'anonymous', '+quit']
        logger.info("Using anonymous login for download.")
    else:
        cmd_login = [steamcmd_path]
        if steam_guard_code:
            cmd_login += ['+set_steam_guard_code', steam_guard_code]
        cmd_login += ['+login', username, password, '+quit']
        
    logger.info('Attempting to log in...')
    log_flush()
    
    try:
        login_process = subprocess.Popen(
            cmd_login, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        register_process(login_process, f"steam_login_{app_id}")
        
        try:
            output_login, error_login = login_process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            login_process.kill()
            output_login, error_login = login_process.communicate()
            error_msg = "Login process timed out. Steam servers may be busy."
            logger.error(error_msg)
            log_flush()
            return "", error_msg
            
        logger.info(f"Login output: {output_login}")
        if error_login:
            logger.error(f"Login error: {error_login}")
        log_flush()
        
        if "Waiting for user info...OK" not in output_login:
            if "Steam Guard" in output_login or "Two-factor code" in output_login:
                error_msg = "Steam Guard code required or invalid. Check your email or authenticator."
            elif "Invalid Password" in output_login or "Login Failure" in output_login:
                error_msg = "Invalid username or password."
            else:
                error_msg = f"Login failed: {output_login.strip()}"
            logger.error(error_msg)
            log_flush()
            return "", error_msg
            
        time.sleep(5)
        status_messages = ["Login successful."]
        logger.info("Login successful.")
        log_flush()
    except Exception as e:
        error_msg = f"Exception during login: {str(e)}"
        logger.error(error_msg)
        log_flush()
        return "", error_msg

    # Update app info
    try:
        max_attempts = 3
        app_info_updated = False
        
        for attempt in range(max_attempts):
            logger.info(f"Attempt {attempt+1} to update AppInfo...")
            update_proc = subprocess.Popen(
                [steamcmd_path, '+app_info_update', '1', '+quit'], 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            register_process(update_proc, f"update_app_info_{app_id}")
            
            try:
                update_output, update_error = update_proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                update_proc.kill()
                update_output, update_error = update_proc.communicate()
                logger.warning("AppInfo update timed out, retrying...")
                continue
                
            logger.info(f"AppInfo update output: {update_output}")
            if update_error:
                logger.warning(f"AppInfo update error: {update_error}")
                
            if "Failed to request AppInfo update" not in update_output:
                logger.info("AppInfo update successful.")
                app_info_updated = True
                break
            else:
                logger.warning("AppInfo update failed, retrying...")
                log_flush()
                time.sleep(5)
                
        if not app_info_updated:
            logger.warning("Could not update AppInfo after multiple attempts, proceeding anyway.")
    except Exception as e:
        logger.error(f"Exception during AppInfo update: {str(e)}")
    
    # Download game
    cmd_download = [
        steamcmd_path,
        '+force_install_dir', './game',
        '+app_update', app_id, 'validate',
        '+quit'
    ]
    logger.info('Starting download...')
    log_flush()
    
    try:
        process_download = subprocess.Popen(
            cmd_download,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        register_process(process_download, f"download_{app_id}")
        
        download_start_time = time.time()
        status_messages = []
        
        # Process stdout
        for line in process_download.stdout:
            if '%' in line:
                try:
                    progress_match = re.search(r'(\d+)%', line)
                    if progress_match:
                        progress = int(progress_match.group(1))
                        elapsed_time = time.time() - download_start_time
                        if progress > 0:
                            total_time_est = elapsed_time / (progress / 100)
                            remaining_time = total_time_est - elapsed_time
                            minutes, seconds = divmod(int(remaining_time), 60)
                            hours, minutes = divmod(minutes, 60)
                            
                            time_remaining = ""
                            if hours > 0:
                                time_remaining = f"~{hours}h {minutes}m remaining"
                            else:
                                time_remaining = f"~{minutes}m {seconds}s remaining"
                                
                            status = f"Downloading: {progress}% complete, {time_remaining}"
                            status_messages.append(status)
                            logger.info(status)
                            log_flush()
                        else:
                            status_messages.append(line.strip())
                            logger.info(line.strip())
                            log_flush()
                except Exception as e:
                    logger.warning(f"Failed to parse download progress: {line.strip()}, error: {str(e)}")
                    status_messages.append(line.strip())
                    log_flush()
            else:
                status_messages.append(line.strip())
                logger.info(f"Download output: {line.strip()}")
                log_flush()
                
        process_download.wait()
        
        if process_download.returncode != 0:
            error_output = ""
            for line in process_download.stderr:
                error_output += line
                logger.error(f"Download error: {line.strip()}")
                
            logger.error(f"Download failed with code {process_download.returncode}")
            log_flush()
            return "\n".join(status_messages), f"Download failed with code {process_download.returncode}: {error_output}"
    except Exception as e:
        error_msg = f"Exception during download: {str(e)}"
        logger.error(error_msg)
        log_flush()
        return "\n".join(status_messages) if status_messages else "", error_msg

    # Compression
    logger.info('Starting compression...')
    status_messages.append('Starting compression...')
    log_flush()
    
    try:
        cmd_compress = ['7z', 'a', '-t7z', '-v4g', output_path, './game']
        process_compress = subprocess.Popen(
            cmd_compress,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        register_process(process_compress, f"compress_{app_id}")
        
        compress_start_time = time.time()
        
        # Process stdout
        for line in process_compress.stdout:
            if '%' in line:
                try:
                    progress_match = re.search(r'(\d+)%', line)
                    if progress_match:
                        progress = int(progress_match.group(1))
                        elapsed_time = time.time() - compress_start_time
                        if progress > 0:
                            total_time_est = elapsed_time / (progress / 100)
                            remaining_time = total_time_est - elapsed_time
                            minutes, seconds = divmod(int(remaining_time), 60)
                            hours, minutes = divmod(minutes, 60)
                            
                            time_remaining = ""
                            if hours > 0:
                                time_remaining = f"~{hours}h {minutes}m remaining"
                            else:
                                time_remaining = f"~{minutes}m {seconds}s remaining"
                                
                            status = f"Compressing: {progress}% complete, {time_remaining}"
                            status_messages.append(status)
                            logger.info(status)
                            log_flush()
                        else:
                            status_messages.append(line.strip())
                            logger.info(line.strip())
                            log_flush()
                except Exception as e:
                    logger.warning(f"Failed to parse compression progress: {line.strip()}, error: {str(e)}")
                    status_messages.append(line.strip())
                    log_flush()
            else:
                status_messages.append(line.strip())
                logger.info(f"Compression output: {line.strip()}")
                log_flush()
                
        process_compress.wait()
        
        if process_compress.returncode != 0:
            error_output = ""
            for line in process_compress.stderr:
                error_output += line
                logger.error(f"Compression error: {line.strip()}")
                
            logger.error(f"Compression failed with code {process_compress.returncode}")
            log_flush()
            return "\n".join(status_messages), f"Compression failed with code {process_compress.returncode}: {error_output}"
    except Exception as e:
        error_msg = f"Exception during compression: {str(e)}"
        logger.error(error_msg)
        log_flush()
        return "\n".join(status_messages), error_msg

    # Cleanup
    try:
        shutil.rmtree("./game", ignore_errors=True)
    except Exception as e:
        logger.warning(f"Failed to clean up game directory: {str(e)}")
        
    completion_msg = f"Completed! Files saved as {output_path}.001, {output_path}.002, etc."
    logger.info(completion_msg)
    log_flush()
    return "\n".join(status_messages) + "\n" + completion_msg, ""

def download_and_compress_from_url(username, password, steam_guard_code, anonymous, steam_url, output_path, resume=False):
    """Extract app ID from URL and start download process."""
    logger.info(f"Extracting app ID from URL: {steam_url}")
    match = re.search(r"/app/(\d+)", steam_url)
    if not match:
        error_msg = "Error: Could not extract App ID from Steam URL."
        logger.error(error_msg)
        log_flush()
        return "", error_msg
        
    app_id = match.group(1)
    logger.info(f"Extracted App ID: {app_id}")
    log_flush()
    
    # Save metadata about this download
    try:
        metadata = {
            "app_id": app_id,
            "steam_url": steam_url,
            "timestamp": datetime.now().isoformat(),
            "output_path": output_path,
            "user": "anonymous" if anonymous else hash_credentials(username, password)
        }
        metadata_dir = os.path.join(os.path.dirname(output_path), ".metadata")
        os.makedirs(metadata_dir, exist_ok=True)
        with open(os.path.join(metadata_dir, f"{app_id}.json"), 'w') as f:
            json.dump(metadata, f)
    except Exception as e:
        logger.warning(f"Failed to save metadata: {str(e)}")
    
    # Check game size
    size_msg, size_bytes = estimate_game_size(app_id, os.path.join(os.getcwd(), "steamcmd", "steamcmd.sh"))
    status_messages = [size_msg]
    
    # If we have size estimate, verify disk space
    if size_bytes:
        available_space = get_available_space(os.getcwd())
        required_space = size_bytes * 1.5  # 50% buffer for installation and compression
        if available_space < required_space:
            warning = f"WARNING: Available space ({available_space/1024**3:.2f} GB) may not be sufficient for this game ({size_bytes/1024**3:.2f} GB) plus overhead."
            logger.warning(warning)
            status_messages.append(warning)
    
    # Start download process
    status, error = download_and_compress(username, password, steam_guard_code, app_id, output_path, anonymous, resume)
    if status:
        status_messages.append(status)
    return "\n".join(status_messages), error

# === Queue Management ===

download_queue = Queue()
queue_status = []
queue_lock = threading.Lock()  # Add lock for thread safety

def process_queue():
    """Background thread to process the download queue."""
    while True:
        task = download_queue.get()
        task_id = task.get('id', 'unknown')
        
        with queue_lock:
            queue_status.append(f"Processing download task {task_id} for {task['steam_url']}")
        
        logger.info(f"Starting download task {task_id} from queue")
        try:
            status, error = download_and_compress_from_url(
                task['username'], task['password'], task['steam_guard_code'],
                task['anonymous'], task['steam_url'], task['output_path'], task['resume']
            )
            
            result = "Completed" if not error else f"Failed: {error}"
            with queue_lock:
                queue_status.append(f"Task {task_id} {result}")
                if len(queue_status) > 100:
                    queue_status.pop(0)
                    
            logger.info(f"Download task {task_id} completed with status: {result}")
        except Exception as e:
            with queue_lock:
                queue_status.append(f"Task {task_id} failed with exception: {str(e)}")
                if len(queue_status) > 100:
                    queue_status.pop(0)
            logger.error(f"Exception in download task {task_id}: {str(e)}")
        finally:
            download_queue.task_done()

# Start queue processing thread
queue_thread = threading.Thread(target=process_queue, daemon=True)
queue_thread.start()

def add_to_queue(username, password, steam_guard_code, anonymous, steam_url, output_path, resume):
    """Add a download task to the queue."""
    task_id = secrets.token_hex(4)
    task = {
        'id': task_id,
        'username': username,
        'password': password,
        'steam_guard_code': steam_guard_code,
        'anonymous': anonymous,
        'steam_url': steam_url,
        'output_path': output_path,
        'resume': resume,
        'timestamp': datetime.now().isoformat()
    }
    download_queue.put(task)
    
    # Save task metadata to .queue directory (if needed)
    try:
        queue_dir = os.path.join(os.getcwd(), ".queue")
        os.makedirs(queue_dir, exist_ok=True)
        # Save public task info (no credentials)
        public_task = {
            'id': task_id,
            'anonymous': anonymous,
            'steam_url': steam_url,
            'output_path': output_path,
            'resume': resume,
            'timestamp': task['timestamp'],
            'status': 'queued'
        }
        with open(os.path.join(queue_dir, f"{task_id}.json"), 'w') as f:
            json.dump(public_task, f)
        logger.info(f"Added task {task_id} to download queue")
        with queue_lock:
            queue_status.append(f"Task {task_id} for {steam_url} added to queue")
            if len(queue_status) > 100:
                queue_status.pop(0)
    except Exception as e:
        logger.error(f"Failed to save queue task: {str(e)}")
    return task_id

def get_queue_status():
    """Get current queue status."""
    with queue_lock:
        return list(queue_status)

def get_queue_length():
    """Get the number of tasks in the queue."""
    return download_queue.qsize()

def load_queue_tasks():
    """Load previously saved queue tasks at startup."""
    try:
        queue_dir = os.path.join(os.getcwd(), ".queue")
        if not os.path.exists(queue_dir):
            logger.info("No saved queue found")
            return
        task_files = [f for f in os.listdir(queue_dir) if f.endswith('.json')]
        tasks_loaded = 0
        for task_file in task_files:
            try:
                task_id = task_file.split('.')[0]
                with open(os.path.join(queue_dir, task_file), 'r') as f:
                    task = json.load(f)
                if task.get('status') in ['completed', 'failed']:
                    continue
                # For non-anonymous tasks, credentials loading would be added here if needed
                add_to_queue(
                    "", "", "",  # Credentials placeholders for anonymous tasks
                    task['anonymous'], task['steam_url'], task['output_path'], task.get('resume', False)
                )
                tasks_loaded += 1
            except Exception as e:
                logger.error(f"Failed to load queue task {task_file}: {str(e)}")
        logger.info(f"Loaded {tasks_loaded} tasks from queue")
    except Exception as e:
        logger.error(f"Failed to load queue: {str(e)}")

# Load queue tasks at startup
try:
    load_queue_tasks()
except Exception as e:
    logger.error(f"Failed to load queue tasks at startup: {str(e)}")

def get_downloaded_files(output_path=None):
    """
    Return a list of downloaded file parts or the main file if parts are not found.
    If no output_path is provided, defaults to "./output/game.7z".
    """
    if not output_path:
        output_path = os.path.join(os.getcwd(), "output", "game.7z")
    base = output_path
    files = []
    i = 1
    while True:
        part_file = f"{base}.{str(i).zfill(3)}"
        if os.path.exists(part_file):
            files.append(part_file)
            i += 1
        else:
            break
    if not files and os.path.exists(output_path):
        files.append(output_path)
    return "\n".join(files) if files else "No downloaded files found."
