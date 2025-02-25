import os
import gradio as gr
import threading
import subprocess
import sys
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
        
        # Run the script and capture output
        process = subprocess.run(
            ["bash", "./install_dependencies.sh"], 
            capture_output=True, 
            text=True
        )
        status = process.stdout
        
        if process.returncode != 0:
            status += f"\nError (code {process.returncode}): {process.stderr}"
        else:
            status += "\nDependencies installed successfully!"
        
        return status
    except Exception as e:
        return f"Exception during installation: {str(e)}"

with gr.Blocks() as demo:
    gr.Markdown("# Game Downloader and Compressor - Setup Demo")
    
    with gr.Tab("System Setup"):
        install_output = gr.Textbox(label="Installation Output", lines=10)
        install_btn = gr.Button("Install Dependencies (SteamCMD & 7zip)")
        install_btn.click(fn=install_dependencies, inputs=[], outputs=install_output)
    
    with gr.Tab("Test"):
        def greet(name):
            return f"Hello, {name}!"
        gr.Interface(fn=greet, inputs="text", outputs="text").render()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    # Only use share=True in development, not in Railway
    is_railway = os.getenv("RAILWAY_ENVIRONMENT") is not None
    demo.launch(
        server_name="0.0.0.0", 
        server_port=port, 
        share=True,  # Always share the Gradio interface
        debug=os.getenv("DEBUG", "false").lower() == "true"
    )
