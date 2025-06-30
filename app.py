import streamlit as st
import subprocess
import os
import io
import re
import json
import time
from urllib.parse import urlparse
import requests # <-- THE MISSING LINE IS ADDED HERE

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

# --- Selenium-based Downloader (for Nanoo.tv and other tricky sites) ---
def download_with_selenium(url: str):
    """
    Fallback method using Selenium to find a direct .mp4 link by sniffing network traffic.
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
            time.sleep(10)
            status_widget.info("🕵️‍♂️ Selenium: Analyzing network traffic...")
            logs = driver.get_log("performance")

        status_widget.empty()

        stream_url = None
        for entry in logs:
            log = json.loads(entry["message"])["message"]
            if (
                log.get("method") == "Network.responseReceived"
                and "params" in log
                and "response" in log["params"]
                and "url" in log["params"]["response"]
                and "_stream_" in log["params"]["response"]["url"]
                and ".mp4" in log["params"]["response"]["url"]
            ):
                stream_url = log["params"]["response"]["url"]
                break
        
        if stream_url:
            st.success("✅ Selenium found a direct .mp4 link!")
            st.code(stream_url)
            # Now download the found URL
            download_direct_link(stream_url)
        else:
            st.error("❌ Selenium fallback also failed. Could not find a downloadable video stream.")

    except Exception as e:
        status_widget.empty()
        st.error("An error occurred during Selenium browser automation.")
        st.code(str(e), language="text")

def download_direct_link(stream_url: str):
    """Helper function to download a given direct link."""
    try:
        file_name = os.path.basename(urlparse(stream_url).path)
        with st.spinner(f"Downloading '{file_name}'..."):
            response = requests.get(stream_url, stream=True, timeout=30)
            response.raise_for_status()
            
            video_bytes = io.BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                video_bytes.write(chunk)
            video_bytes.seek(0)
            
            st.download_button(
                label=f"⬇️ Download {file_name}",
                data=video_bytes,
                file_name=file_name,
                mime="video/mp4",
            )
    except Exception as e:
        st.error(f"Failed to download the direct link: {e}")


# --- yt-dlp Downloader (for SRF and other standard sites) ---
def download_with_yt_dlp(video_url: str):
    """
    Primary method using yt-dlp to download video. If it fails with a generic
    extractor error, it will trigger the Selenium fallback.
    """
    st.info("🚀 Attempting download with yt-dlp (fast method)...")
    
    temp_dir = "temp_downloads"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    output_template = os.path.join(temp_dir, "%(id)s.%(ext)s")
    
    command = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_template,
        video_url
    ]
    
    log_area = st.expander("Show yt-dlp Logs")
    full_log = ""
    unsupported_url_error = False

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8')
    
    for line in iter(process.stdout.readline, ""):
        log_area.text(line.strip())
        full_log += line
        # Check for the specific error that indicates we should fall back
        if "Unsupported URL" in line or "Falling back on generic information extractor" in line:
            unsupported_url_error = True
    
    process.wait()
    
    if process.returncode == 0:
        st.success("✅ yt-dlp download complete!")
        try:
            downloaded_file = max([os.path.join(temp_dir, f) for f in os.listdir(temp_dir)], key=os.path.getctime)
            file_name = os.path.basename(downloaded_file)

            st.markdown("---")
            with open(downloaded_file, "rb") as fp:
                st.download_button(
                    label=f"⬇️ Download {file_name}",
                    data=fp,
                    file_name=file_name,
                    mime="video/mp4"
                )
            os.remove(downloaded_file)
        except (ValueError, FileNotFoundError):
             st.error("Could not find the downloaded file after processing.")
    else:
        # If the process failed, check if it was due to an unsupported URL
        if unsupported_url_error:
            st.warning("⚠️ yt-dlp does not support this URL directly. Triggering fallback to browser automation method...")
            download_with_selenium(video_url)
        else:
            st.error("❌ yt-dlp failed. See logs above for details.")


# --- Main App ---
def main():
    st.set_page_config(page_title="Hybrid Video Downloader", page_icon="🦾", layout="centered")
    st.title("Hybrid Universal Video Downloader")
    
    with st.expander("How this works"):
        st.markdown("""
        This app combines two methods to maximize success:
        1.  **Fast Method (`yt-dlp`):** It first tries to download using `yt-dlp`, which is very fast for supported sites (like SRF, YouTube, etc.).
        2.  **Fallback Method (`Selenium`):** If the fast method fails (like with Nanoo.tv), it automatically launches a virtual browser in the background to find the video link, just like a human user.
        """)

    url_input = st.text_input("Enter Video Page URL:", value="https://www.srf.ch/play/tv/redirect/detail/5b477667-1d20-414d-8ab0-2d0f6ac565a1")
    st.caption("Tip: For SRF, use the '.../redirect/detail/...' URL, not the '.../embed?urn=...' one.")
    
    if st.button("Download Video", type="primary"):
        if url_input:
            download_with_yt_dlp(url_input)
        else:
            st.warning("Please enter a URL.")

if __name__ == "__main__":
    main()
