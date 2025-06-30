import streamlit as st
import requests
import re
from urllib.parse import urlparse, parse_qs

def get_video_info(nanoo_url):
    """
    This function takes a nanoo.tv URL and attempts to extract the
    underlying video stream URL and other relevant information.

    Args:
        nanoo_url (str): The URL of the nanoo.tv page.

    Returns:
        dict: A dictionary containing video information or an error.
    """
    try:
        # Fetch the HTML content of the page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        response = requests.get(nanoo_url, headers=headers, timeout=15)
        response.raise_for_status()  # Raise an exception for bad status codes
        html_content = response.text

        # Use regex to find potential stream URLs within the HTML
        # This pattern looks for URLs ending in .mp4 with query parameters
        stream_url_match = re.search(r'(https?://[^\s"\']+\.mp4\?[^\s"\']+)', html_content)

        if stream_url_match:
            stream_url = stream_url_match.group(1)
            # Let's try to make the URL cleaner and more generic if possible
            parsed_url = urlparse(stream_url)
            query_params = parse_qs(parsed_url.query)

            # Extract key information (these might change over time)
            video_id_match = re.search(r'/(\d+)_stream', parsed_url.path)
            video_id = video_id_match.group(1) if video_id_match else "Unknown"

            return {
                "status": "success",
                "original_url": nanoo_url,
                "stream_url": stream_url,
                "video_id": video_id,
                "message": "Direkter Videostream gefunden!"
            }
        else:
            return {
                "status": "error",
                "message": "Konnte keinen direkten .mp4-Stream auf der Seite finden. Die Methode zum Einbetten hat sich möglicherweise geändert."
            }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Fehler beim Abrufen der URL: {e}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ein unerwarteter Fehler ist aufgetreten: {e}"
        }

def download_video(url, filename):
    """
    Downloads a video from a URL and saves it locally.
    Displays a progress bar in the Streamlit app.
    """
    try:
        with st.spinner(f'"{filename}" wird heruntergeladen...'):
            r = requests.get(url, stream=True)
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            block_size = 1024  # 1 Kilobyte
            progress_bar = st.progress(0)
            written_bytes = 0
            with open(filename, 'wb') as f:
                for data in r.iter_content(block_size):
                    written_bytes += len(data)
                    f.write(data)
                    progress = int((written_bytes / total_size) * 100)
                    progress_bar.progress(progress)
        st.success(f'Video "{filename}" erfolgreich heruntergeladen!')
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Download-Fehler: {e}")
        return False
    except Exception as e:
        st.error(f"Ein Fehler ist beim Speichern der Datei aufgetreten: {e}")
        return False

# --- Streamlit App UI ---
st.set_page_config(page_title="Nanoo Video Downloader", page_icon="⬇️", layout="centered")

st.title("Nanoo.tv Video Downloader")
st.write("""
Geben Sie eine nanoo.tv-Video-URL ein, um den direkten `.mp4`-Link zu finden und das Video herunterzuladen.
**Hinweis:** Dies funktioniert, indem der Seiteninhalt analysiert wird. Wenn nanoo.tv seine Website ändert, funktioniert dies möglicherweise nicht mehr.
""")

# --- Instructions ---
with st.expander("Wie es funktioniert und rechtliche Hinweise"):
    st.markdown("""
    1.  **URL einfügen:** Fügen Sie die vollständige URL der nanoo.tv-Seite mit dem Video ein (z. B. `https://www.nanoo.tv/link/w/...`).
    2.  **Link extrahieren:** Die App lädt den HTML-Code der Seite und sucht nach einer URL, die auf `.mp4` endet. Dies ist wahrscheinlich der temporäre Stream-Link.
    3.  **Herunterladen:** Wenn ein Link gefunden wird, können Sie versuchen, das Video direkt herunterzuladen.

    **Wichtiger rechtlicher Hinweis:** Bitte stellen Sie sicher, dass Sie die Erlaubnis des Rechteinhabers haben, bevor Sie Videos herunterladen. Das Herunterladen von urheberrechtlich geschütztem Material ohne Genehmigung kann illegal sein. Dieses Tool ist für Bildungszwecke und für das Herunterladen Ihrer eigenen Inhalte oder von Inhalten, für die Sie eine Berechtigung haben, gedacht.
    """)

# --- Main App Logic ---
url_input = st.text_input("Nanoo.tv Video-URL eingeben:", "https://www.nanoo.tv/link/w/PrzEXXhn")

if st.button("Download-Link extrahieren"):
    if url_input:
        with st.spinner("Analysiere URL..."):
            video_info = get_video_info(url_input)

            if video_info["status"] == "success":
                st.success(video_info["message"])
                st.session_state.video_info = video_info # Store info in session state

                st.markdown(f"**Video-ID:** `{video_info['video_id']}`")
                st.markdown("**Gefundener Stream-Link:**")
                st.code(video_info['stream_url'], language='text')

            else:
                st.error(video_info["message"])
                st.session_state.video_info = None
    else:
        st.warning("Bitte geben Sie eine URL ein.")

# --- Download Button ---
# Check if video_info is in session state before showing the download button
if 'video_info' in st.session_state and st.session_state.video_info:
    video_info = st.session_state.video_info
    st.markdown("---")
    st.write("Möchten Sie versuchen, dieses Video jetzt herunterzuladen?")
    
    file_name = f"nanoo_video_{video_info['video_id']}.mp4"
    
    if st.button(f"Herunterladen als {file_name}"):
        download_video(video_info['stream_url'], file_name)

