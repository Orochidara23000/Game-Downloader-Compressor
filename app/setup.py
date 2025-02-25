import os
import gradio as gr
import threading
from common import get_downloaded_files  # Use another function from common if needed

with gr.Blocks() as demo:
    gr.Markdown("# Game Downloader and Compressor - Setup Demo")
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
        share=not is_railway,  # Don't use Gradio sharing on Railway
        debug=os.getenv("DEBUG", "false").lower() == "true"
    )
