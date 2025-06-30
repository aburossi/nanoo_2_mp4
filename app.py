import streamlit as st
import requests
import re
import json
import time
import os
import io
from urllib.parse import urlparse

# This needs to be imported to use Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

def get_video_info_selenium_cloud(nanoo_url: str) -> dict:
    """
    Uses Selenium in a Streamlit Cloud-optimized configuration to find the .mp4 URL.
    This function launches a headless Chrome browser in the background.

    Args:
        nanoo_url (str): The URL of the nanoo.tv page.

    Returns:
        dict: A dictionary containing video information or an error message.
    """
    status_widget = st.empty()
    try:
        status_widget.info("🚀 Initializing a virtual browser in the cloud...")
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        # --- FIX APPLIED HERE ---
        # Add a unique user data directory for each run to prevent session conflicts
        chrome_options.add_argument(f"--user-data-dir=/tmp/selenium_{int(time.time())}")
        # ------------------------

        # Enable performance logging to capture network requests
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        
        status_widget.info("🌍 Opening browser and navigating to URL...")
        
        # In Streamlit Cloud, Chromium is installed via packages.txt.
        # We can specify the service to be more robust.
        service = ChromeService(executable_path="/usr/bin/chromedriver")
        with webdriver.Chrome(service=service, options=chrome_options) as driver:
            driver.get(nanoo_url)

            # Wait for the page to load and network requests to fire.
            time.sleep(10) 
            
            status_widget.info("🕵️‍♂️ Analyzing network traffic for video files...")
            logs = driver.get_log("performance")

        status_widget.empty()  # Clear status message

        stream_url = None
        for entry in logs:
            log = json.loads(entry["message"])["message"]
            if (
                log.get("method") == "Network.responseReceived"
                and "params" in log
                and "response" in log["params"]
                and "url" in log["params"]["response"]
                # Look for the specific video stream URL pattern
                and "_stream_hd.mp4" in log["params"]["response"]["url"]
            ):
                stream_url = log["params"]["response"]["url"]
                # We take the first one we find
                break
        
        if stream_url:
            # Try to extract a video ID for a clean filename
            video_id_match = re.search(r'/(\d+)_stream', urlparse(stream_url).path)
            video_id = video_id_match.group(1) if video_id_match else "video"
            
            return {
                "status": "success",
                "stream_url": stream_url.replace("&amp;", "&"), # Sanitize URL
                "video_id": video_id,
                "message": "✅ Direct video stream found!"
            }
        else:
            return {
                "status": "error",
                "message": "❌ Could not find an .mp4 stream in the network traffic. The site may have changed its video delivery method."
            }

    except Exception as e:
        status_widget.empty()
        st.error("An error occurred during browser automation.")
        st.code(str(e), language="text")
        return {
            "status": "error",
            "message": "Browser automation failed."
        }


def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(page_title="Cloud Video Downloader", page_icon="☁️", layout="centered")

    st.title("Cloud-Ready Video Downloader")
    st.write("This app uses browser automation in the cloud to extract direct video links.")

    with st.expander("Instructions & Disclaimer"):
        st.markdown("""
        1.  **Paste URL** and click **"Extract Video Link"**.
        2.  **Be Patient:** The app launches a browser in the background. This can take 15-30 seconds.
        3.  **Download:** If a link is found, a download button will appear. The video will be downloaded to the server and then provided to you.
        
        **Disclaimer:** This tool is for educational purposes. Please ensure you have the right to download the content before proceeding.
        """)

    # Initialize session state to hold video info
    if "video_info" not in st.session_state:
        st.session_state.video_info = None

    url_input = st.text_input("Enter the video page URL:", value="https://www.nanoo.tv/link/w/PrzEXXhn")

    if st.button("Extract Video Link", type="primary"):
        if url_input:
            # Clear previous results and run the extraction
            st.session_state.video_info = None
            st.session_state.video_info = get_video_info_selenium_cloud(url_input)
        else:
            st.warning("Please enter a URL.")

    # --- Display results and download button AFTER extraction ---
    if st.session_state.video_info:
        video_info = st.session_state.video_info
        st.markdown("---")

        if video_info.get("status") == "success":
            st.success(video_info["message"])
            st.markdown(f"**Video ID:** `{video_info['video_id']}`")
            st.markdown("**Found Stream Link:**")
            st.code(video_info['stream_url'], language='text')

            st.write("Click the button below to download the video.")
            
            file_name = f"video_{video_info['video_id']}.mp4"
            
            # Download the video content into an in-memory buffer when the button is pressed
            with st.spinner(f"Preparing '{file_name}' for download..."):
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Referer': 'https://www.nanoo.tv/'
                    }
                    response = requests.get(video_info['stream_url'], headers=headers, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    # Use an in-memory bytes buffer
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
                except requests.exceptions.RequestException as e:
                    st.error(f"Download failed: {e}")
                except Exception as e:
                    st.error(f"An error occurred while preparing the download: {e}")

        else:
            st.error(video_info["message"])

if __name__ == "__main__":
    main()
```

### What I Changed

In the `get_video_info_selenium_cloud` function, I added/changed two key things:

1.  **Unique User Directory:**
    ```python
    chrome_options.add_argument(f"--user-data-dir=/tmp/selenium_{int(time.time())}")
    ```
    This line creates a new, temporary profile directory for each run, named with the current timestamp (e.g., `/tmp/selenium_1677611234`). This completely avoids the "directory is already in use" conflict.

2.  **Explicit Driver Service:**
    ```python
    service = ChromeService(executable_path="/usr/bin/chromedriver")
    with webdriver.Chrome(service=service, options=chrome_options) as driver:
    ```
    This tells Selenium the exact path to the `chromedriver` executable that we installed via `packages.txt`. This is more reliable than hoping it's found in the system's `PATH`.

Please update your `app.py` with this new code. Your `packages.txt` and `requirements.txt` files are correct and do not need to be changed. This should finally resolve the iss
