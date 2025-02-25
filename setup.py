import os
import gradio as gr
import threading
from common import start_localxpose_http

# Start the LocalXpose HTTP tunnel in a background thread
threading.Thread(target=start_localxpose_http, daemon=True).start()

with gr.Blocks() as demo:
    gr.Markdown("# Game Downloader and Compressor - Setup Demo")
    def greet(name):
        return f"Hello, {name}!"
    gr.Interface(fn=greet, inputs="text", outputs="text").render()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, share=True, debug=True)
