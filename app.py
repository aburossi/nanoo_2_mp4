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

# --- Sanitization Function ---
def sanitize_and_extract_url(input_text: str) -> str:
    """
    Extracts the URL from an iframe embed code or returns the input if it's already a URL.
    """
    match = re.search(r'<iframe.*?src="([^"]+)"', input_text)
    if match:
        st.info("Iframe detected. Extracted the source URL for you.")
        return match.group(1)
    return input_text.strip()

# --- UI Helper Functions ---
def display_download_button(file_name: str, data: io.BytesIO, label: str):
    """Creates the download button for the user with the correct MIME type."""
    file_ext = os.path.splitext(file_name)[1].lower()
    mime_types = {
        '.mp4': 'video/mp4',
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/mp4',
        '.webm': 'video/webm',
        '.ogg': 'audio/ogg'
    }
    mime = mime_types.get(file_ext, 'application/octet-stream')
    st.download_button(
        label=f"⬇️ {label}: {file_name}",
        data=data,
        file_name=file_name,
        mime=mime,
    )

# --- Logic Functions (Update Session State) ---

def fetch_data_with_yt_dlp(url: str):
    """
    Uses yt-dlp to get streamable links and updates the session state.
    """
    st.info("🚀 Using yt-dlp to analyze the URL...")
    format_selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestaudio/best"
    try:
        get_url_command = ["yt-dlp", "-f", format_selector, "-g", url]
        result = subprocess.run(get_url_command, capture_output=True, text=True, check=True, encoding='utf-8')
        
        st.session_state.stream_urls = result.stdout.strip()
        if st.session_state.stream_urls:
            st.session_state.stage = 'fetched' # Transition to next stage
        else:
            st.warning("yt-dlp ran but found no streamable links. Trying Selenium fallback...")
            st.session_state.stage = 'selenium_fallback'

    except subprocess.CalledProcessError as e:
        if "Unsupported URL" in e.stderr:
             st.warning("⚠️ yt-dlp does not support this URL directly. Triggering fallback to browser automation...")
             st.session_state.stage = 'selenium_fallback' # Transition to fallback
        else:
             st.error(f"yt-dlp failed. Error: {e.stderr.strip()}")
             st.session_state.stage = 'initial' # Reset on error

def run_full_yt_dlp_download(url: str):
    """
    Runs the full yt-dlp download process and stores the result in session state.
    """
    temp_dir = "temp_downloads"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    output_template = os.path.join(temp_dir, "%(title)s - %(id)s.%(ext)s")
    format_selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestaudio/best"
    command = [
        "yt-dlp", "-f", format_selector,
        "--merge-output-format", "mp4",
        "-o", output_template, url
    ]

    log_area = st.expander("Show Full Download Logs", expanded=True)
    with st.spinner("yt-dlp is running..."):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8')
        for line in iter(process.stdout.readline, ""):
            log_area.text(line.strip())
        process.wait()

    if process.returncode == 0:
        try:
            downloaded_file = max([os.path.join(temp_dir, f) for f in os.listdir(temp_dir)], key=os.path.getctime)
            file_name = os.path.basename(downloaded_file)
            with open(downloaded_file, "rb") as fp:
                media_bytes = io.BytesIO(fp.read())
            
            # Store data for the download button
            st.session_state.download_info = {"file_name": file_name, "data": media_bytes}
            st.session_state.stage = 'downloaded'
            os.remove(downloaded_file)
        except (ValueError, FileNotFoundError):
            st.error("Could not find the downloaded file after processing.")
            st.session_state.stage = 'initial'
    else:
        st.error("❌ yt-dlp failed. See full logs above for details.")
        st.session_state.stage = 'initial'

def start_selenium_process(url: str):
    """
    Selenium fallback to find a direct media link and update session state.
    """
    status_widget = st.empty()
    try:
        status_widget.info("🚀 Selenium Fallback: Initializing virtual browser...")
        # (Selenium setup code remains the same)
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"--user-data-dir=/tmp/selenium_{int(time.time())}")
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        service = ChromeService(executable_path="/usr/bin/chromedriver")

        with webdriver.Chrome(service=service, options=chrome_options) as driver:
            status_widget.info("🌍 Selenium: Navigating to URL...")
            driver.get(url)
            time.sleep(12)
            status_widget.info("🕵️‍♂️ Selenium: Analyzing network traffic...")
            logs = driver.get_log("performance")
        status_widget.empty()

        stream_url = None
        stream_pattern = re.compile(r'https?://.*(?:_stream_|/videos?/|/audio/|manifest|media).*?\.(?:mp4|mp3)(?:[?&].*)?$', re.IGNORECASE)
        for entry in logs:
            log = json.loads(entry["message"])["message"]
            if (log.get("method") == "Network.responseReceived" and "params" in log and "response" in log["params"] and "url" in log["params"]["response"]):
                found_url = log["params"]["response"]["url"]
                if stream_pattern.search(found_url):
                    stream_url = found_url
                    break
        
        if stream_url:
            st.session_state.stream_urls = stream_url # Store single URL
            st.session_state.stage = 'selenium_fetched'
        else:
            st.error("❌ Selenium fallback also failed. Could not find a downloadable video or audio stream.")
            st.session_state.stage = 'initial'
    except Exception as e:
        status_widget.empty()
        st.error(f"An error occurred during Selenium browser automation: {e}")
        st.session_state.stage = 'initial'

