import streamlit as st
import subprocess
import os
import io
import re
import json
import time
from urllib.parse import urlparse
import requests

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

# --- Helper function to display the final download button ---
def display_download_button(file_name: str, data: io.BytesIO, label: str):
    """Creates the download button for the user with the correct MIME type."""
    # Determine MIME type from file extension
    file_ext = os.path.splitext(file_name)[1].lower()
    mime_types = {
        '.mp4': 'video/mp4',
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/mp4',
        '.webm': 'video/webm',
        '.ogg': 'audio/ogg'
    }
    mime = mime_types.get(file_ext, 'application/octet-stream') # Fallback

    st.download_button(
        label=f"⬇️ {label}: {file_name}",
        data=data,
        file_name=file_name,
        mime=mime,
    )

# --- Selenium-based Downloader (for tricky sites) ---
def start_selenium_process(url: str):
    """
    Fallback method using Selenium to find a direct media link (.mp4, .mp3)
    by sniffing network traffic.
    """
    status_widget = st.empty()
    try:
        status_widget.info("🚀 Selenium Fallback: Initializing virtual browser...")

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"--user-data-dir=/tmp/selenium_{int(time.time())}")
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        status_widget.info("🌍 Selenium: Navigating to URL...")
        service = ChromeService(executable_path="/usr/bin/chromedriver")

        with webdriver.Chrome(service=service, options=chrome_options) as driver:
            driver.get(url)
            time.sleep(12)
            status_widget.info("🕵️‍♂️ Selenium: Analyzing network traffic for video/audio streams...")
            logs = driver.get_log("performance")

        status_widget.empty()

        stream_url = None
        # --- MODIFIED: Updated regex to find .mp4 and .mp3 files ---
        stream_pattern = re.compile(r'https?://.*(?:_stream_|/videos?/|/audio/|manifest|media).*?\.(?:mp4|mp3)(?:[?&].*)?$', re.IGNORECASE)

        for entry in logs:
            log = json.loads(entry["message"])["message"]
            if (
                log.get("method") == "Network.responseReceived"
                and "params" in log
                and "response" in log["params"]
                and "url" in log["params"]["response"]
            ):
                found_url = log["params"]["response"]["url"]
                if stream_pattern.search(found_url):
                    stream_url = found_url
                    break

        if stream_url:
            st.success("✅ Selenium found a potential media link!")
            st.code(stream_url, language="text")

            if st.button("Start Download from Found Link", key="selenium_download"):
                download_from_direct_link(stream_url)
        else:
            st.error("❌ Selenium fallback failed. Could not find a downloadable video or audio stream.")

    except Exception as e:
        status_widget.empty()
        st.error("An error occurred during Selenium browser automation.")
        st.code(str(e), language="text")

def download_from_direct_link(stream_url: str):
    """Helper function to download from a direct link when a button is pressed."""
    try:
        # Sanitize filename from URL
        file_name = os.path.basename(urlparse(stream_url).path)
        if not file_name:
            file_ext = ".mp3" if ".mp3" in stream_url else ".mp4"
            file_name = f"media_file_{int(time.time())}{file_ext}"

        with st.spinner(f"Downloading '{file_name}'... This may take a moment."):
            response = requests.get(stream_url, stream=True, timeout=60)
            response.raise_for_status()

            media_bytes = io.BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                media_bytes.write(chunk)
            media_bytes.seek(0)

            # --- MODIFIED: display_download_button now handles MIME types ---
            display_download_button(file_name, media_bytes, "Download File")

    except requests.exceptions.RequestException as e:
        st.error(f"Failed to download from the direct link: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred during download: {e}")

