import os
import subprocess
import time
import re
import logging
import shutil
from datetime import datetime
from queue import Queue
import threading

# === Logging Setup ===
log_dir = os.path.join(os.getcwd(), "logs")
os.makedirs(log_dir, exist_ok=True)
log_filename = os.path.join(log_dir, f'process_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logger = logging.getLogger("SteamCMDLogger")
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
handler = logging.FileHandler(log_filename, mode='a', delay=False)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def log_flush():
    for h in logger.handlers:
        h.flush()

# === Utility Functions ===

def get_available_space(path):
    result = subprocess.run(['df', '-k', path], capture_output=True, text=True)
    lines = result.stdout.splitlines()
    if len(lines) > 1:
        return int(lines[1].split()[3]) * 1024
    return 0

def verify_output_path(output_path):
    logger.info("Verifying output path...")
    if not os.path.isabs(output_path):
        msg = "Error: Output path must be absolute."
        logger.error(msg)
        log_flush()
        return msg
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    except Exception as e:
        msg = f"Error: Could not create directory: {str(e)}"
        logger.error(msg)
        log_flush()
        return msg
    msg = "Output path verified successfully."
    logger.info(msg)
    log_flush()
    return msg

def verify_disk_space(dummy=None):
    logger.info("Verifying disk space...")
    local_available = get_available_space(os.getcwd())
    msg = f"Available Disk Space: {local_available/1024**3:.2f} GB"
    logger.info(msg)
    log_flush()
    return msg

def verify_steam_login(username, password, steam_guard_code, anonymous=False):
    logger.info("Verifying Steam login...")
    steamcmd_path = os.path.join(os.getcwd(), "steamcmd", "steamcmd.sh")
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
        login_process = subprocess.run(cmd_login, capture_output=True, text=True)
        output = login_process.stdout
        logger.info(f"Login output: {output}")
        log_flush()
        if "Waiting for user info...OK" in output:
            time.sleep(20)
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
            log_flush()
            if attempt < retries - 1:
                logger.info("Retrying login...")
                time.sleep(10)
            else:
                return msg

def system_check():
    messages = []
    messages.append("System Check:")
    local_space = get_available_space(os.getcwd())
    messages.append(f"Available Disk Space: {local_space/1024**3:.2f} GB")
    steamcmd_path = os.path.join(os.getcwd(), "steamcmd", "steamcmd.sh")
    if os.path.exists(steamcmd_path):
        messages.append("steamcmd found.")
    else:
        messages.append("steamcmd not found in ./steamcmd")
    # Since LocalXpose is installed globally via npm as "loclx", check its availability:
    try:
        subprocess.run(["loclx", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        messages.append("LocalXpose (loclx) found.")
    except Exception:
        messages.append("LocalXpose (loclx) not found.")
    if shutil.which("7z"):
        messages.append("7z found.")
    else:
        messages.append("7z not found.")
    return "\n".join(messages)

def estimate_game_size(app_id, steamcmd_path):
    logger.info(f"Estimating game size for app id {app_id}")
    cmd = [steamcmd_path, '+app_info_update', '1', '+app_info_print', app_id, '+quit']
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = proc.stdout
    match = re.search(r'"SizeOnDisk"\s+"(\d+)"', output)
    if not match:
        match = re.search(r'"size"\s+"(\d+)"', output)
    if match:
        size_bytes = int(match.group(1))
        estimated_gb = size_bytes / 1024**3
        msg = f"Estimated game size: {estimated_gb:.2f} GB"
        logger.info(msg)
        return msg, size_bytes
    else:
        msg = "Could not determine game size. Proceeding without size estimation."
        logger.warning(msg)
        return msg, None

def download_and_compress(username, password, steam_guard_code, app_id, output_path, anonymous=False, resume=False):
    logger.info("Starting full download and compression process.")
    logger.info(f"Username: {username if not anonymous else 'anonymous'}, App ID: {app_id}, Output Path: {output_path}")
    log_flush()

    msg = verify_output_path(output_path)
    if "Error" in msg:
        return "", msg

    local_available = get_available_space(os.getcwd())
    if local_available < 10*1024**3:
        warning = "Warning: Less than 10GB available on disk. Download may fail."
        logger.warning(warning)
    log_flush()

    if not resume:
        if os.path.exists("./game"):
            shutil.rmtree("./game")
    if not os.path.exists("./game"):
        os.makedirs("./game")

    steamcmd_path = os.path.join(os.getcwd(), "steamcmd", "steamcmd.sh")
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
    login_process = subprocess.run(cmd_login, capture_output=True, text=True)
    output_login = login_process.stdout
    logger.info(f"Login output: {output_login}")
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

    time.sleep(20)
    status_messages = ["Login successful."]
    logger.info("Login successful.")
    log_flush()

    max_attempts = 3
    for attempt in range(max_attempts):
        logger.info(f"Attempt {attempt+1} to update AppInfo...")
        update_proc = subprocess.run([steamcmd_path, '+app_info_update', '1', '+quit'], capture_output=True, text=True)
        logger.info(update_proc.stdout)
        log_flush()
        if "Failed to request AppInfo update" not in update_proc.stdout:
            logger.info("AppInfo update successful.")
            break
        else:
            logger.warning("AppInfo update failed, retrying...")
            log_flush()
            time.sleep(5)

    cmd_download = [
        steamcmd_path,
        '+force_install_dir', './game',
        '+app_update', app_id, 'validate',
        '+quit'
    ]
    logger.info('Starting download...')
    log_flush()
    process_download = subprocess.Popen(
        cmd_download,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    download_start_time = time.time()
    for line in process_download.stdout:
        if '%' in line:
            try:
                progress = int(re.search(r'(\d+)%', line).group(1))
                elapsed_time = time.time() - download_start_time
                if progress > 0:
                    total_time_est = elapsed_time / (progress / 100)
                    remaining_time = total_time_est - elapsed_time
                    minutes, seconds = divmod(int(remaining_time), 60)
                    status = f"Downloading: {progress}% complete, ~{minutes}m {seconds}s remaining"
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
        error_message = process_download.stderr.read()
        logger.error(f"Download failed: {error_message}")
        log_flush()
        return "\n".join(status_messages), f"Download failed: {error_message}"

    logger.info('Starting compression...')
    log_flush()
    cmd_compress = ['7z', 'a', '-t7z', '-v4g', output_path, './game']
    process_compress = subprocess.Popen(
        cmd_compress,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    compress_start_time = time.time()
    for line in process_compress.stdout:
        if '%' in line:
            try:
                progress = int(re.search(r'(\d+)%', line).group(1))
                elapsed_time = time.time() - compress_start_time
                if progress > 0:
                    total_time_est = elapsed_time / (progress / 100)
                    remaining_time = total_time_est - elapsed_time
                    minutes, seconds = divmod(int(remaining_time), 60)
                    status = f"Compressing: {progress}% complete, ~{minutes}m {seconds}s remaining"
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
        error_message = process_compress.stderr.read()
        logger.error(f"Compression failed: {error_message}")
        log_flush()
        return "\n".join(status_messages), f"Compression failed: {error_message}"

    shutil.rmtree("./game", ignore_errors=True)
    completion_msg = f"Completed! Files saved as {output_path}.001, {output_path}.002, etc."
    logger.info(completion_msg)
    log_flush()
    return "\n".join(status_messages) + "\n" + completion_msg, ""

def download_and_compress_from_url(username, password, steam_guard_code, anonymous, steam_url, output_path, resume=False):
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
    size_msg, size_bytes = estimate_game_size(app_id, os.path.join(os.getcwd(), "steamcmd", "steamcmd.sh"))
    status_messages = [size_msg]
    status, error = download_and_compress(username, password, steam_guard_code, app_id, output_path, anonymous, resume)
    status_messages.append(status)
    return "\n".join(status_messages), error

# === Queue Management ===

download_queue = Queue()
queue_status = []

def process_queue():
    while True:
        task = download_queue.get()
        task_status = f"Processing download for {task['steam_url']}"
        queue_status.append(task_status)
        status, error = download_and_compress_from_url(
            task['username'], task['password'], task['steam_guard_code'],
            task['anonymous'], task['steam_url'], task['output_path'], task['resume']
        )
        result_status = f"Completed download for {task['steam_url']}. Status: {status}. Error: {error}"
        queue_status.append(result_status)
        download_queue.task_done()

threading.Thread(target=process_queue, daemon=True).start()

def add_to_queue(username, password, steam_guard_code, anonymous, steam_url, output_path, resume):
    task = {
        'username': username,
        'password': password,
        'steam_guard_code': steam_guard_code,
        'anonymous': anonymous,
        'steam_url': steam_url,
        'output_path': output_path,
        'resume': resume
    }
    download_queue.put(task)
    return f"Task added to queue. Queue size: {download_queue.qsize()}"

def get_queue_status():
    return "\n".join(queue_status)

def get_downloaded_files(output_path=None):
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
    if files:
        return "\n".join(files)
    else:
        return "No downloaded files found."

# === LocalXpose Tunnel Functions ===

localxpose_authtoken = os.getenv("LOCALXPOSE_AUTHTOKEN", "your_default_token")

def get_loclx_path():
    """Attempt to locate the 'loclx' binary."""
    loclx_path = shutil.which("loclx")
    if not loclx_path:
        # Try to get the global npm binary directory
        npm_bin = subprocess.run(["npm", "bin", "-g"], capture_output=True, text=True).stdout.strip()
        loclx_path = os.path.join(npm_bin, "loclx")
        if not os.path.exists(loclx_path):
            raise FileNotFoundError("loclx not found. Ensure 'npm install -g loclx' has been executed and the global npm bin directory is in PATH.")
    return loclx_path

def start_localxpose_http():
    # Use the globally installed "loclx" from npm
    loclx_path = get_loclx_path()
    cmd = [loclx_path, "tunnel", "http", "--to", "http://localhost:7860", "--authtoken", localxpose_authtoken]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in process.stdout:
        print(line, end="")

def start_localxpose_udp(tunnel_type="basic", port=None, to_addr=None, reserved_endpoint=None):
    loclx_path = get_loclx_path()
    cmd = [loclx_path, "tunnel", "udp"]
    if tunnel_type == "custom_port":
        if port:
            cmd += ['--port', str(port)]
    elif tunnel_type == "custom_to":
        if port and to_addr:
            cmd += ['--port', str(port), '--to', to_addr]
    elif tunnel_type == "reserved":
        if reserved_endpoint:
            cmd += ['--reserved-endpoint', reserved_endpoint]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in process.stdout:
        print(line, end="")

def start_udp_tunnel(tunnel_type, port, to_addr, reserved_endpoint):
    p = port.strip() if port and port.strip() else None
    t_addr = to_addr.strip() if to_addr and to_addr.strip() else None
    r_endpoint = reserved_endpoint.strip() if reserved_endpoint and reserved_endpoint.strip() else None
    threading.Thread(target=start_localxpose_udp, args=(tunnel_type, p, t_addr, r_endpoint), daemon=True).start()
    return f"UDP tunnel started with type: {tunnel_type}"
