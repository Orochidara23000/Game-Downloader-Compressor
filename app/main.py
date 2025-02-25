import os
import gradio as gr
import threading
from common import (
    system_check, verify_disk_space, verify_steam_login,
    download_and_compress_from_url, add_to_queue, get_queue_status, get_downloaded_files,
    start_udp_tunnel, start_localxpose_http
)

# Ensure the default output directory exists
default_output_dir = os.path.join(os.getcwd(), "output")
os.makedirs(default_output_dir, exist_ok=True)
default_output_path = os.path.join(default_output_dir, "game.7z")

# Start the LocalXpose HTTP tunnel in a background thread
threading.Thread(target=start_localxpose_http, daemon=True).start()

with gr.Blocks() as demo:
    gr.Markdown("# Game Downloader and Compressor")

    with gr.Accordion("System Check", open=True):
        system_check_output = gr.Textbox(label="System Check Result", lines=5)
        system_check_btn = gr.Button("Run System Check")
        system_check_btn.click(fn=system_check, inputs=[], outputs=system_check_output)

    with gr.Accordion("Step 1: Verify Disk Space", open=False):
        disk_space_result = gr.Textbox(label="Disk Space Information")
        verify_disk_btn = gr.Button("Verify Disk Space")
        verify_disk_btn.click(fn=verify_disk_space, inputs=[], outputs=disk_space_result)

    with gr.Accordion("Step 2: Verify Steam Login", open=False):
        username_input = gr.Textbox(label="Steam Username", placeholder="Enter your Steam username")
        password_input = gr.Textbox(label="Steam Password", type="password", placeholder="Enter your Steam password")
        steam_guard_input = gr.Textbox(label="Steam Guard Code (if required)", placeholder="Enter code from email")
        anonymous_checkbox = gr.Checkbox(label="Use Anonymous Login (for free games)", value=False)
        login_verification = gr.Textbox(label="Login Verification")
        verify_login_btn = gr.Button("Verify Steam Login")
        verify_login_btn.click(
            fn=verify_steam_login,
            inputs=[username_input, password_input, steam_guard_input, anonymous_checkbox],
            outputs=login_verification
        )

    with gr.Accordion("Step 3: Download and Compress Game", open=True):
        # Removed the output path input; now using the default_output_path
        steam_url_input = gr.Textbox(label="Steam URL", placeholder="e.g., https://store.steampowered.com/app/440/Team_Fortress_2/")
        anonymous_checkbox_dl = gr.Checkbox(label="Use Anonymous Login (for free games)", value=False)
        resume_checkbox = gr.Checkbox(label="Resume Download (if already started)", value=False)
        download_status = gr.Textbox(label="Status Updates", lines=10)
        download_error = gr.Textbox(label="Error Messages", lines=5)
        direct_download_btn = gr.Button("Direct Download and Compress")
        queue_download_btn = gr.Button("Add to Queue")
        # Use default_output_path in function calls
        direct_download_btn.click(
            fn=lambda u, p, s, a, url, r: download_and_compress_from_url(u, p, s, a, url, default_output_path, r),
            inputs=[username_input, password_input, steam_guard_input, anonymous_checkbox_dl, steam_url_input, resume_checkbox],
            outputs=[download_status, download_error]
        )
        queue_download_btn.click(
            fn=lambda u, p, s, a, url, r: add_to_queue(u, p, s, a, url, default_output_path, r),
            inputs=[username_input, password_input, steam_guard_input, anonymous_checkbox_dl, steam_url_input, resume_checkbox],
            outputs=download_status
        )

    with gr.Accordion("Queue Management", open=False):
        queue_status_box = gr.Textbox(label="Queue Status", lines=10)
        refresh_queue_btn = gr.Button("Refresh Queue Status")
        refresh_queue_btn.click(fn=get_queue_status, inputs=[], outputs=queue_status_box)

    with gr.Accordion("Downloaded Files", open=False):
        downloaded_files_box = gr.Textbox(label="Downloaded File(s)", lines=5)
        refresh_files_btn = gr.Button("Get Downloaded Files")
        refresh_files_btn.click(fn=get_downloaded_files, inputs=[], outputs=downloaded_files_box)

    with gr.Accordion("UDP Tunnel Options", open=False):
        gr.Markdown("Select the UDP tunnel type and parameters (as per your LocalXpose dashboard):")
        udp_tunnel_type = gr.Dropdown(label="Tunnel Type", choices=["basic", "custom_port", "custom_to", "reserved"], value="basic")
        udp_port = gr.Textbox(label="Port (e.g., 4545)", placeholder="Enter port if needed", value="")
        udp_to = gr.Textbox(label="Local Address (e.g., 192.168.10.3:6655)", placeholder="Enter destination address if needed", value="")
        udp_reserved = gr.Textbox(label="Reserved Endpoint (e.g., us.loclx.io:4455)", placeholder="Enter reserved endpoint if needed", value="")
        udp_tunnel_status = gr.Textbox(label="UDP Tunnel Status", lines=2)
        start_udp_btn = gr.Button("Start UDP Tunnel")
        start_udp_btn.click(fn=start_udp_tunnel,
                            inputs=[udp_tunnel_type, udp_port, udp_to, udp_reserved],
                            outputs=udp_tunnel_status)

# Launch Gradio interface on port 7860
if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, share=True, debug=True)
