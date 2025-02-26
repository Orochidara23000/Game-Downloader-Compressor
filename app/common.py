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
    path = os.path.abspath(path)  # Ensure absolute path
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
    output_path = os.path.abspath(output_path)  # Ensure absolute path
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
    
    # Check for steamcmd in multiple locations
    steamcmd_paths = [
        os.path.join(os.getcwd(), "steamcmd", "steamcmd.sh"),
        "/app/steamcmd/steamcmd.sh",
        "/usr/local/bin/steamcmd",
        shutil.which("steamcmd")
    ]
    
    messages.append("Checking for steamcmd in multiple locations:")
    found_steamcmd = False
    
    for path in steamcmd_paths:
        if path and os.path.exists(path):
            messages.append(f"steamcmd found at: {path}")
            found_steamcmd = True
            if os.access(path, os.X_OK):
                messages.append(f"steamcmd at {path} is executable.")
            else:
                messages.append(f"WARNING: steamcmd at {path} is not executable. Fixing permissions...")
                try:
                    os.chmod(path, 0o755)
                    messages.append(f"Permissions fixed for {path}")
                except Exception as e:
                    messages.append(f"Failed to fix permissions: {str(e)}")
    
    if not found_steamcmd:
        messages.append("ERROR: steamcmd not found in any expected location.")
        # Try to find it anywhere on the system
        try:
            result = subprocess.run(['find', '/', '-name', 'steamcmd.sh', '-type', 'f'], 
                                   capture_output=True, text=True, timeout=10)
            if result.stdout:
                messages.append(f"Potential steamcmd locations: {result.stdout.strip()}")
                # Try to create a symlink to the first found location
                first_found = result.stdout.strip().split('\n')[0]
                try:
                    os.symlink(first_found, '/usr/local/bin/steamcmd')
                    messages.append(f"Created symlink from {first_found} to /usr/local/bin/steamcmd")
                except Exception as e:
                    messages.append(f"Failed to create symlink: {str(e)}")
        except Exception as e:
            messages.append(f"Failed to search for steamcmd: {str(e)}")
        
        # If not found, install it
        try:
            messages.append("Attempting to install SteamCMD...")
            install_cmd = ["bash", "./install_dependencies.sh"]
            result = subprocess.run(install_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                messages.append("SteamCMD installation may have been successful. Please restart the application.")
            else:
                messages.append(f"SteamCMD installation failed: {result.stderr}")
        except Exception as e:
            messages.append(f"Failed to install SteamCMD: {str(e)}")
    
    # Check for 7z in multiple locations
    sevenzip_paths = ['/usr/bin/7z', '/bin/7z', '/usr/local/bin/7z', shutil.which("7z")]
    messages.append("Checking for 7z in multiple locations:")
    found_7z = False
    
    for path in sevenzip_paths:
        if path and os.path.exists(path):
            messages.append(f"7z found at: {path}")
            found_7z = True
            break
    
    if found_7z:
        try:
            result = subprocess.run(['7z', '--help'], capture_output=True, text=True)
            if result.returncode == 0:
                messages.append("7z is working correctly.")
            else:
                messages.append(f"WARNING: 7z is installed but returned code {result.returncode}.")
                messages.append(f"Error output: {result.stderr}")
        except Exception as e:
            messages.append(f"WARNING: 7z check failed with exception: {str(e)}")
    else:
        messages.append("ERROR: 7z not found in any expected location.")
        # Try to install 7zip if not found
        try:
            messages.append("Attempting to install 7zip...")
            result = subprocess.run(['apt-get', 'update'], capture_output=True, text=True)
            install_result = subprocess.run(['apt-get', 'install', '-y', 'p7zip-full'], 
                                           capture_output=True, text=True)
            if install_result.returncode == 0:
                messages.append("7zip installation successful.")
                if shutil.which("7z"):
                    messages.append(f"7z now found at: {shutil.which('7z')}")
            else:
                messages.append(f"7zip installation failed: {install_result.stderr}")
        except Exception as e:
            messages.append(f"Failed to install 7zip: {str(e)}")
    
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
