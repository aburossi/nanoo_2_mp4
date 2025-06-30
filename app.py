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
    """Creates the download button for the user."""
    st.download_button(
        label=f"⬇️ {label}: {file_name}",
        data=data,
        file_name=file_name,
        mime="video/mp4",
    )

# --- Selenium-based Downloader (for Nanoo.tv and other tricky sites) ---
def start_selenium_process(url: str):
    """
    Fallback method using Selenium to find a direct .mp4 link by sniffing network traffic.
    The download itself is triggered by a user button.
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
        # Ensure the path to chromedriver is correct for your Streamlit environment
        service = ChromeService(executable_path="/usr/bin/chromedriver")

        with webdriver.Chrome(service=service, options=chrome_options) as driver:
            driver.get(url)
            # Increased sleep time to allow for more complex sites to load
            time.sleep(12)
            status_widget.info("🕵️‍♂️ Selenium: Analyzing network traffic...")
            logs = driver.get_log("performance")

        status_widget.empty()

        stream_url = None
        # Enhanced regex to find more stream variations
        stream_pattern = re.compile(r'https?://.*(?:_stream_|/videos?/|manifest).*?\.mp4(?:[?&].*)?$')
        
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
            st.success("✅ Selenium found a potential .mp4 link!")
            st.code(stream_url, language="text")
            
            # Add a button to let the user initiate the download
            if st.button("Start Download from Found Link", key="selenium_download"):
                download_from_direct_link(stream_url)
        else:
            st.error("❌ Selenium fallback failed. Could not find a downloadable video stream in the network traffic.")

    except Exception as e:
        status_widget.empty()
        st.error("An error occurred during Selenium browser automation.")
        st.code(str(e), language="text")

def download_from_direct_link(stream_url: str):
    """Helper function to download from a direct link when a button is pressed."""
    try:
        file_name = os.path.basename(urlparse(stream_url).path)
        if not file_name:
             # Create a fallback filename
            file_name = f"video_{int(time.time())}.mp4"

        with st.spinner(f"Downloading '{file_name}'... This may take a moment."):
            response = requests.get(stream_url, stream=True, timeout=60)
            response.raise_for_status()
            
            video_bytes = io.BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                video_bytes.write(chunk)
            video_bytes.seek(0)
            
            display_download_button(file_name, video_bytes, "Download File")

    except requests.exceptions.RequestException as e:
        st.error(f"Failed to download from the direct link: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred during download: {e}")

# --- yt-dlp Downloader (for SRF and other standard sites) ---
def fetch_data_with_yt_dlp(video_url: str):
    """
    Primary method using yt-dlp. It first gets streamable links.
    The user can then choose to trigger the full download and merge process.
    """
    st.info("🚀 Using yt-dlp to analyze the URL...")
    
    # --- Step 1: Get and Display Stream URL(s) First ---
    try:
        st.write("Analyzing streamable link(s)...")
        get_url_command = [
            "yt-dlp", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-g", video_url
        ]
        result = subprocess.run(get_url_command, capture_output=True, text=True, check=True, encoding='utf-8')
        stream_urls = result.stdout.strip()
        
        if stream_urls:
            st.success("✅ Found streamable link(s) for direct use:")
            st.code(stream_urls, language='text')
        else:
            st.warning("Could not extract a direct streamable link, but will attempt full download if requested.")

    except subprocess.CalledProcessError as e:
        # If getting the URL fails, it might be an unsupported URL or still downloadable.
        if "Unsupported URL" in e.stderr:
             st.warning("⚠️ yt-dlp does not support this URL directly. Triggering fallback to browser automation...")
             start_selenium_process(video_url)
             return # Stop further execution in this function
        st.warning(f"Could not extract a direct streamable link. Error: {e.stderr.strip()}")

    st.markdown("---")
    
    # --- Step 2: Add a button for the user to start the full download ---
    st.write("To get the complete, merged video file, start the full download process.")
    if st.button("Start Full Download & Merge with yt-dlp", type="primary"):
        run_full_yt_dlp_download(video_url)

def run_full_yt_dlp_download(video_url: str):
    """
    This function runs the main yt-dlp download and merge process.
    It is called only when the user clicks the corresponding button.
    """
    temp_dir = "temp_downloads"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    output_template = os.path.join(temp_dir, "%(title)s - %(id)s.%(ext)s")
    
    command = [
        "yt-dlp", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_template, video_url
    ]
    
    log_area = st.expander("Show Full Download Logs", expanded=True)
    unsupported_url_error = False
    
    with st.spinner("yt-dlp is running... Merging video and audio streams."):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8')
        
        for line in iter(process.stdout.readline, ""):
            log_area.text(line.strip())
            if "Unsupported URL" in line or "Falling back on generic information extractor" in line:
                unsupported_url_error = True
        
        process.wait()
    
    if process.returncode == 0:
        st.success("✅ Full file download and merge complete!")
        try:
            # Find the most recently created file in the temp directory
            downloaded_file = max([os.path.join(temp_dir, f) for f in os.listdir(temp_dir)], key=os.path.getctime)
            file_name = os.path.basename(downloaded_file)

            with open(downloaded_file, "rb") as fp:
                video_bytes = io.BytesIO(fp.read())
            
            display_download_button(file_name, video_bytes, "Download merged file")
            
            # Clean up the downloaded file
            os.remove(downloaded_file)
        except (ValueError, FileNotFoundError):
            st.error("Could not find the downloaded file after processing.")
    else:
        if unsupported_url_error:
            st.warning("⚠️ yt-dlp failed because the URL is unsupported. Trying the Selenium fallback method.")
            start_selenium_process(video_url)
        else:
            st.error("❌ yt-dlp failed. See full logs above for details.")

# --- Main App ---
def main():
    st.set_page_config(page_title="Hybrid Video Downloader", page_icon="🦾", layout="centered")
    st.title("Hybrid Universal Video Downloader")
    
    with st.expander("How this works"):
        st.markdown("""
        This app gives you control over the download process.
        1.  **Analyze URL:** First, it analyzes the URL with `yt-dlp` to find streamable links.
        2.  **User-Triggered Download:** It then waits for you to click a button to start the actual download.
            - **Fast Method (`yt-dlp`):** For supported sites (like SRF), you can click to start the full download and merge process.
            - **Fallback Method (`Selenium`):** If `yt-dlp` fails (like with Nanoo.tv), it automatically tries to find a video link using a background browser. You then get a final button to download from that link.
        """)

    url_input = st.text_input("Enter Video Page URL:", value="https://www.srf.ch/play/tv/redirect/detail/5b477667-1d20-414d-8ab0-2d0f6ac565a1")
    st.caption("Tip: For SRF, use the '.../redirect/detail/...' URL, not the '.../embed?urn=...' one.")
    
    if st.button("Fetch Data from URL", type="primary"):
        if url_input:
            # The main function now just starts the initial data fetching
            fetch_data_with_yt_dlp(url_input)
        else:
            st.warning("Please enter a URL.")

if __name__ == "__main__":
    main()
