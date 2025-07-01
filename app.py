import streamlit as st
import subprocess
import os
import io
import re
import time
from urllib.parse import urlparse
import requests

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
            st.warning("yt-dlp ran but found no streamable links. Trying alternative approach...")
            st.session_state.stage = 'alternative_fallback'

    except subprocess.CalledProcessError as e:
        if "Unsupported URL" in e.stderr:
             st.warning("⚠️ yt-dlp does not support this URL directly. Trying alternative approach...")
             st.session_state.stage = 'alternative_fallback'
        else:
             st.error(f"yt-dlp failed. Error: {e.stderr.strip()}")
             st.session_state.stage = 'initial'

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

def extract_nanoo_media_url(url: str):
    """
    Extract media URL from Nanoo.tv by simulating browser behavior and intercepting network requests.
    """
    status_widget = st.empty()
    media_url = None
    
    try:
        status_widget.info("🎯 Detected Nanoo.tv - extracting media URL...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }
        
        # Step 1: Get the main page
        status_widget.info("📡 Step 1: Loading Nanoo.tv page...")
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        content = response.text
        
        # Step 2: Extract the media ID from the URL
        status_widget.info("🔍 Step 2: Extracting media ID...")
        media_id_match = re.search(r'/link/v/([a-zA-Z0-9]+)', url)
        if media_id_match:
            media_id = media_id_match.group(1)
            st.info(f"Found media ID: {media_id}")
        else:
            st.warning("Could not extract media ID from URL")
            return None
        
        # Step 3: Look for any immediate media URLs in the HTML
        status_widget.info("🔎 Step 3: Searching for embedded media URLs...")
        immediate_patterns = [
            r'"(https?://http\.nanoo\.tv/mediacontent/export/[^"]*\.mp4[^"]*)"',
            r'"(https?://[^"]*nanoo\.tv[^"]*stream[^"]*\.mp4[^"]*)"',
            r'src[:\s]*["\']([^"\']*http\.nanoo\.tv[^"\']*\.mp4[^"\']*)["\']',
        ]
        
        for pattern in immediate_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                media_url = matches[0]
                st.success(f"Found embedded media URL: {media_url}")
                break
        
        # Step 4: Try to trigger the media URL generation by simulating what the browser does
        if not media_url:
            status_widget.info("🌐 Step 4: Simulating browser requests to generate media URL...")
            
            # Extract any tokens, session info, or parameters from the page
            token_patterns = [
                r'"token"[:\s]*"([^"]+)"',
                r'"auth"[:\s]*"([^"]+)"',
                r'"session"[:\s]*"([^"]+)"',
                r'data-token="([^"]+)"',
                r'_token["\s]*:["\s]*"([^"]+)"',
            ]
            
            auth_token = None
            for pattern in token_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    auth_token = match.group(1)
                    break
            
            # Try different API endpoints that might generate the media URL
            api_endpoints = [
                f"https://www.nanoo.tv/player/load/{media_id}",
                f"https://www.nanoo.tv/api/player/{media_id}",
                f"https://www.nanoo.tv/embed/player/{media_id}",
                f"https://www.nanoo.tv/link/player/{media_id}",
                f"https://api.nanoo.tv/v1/media/{media_id}",
                f"https://www.nanoo.tv/ajax/media/{media_id}",
            ]
            
            # Update headers for API requests
            api_headers = headers.copy()
            api_headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': url,
            })
            
            if auth_token:
                api_headers['Authorization'] = f'Bearer {auth_token}'
                api_headers['X-CSRF-TOKEN'] = auth_token
            
            for api_endpoint in api_endpoints:
                try:
                    status_widget.info(f"🔄 Trying: {api_endpoint}")
                    api_response = session.get(api_endpoint, headers=api_headers, timeout=15)
                    
                    if api_response.status_code == 200:
                        try:
                            # Try to parse as JSON
                            api_data = api_response.json()
                            st.info(f"API Response received: {type(api_data)}")
                            
                            # Look for media URLs in the JSON response
                            def find_media_url_in_json(obj, path=""):
                                if isinstance(obj, dict):
                                    for key, value in obj.items():
                                        if isinstance(value, str) and 'http.nanoo.tv' in value and '.mp4' in value:
                                            return value
                                        elif isinstance(value, (dict, list)):
                                            result = find_media_url_in_json(value, f"{path}.{key}")
                                            if result:
                                                return result
                                elif isinstance(obj, list):
                                    for i, item in enumerate(obj):
                                        result = find_media_url_in_json(item, f"{path}[{i}]")
                                        if result:
                                            return result
                                return None
                            
                            found_url = find_media_url_in_json(api_data)
                            if found_url:
                                media_url = found_url
                                st.success(f"Found media URL in API response: {media_url}")
                                break
                                
                        except ValueError:
                            # Not JSON, search in text
                            response_text = api_response.text
                            for pattern in immediate_patterns:
                                matches = re.findall(pattern, response_text, re.IGNORECASE)
                                if matches:
                                    media_url = matches[0]
                                    st.success(f"Found media URL in API text response: {media_url}")
                                    break
                            if media_url:
                                break
                                
                except Exception as e:
                    continue
                    
            if media_url:
                status_widget.empty()
                return media_url
        
        # Step 5: Try to construct the media URL based on patterns
        if not media_url:
            status_widget.info("🔧 Step 5: Attempting to construct media URL...")
            
            # Extract any numeric IDs from the page that might be the actual media content ID
            numeric_id_patterns = [
                r'"contentId"[:\s]*([0-9]+)',
                r'"mediaContentId"[:\s]*([0-9]+)',
                r'"id"[:\s]*([0-9]+)',
                r'data-content-id="([0-9]+)"',
                r'/export/([0-9]+)/',
            ]
            
            content_id = None
            for pattern in numeric_id_patterns:
                match = re.search(pattern, content)
                if match:
                    content_id = match.group(1)
                    st.info(f"Found potential content ID: {content_id}")
                    break
            
            if content_id:
                # Try to construct the URL based on the pattern you provided
                constructed_urls = [
                    f"https://http.nanoo.tv/mediacontent/export/{content_id}/{content_id}_stream_hi.mp4",
                    f"https://http.nanoo.tv/mediacontent/export/{content_id}/{content_id}_stream.mp4",
                    f"https://http.nanoo.tv/mediacontent/export/{content_id}/{content_id}.mp4",
                ]
                
                for constructed_url in constructed_urls:
                    try:
                        # Test if the constructed URL is accessible
                        test_response = session.head(constructed_url, headers=headers, timeout=10)
                        if test_response.status_code == 200:
                            media_url = constructed_url
                            st.success(f"Successfully constructed media URL: {media_url}")
                            break
                    except:
                        continue
        
        status_widget.empty()
        return media_url
        
    except Exception as e:
        status_widget.empty()
        st.error(f"Error extracting from Nanoo.tv: {e}")
        return None