# --- yt-dlp Downloader (Primary Method) ---
def fetch_data_with_yt_dlp(video_url: str):
    """
    Primary method using yt-dlp, now with improved format selection for both
    video and audio files.
    """
    st.info("🚀 Using yt-dlp to analyze the URL...")

    # --- MODIFIED: Format selection is now more inclusive of audio formats ---
    format_selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestaudio/best"

    try:
        st.write("Analyzing streamable link(s)...")
        get_url_command = ["yt-dlp", "-f", format_selector, "-g", video_url]
        result = subprocess.run(get_url_command, capture_output=True, text=True, check=True, encoding='utf-8')
        stream_urls = result.stdout.strip()

        if stream_urls:
            st.success("✅ Found streamable link(s) for direct use:")
            st.code(stream_urls, language='text')
        else:
            st.warning("Could not extract a direct streamable link, but will attempt full download if requested.")

    except subprocess.CalledProcessError as e:
        if "Unsupported URL" in e.stderr:
             st.warning("⚠️ yt-dlp does not support this URL directly. Triggering fallback to browser automation...")
             start_selenium_process(video_url)
             return
        st.warning(f"Could not extract a direct streamable link. Error: {e.stderr.strip()}")

    st.markdown("---")
    st.write("To get the complete, merged file, start the full download process.")
    if st.button("Start Full Download & Merge with yt-dlp", type="primary"):
        run_full_yt_dlp_download(video_url, format_selector)

def run_full_yt_dlp_download(video_url: str, format_selector: str):
    """
    This function runs the main yt-dlp download process.
    """
    temp_dir = "temp_downloads"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    output_template = os.path.join(temp_dir, "%(title)s - %(id)s.%(ext)s")

    command = [
        "yt-dlp", "-f", format_selector,
        "--merge-output-format", "mp4", # yt-dlp handles audio-only cases gracefully
        "-o", output_template, video_url
    ]

    log_area = st.expander("Show Full Download Logs", expanded=True)
    with st.spinner("yt-dlp is running... This may involve downloading and merging files."):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8')
        for line in iter(process.stdout.readline, ""):
            log_area.text(line.strip())
        process.wait()

    if process.returncode == 0:
        st.success("✅ Full file download complete!")
        try:
            downloaded_file = max([os.path.join(temp_dir, f) for f in os.listdir(temp_dir)], key=os.path.getctime)
            file_name = os.path.basename(downloaded_file)

            with open(downloaded_file, "rb") as fp:
                media_bytes = io.BytesIO(fp.read())

            # --- MODIFIED: display_download_button handles the MIME type ---
            display_download_button(file_name, media_bytes, "Download File")
            os.remove(downloaded_file)

        except (ValueError, FileNotFoundError):
            st.error("Could not find the downloaded file after processing.")
    else:
        st.error("❌ yt-dlp failed. See full logs above for details.")
        st.info("You could try the Selenium fallback if it wasn't triggered automatically.")


# --- Main App ---
def main():
    st.set_page_config(page_title="Hybrid Media Downloader", page_icon="🎧", layout="centered")
    st.title("Hybrid Universal Media Downloader")
    st.markdown("Now with support for both **video** and **audio** files!")

    with st.expander("How this works"):
        st.markdown("""
        This app gives you control over the download process for video and audio.
        1.  **Analyze URL:** It first analyzes the URL with `yt-dlp`, which can now find video and audio streams (like `.mp3` from radio pages).
        2.  **User-Triggered Download:** It then waits for you.
            - **Fast Method (`yt-dlp`):** For most sites (like SRF), you can start the full, high-quality download.
            - **Fallback Method (`Selenium`):** If `yt-dlp` can't handle the URL, it automatically uses a background browser to find `.mp4` or `.mp3` links, which you can then download.
        """)
    
    # Add the new audio URL as a selectable example
    url_examples = {
        "SRF Video": "https://www.srf.ch/play/tv/redirect/detail/5b477667-1d20-414d-8ab0-2d0f6ac565a1",
        "SRF Radio (Audio)": "https://www.srf.ch/play/radio/redirect/detail/17b705a0-4113-41d0-aa00-d0f3f2205f5f",
    }
    selected_example = st.radio("Choose an example URL:", list(url_examples.keys()), horizontal=True)
    url_input = st.text_input("Or enter any Video/Audio Page URL:", value=url_examples[selected_example])

    if st.button("Fetch Data from URL", type="primary"):
        if url_input:
            fetch_data_with_yt_dlp(url_input)
        else:
            st.warning("Please enter a URL.")

if __name__ == "__main__":
    main()
