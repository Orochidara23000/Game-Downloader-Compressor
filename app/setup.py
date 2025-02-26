import os
import gradio as gr
import threading
import subprocess
import sys
import time
from common import get_downloaded_files  # Use another function from common if needed

def install_dependencies():
    """Run the install_dependencies.sh script to set up SteamCMD and 7zip"""
    status = ""
    try:
        # Check if script exists
        if not os.path.exists("./install_dependencies.sh"):
            return "Error: install_dependencies.sh not found."
        
        # Make script executable if it isn't already
        os.chmod("./install_dependencies.sh", 0o755)
        
        print("Starting dependency installation process...")
        
        # Run the script and capture output in real-time
        process = subprocess.Popen(
            ["bash", "./install_dependencies.sh"], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Capture and display output in real-time
        status_lines = []
        for stdout_line in iter(process.stdout.readline, ""):
            line = stdout_line.strip()
            status_lines.append(line)
            print(f"INSTALL: {line}")
            
        # Get the return code
        process.stdout.close()
        return_code = process.wait()
        
        # Capture any stderr output
        stderr_output = process.stderr.read()
        if stderr_output:
            status_lines.append(f"STDERR: {stderr_output}")
            print(f"INSTALL ERROR: {stderr_output}")
        
        status = "\n".join(status_lines)
        
        if return_code != 0:
            status += f"\nError (code {return_code}): Installation failed. Please check logs."
        else:
            status += "\nDependencies installed successfully!"
        
        return status
    except Exception as e:
        error_msg = f"Exception during installation: {str(e)}"
        print(f"INSTALL EXCEPTION: {error_msg}")
        return f"{status}\n{error_msg}" if status else error_msg

with gr.Blocks() as demo:
    gr.Markdown("# Game Downloader and Compressor - Setup")
    
    with gr.Tab("System Setup"):
        install_output = gr.Textbox(label="Installation Output", lines=10)
        install_btn = gr.Button("Install Dependencies (SteamCMD & 7zip)")
        install_btn.click(fn=install_dependencies, inputs=[], outputs=install_output)
    
    with gr.Tab("Test Connection"):
        def greet(name):
            return f"Hello, {name}! Server is up and running."
        
        name_input = gr.Textbox(label="Enter your name", value="World")
        greet_output = gr.Textbox(label="Server Response")
        test_btn = gr.Button("Test Connection")
        test_btn.click(fn=greet, inputs=[name_input], outputs=[greet_output])

    # System status indicator
    system_status = gr.Textbox(
        label="System Status", 
        value="Server running. Interface is accessible via network.", 
        interactive=False
    )
    
    # Keep the server alive by updating status periodically
    def update_status():
        while True:
            time.sleep(60)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            yield f"Server running at {timestamp}. Interface is accessible via network."
    
    demo.load(update_status, None, system_status, every=60)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    print(f"Starting Gradio server on port {port}")
    
    # In Railway, we need to bind to 0.0.0.0 and ensure share is True
    # Also increase the max_threads to handle more connections
    demo.queue(max_size=20)  # Add a queue to handle multiple requests
    demo.launch(
        server_name="0.0.0.0",  # Critical - bind to all interfaces
        server_port=port,
        share=True,  # Always use share for Railway
        debug=os.getenv("DEBUG", "false").lower() == "true",
        show_error=True,  # Show detailed error messages
        prevent_thread_lock=True  # Prevent thread locking for better stability
    )
    
    # Add this to keep the script running even if something goes wrong with Gradio
    try:
        while True:
            time.sleep(3600)  # Sleep for an hour
            print("Server still running...")
    except KeyboardInterrupt:
        print("Server stopped by user")