def try_alternative_extraction(url: str):
    """
    Alternative approach - tries different extraction methods based on the URL.
    """
    media_url = None
    
    # Special handling for Nanoo.tv
    if 'nanoo.tv' in url.lower():
        media_url = extract_nanoo_media_url(url)
    
    # If Nanoo extraction didn't work or it's not Nanoo, try general methods
    if not media_url:
        status_widget = st.empty()
        try:
            status_widget.info("🔍 Trying general extraction methods...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            content = response.text
            
            # General patterns for media URLs
            patterns = [
                r'"(https?://[^"]*\.mp4[^"]*)"',
                r'"(https?://[^"]*\.mp3[^"]*)"',
                r'"(https?://[^"]*\.m4a[^"]*)"',
                r'"(https?://[^"]*\.webm[^"]*)"',
                r'src="([^"]*\.[mp4|mp3|m4a|webm][^"]*)"',
                r'data-src="([^"]*\.[mp4|mp3|m4a|webm][^"]*)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    for match in matches:
                        if match.startswith('http') and any(ext in match.lower() for ext in ['.mp4', '.mp3', '.m4a', '.webm']):
                            media_url = match
                            break
                    if media_url:
                        break
                        
            status_widget.empty()
                        
        except Exception as e:
            status_widget.empty()
            st.warning(f"General extraction failed: {e}")
    
    # Try yt-dlp as final fallback
    if not media_url:
        try:
            st.info("🔧 Trying yt-dlp with extended options...")
            extended_command = [
                "yt-dlp", 
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "--referer", url,
                "-f", "best",
                "-g", 
                url
            ]
            result = subprocess.run(extended_command, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and result.stdout.strip():
                media_url = result.stdout.strip()
        except Exception as e:
            st.warning(f"yt-dlp fallback failed: {e}")
    
    if media_url:
        st.session_state.stream_urls = media_url
        st.session_state.stage = 'alternative_fetched'
    else:
        st.error("❌ Could not find a downloadable media stream.")
        st.info("💡 **For Nanoo.tv links:**")
        st.info("1. Make sure the link is publicly accessible")
        st.info("2. Try opening the link in a browser first to verify it works")
        st.info("3. Some Nanoo.tv content may require login or have restricted access")
        st.session_state.stage = 'initial'

def download_from_direct_link(stream_url: str):
    """Downloads from direct link and updates session state."""
    try:
        file_name = os.path.basename(urlparse(stream_url).path)
        if not file_name or '.' not in file_name:
            file_ext = ".mp3" if ".mp3" in stream_url else ".mp4"
            file_name = f"media_file_{int(time.time())}{file_ext}"

        with st.spinner(f"Downloading '{file_name}'..."):
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(stream_url, stream=True, timeout=60, headers=headers)
            response.raise_for_status()
            
            media_bytes = io.BytesIO()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            progress_bar = st.progress(0)
            for chunk in response.iter_content(chunk_size=8192):
                media_bytes.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    progress = downloaded / total_size
                    progress_bar.progress(progress)
            
            progress_bar.empty()
            media_bytes.seek(0)
            
            st.session_state.download_info = {"file_name": file_name, "data": media_bytes}
            st.session_state.stage = 'downloaded'
    except Exception as e:
        st.error(f"Failed to download the media: {e}")
        st.info("The link might be expired, protected, or require special access.")
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

    # --- URL Input Section ---
    url_examples = {
        "SRF Video": "https://www.srf.ch/play/tv/redirect/detail/5b477667-1d20-414d-8ab0-2d0f6ac565a1",
        "SRF Audio (Embed Code)": '<iframe width="560" height="315" src="https://www.srf.ch/play/embed?urn=urn:srf:audio:17b705a0-4113-41d0-aa00-d0f3f2205f5f&subdivisions=false" allowfullscreen allow="geolocation *; autoplay; encrypted-media"></iframe>',
        "Nanoo.tv (Example)": "https://nanoo.tv/link/example-placeholder",
    }
    selected_example = st.radio(
        "First, choose the type of link you have:", 
        list(url_examples.keys()), 
        horizontal=True, 
        key="examples"
    )
    
    # --- Visual Guide Section ---
    st.markdown("---")
    st.write("**Copy the link as shown in the example and paste it below:**")
    
    # Note: Images would need to be uploaded to your repo or hosted elsewhere
    if selected_example == "Nanoo.tv (Example)":
        st.info("📋 For Nanoo.tv: Click 'Share', then copy the generated link.")
    elif selected_example == "SRF Video":
        st.info("📋 For SRF Video: Click 'Teilen' (Share), then click the 'Link' icon to copy.")
    elif selected_example == "SRF Audio (Embed Code)":
        st.info("📋 For SRF Audio: Click 'Teilen' (Share), then copy the 'Embed Code'.")
    
    url_input = st.text_input(
        "Paste your URL or Embed Code here:", 
        value=url_examples[selected_example], 
        key="url_input_box"
    )
    st.markdown("---")

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
            st.rerun()

    if st.session_state.stage == "downloading":
        run_full_yt_dlp_download(st.session_state.sanitized_url)

    if st.session_state.stage == "alternative_fallback":
        try_alternative_extraction(st.session_state.sanitized_url)

    if st.session_state.stage == "alternative_fetched":
        st.success("✅ Found a potential media link!")
        
        # Display the URL in a copyable format
        st.markdown("**🔗 Extracted Media URL:**")
        st.code(st.session_state.stream_urls, language="text")
        
        # Create a text input with the URL so users can easily copy it
        st.text_input(
            "📋 Copy this URL:", 
            value=st.session_state.stream_urls, 
            key="copyable_url",
            help="You can copy this URL and use it elsewhere, or download the file directly below."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Download File", key="alternative_download", type="primary"):
                st.session_state.stage = "alternative_downloading"
                st.rerun()
        with col2:
            if st.button("🔄 Try Another URL", key="reset_app"):
                st.session_state.stage = "initial"
                st.session_state.sanitized_url = ""
                st.session_state.stream_urls = ""
                st.session_state.download_info = {}
                st.rerun()

    if st.session_state.stage == "alternative_downloading":
        download_from_direct_link(st.session_state.stream_urls)

    if st.session_state.stage == "downloaded":
        st.success("✅ File is ready to download!")
        info = st.session_state.download_info
        display_download_button(info["file_name"], info["data"], "Download File")

    # --- Footer ---
    st.markdown("---")
    st.markdown("💡 **Note:** This app works best with publicly accessible media links. Some platforms may block automated downloads.")

if __name__ == "__main__":
    main()