def download_from_direct_link(stream_url: str):
    """Downloads from direct link and updates session state."""
    try:
        file_name = os.path.basename(urlparse(stream_url).path)
        if not file_name:
            file_ext = ".mp3" if ".mp3" in stream_url else ".mp4"
            file_name = f"media_file_{int(time.time())}{file_ext}"

        with st.spinner(f"Downloading '{file_name}'..."):
            response = requests.get(stream_url, stream=True, timeout=60)
            response.raise_for_status()
            media_bytes = io.BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                media_bytes.write(chunk)
            media_bytes.seek(0)
            
            st.session_state.download_info = {"file_name": file_name, "data": media_bytes}
            st.session_state.stage = 'downloaded'
    except Exception as e:
        st.error(f"Failed to download the direct link: {e}")
        st.session_state.stage = 'initial'

# --- Main App Controller ---
def main():
    st.set_page_config(page_title="Hybrid Media Downloader", page_icon="🔗", layout="centered")
    st.title("Hybrid Universal Media Downloader")
    st.markdown("Supports **video**, **audio**, and tricky sites like **Nanoo.tv**.")

    # --- Initialize Session State ---
    if "stage" not in st.session_state:
        st.session_state.stage = "initial"
        st.session_state.sanitized_url = ""
        st.session_state.stream_urls = ""
        st.session_state.download_info = {}

    # --- UPDATED: How-To Guide with Images ---
    with st.expander("📖 How to Get the Right Link (Visual Guide)"):
        st.subheader("Nanoo.tv")
        st.image("nanoo.png", caption="1. Click 'Share', 2. Copy the generated link.")
        
        st.subheader("SRF Video")
        st.image("srf-video.png", caption="1. Click 'Teilen' (Share), 2. Click the 'Link' icon to copy.")

        st.subheader("SRF Audio / Radio")
        st.image("srf-audio.png", caption="1. Click 'Teilen' (Share), 2. Copy the 'Embed Code'.")

    # --- URL Input ---
    url_examples = {
        "SRF Video": "https://www.srf.ch/play/tv/redirect/detail/5b477667-1d20-414d-8ab0-2d0f6ac565a1",
        "SRF Audio (Embed Code)": '<iframe width="560" height="315" src="https://www.srf.ch/play/embed?urn=urn:srf:audio:17b705a0-4113-41d0-aa00-d0f3f2205f5f&subdivisions=false" allowfullscreen allow="geolocation *; autoplay; encrypted-media"></iframe>',
        "Nanoo.tv (Example)": "https://nanoo.tv/link/example-placeholder",
    }
    selected_example = st.radio("Choose an example:", list(url_examples.keys()), horizontal=True, key="examples")
    
    url_input = st.text_input("Or paste any URL or Embed Code here:", value=url_examples[selected_example], key="url_input_box")

    if st.button("Fetch Data from URL", type="primary"):
        if url_input:
            st.session_state.stage = "fetching"
            st.session_state.sanitized_url = sanitize_and_extract_url(url_input)
            st.session_state.stream_urls = ""
            st.session_state.download_info = {}
        else:
            st.warning("Please paste a URL or embed code.")

    # --- STATE MACHINE ---
    if st.session_state.stage == "fetching":
        fetch_data_with_yt_dlp(st.session_state.sanitized_url)

    if st.session_state.stage == "fetched":
        st.success("✅ Found streamable link(s):")
        st.code(st.session_state.stream_urls, language='text')
        st.markdown("---")
        st.write("To get the complete, merged file, click the button below.")
        if st.button("Start Full Download & Merge with yt-dlp", type="primary"):
            st.session_state.stage = "downloading"
            st.experimental_rerun()

    if st.session_state.stage == "downloading":
        run_full_yt_dlp_download(st.session_state.sanitized_url)

    if st.session_state.stage == "selenium_fallback":
        start_selenium_process(st.session_state.sanitized_url)

    if st.session_state.stage == "selenium_fetched":
        st.success("✅ Selenium found a potential media link!")
        st.code(st.session_state.stream_urls, language="text")
        if st.button("Start Download from Found Link", key="selenium_download"):
            st.session_state.stage = "selenium_downloading"
            st.experimental_rerun()

    if st.session_state.stage == "selenium_downloading":
        download_from_direct_link(st.session_state.stream_urls)

    if st.session_state.stage == "downloaded":
        st.success("✅ File is ready to download!")
        info = st.session_state.download_info
        display_download_button(info["file_name"], info["data"], "Download File")

if __name__ == "__main__":
    main()
