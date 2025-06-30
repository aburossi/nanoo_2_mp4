import streamlit as st
import requests
import re
import json
import time
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- Selenium-basierte Funktion zum Extrahieren der Video-URL ---
def get_video_info_selenium(nanoo_url):
    """
    Verwendet Selenium, um einen Browser zu steuern, die Seite zu laden und den
    Netzwerkverkehr abzufangen, um die .mp4-URL zu finden.
    Dies ist eine robustere Methode.

    Args:
        nanoo_url (str): Die URL der nanoo.tv Seite.

    Returns:
        dict: Ein Wörterbuch mit Videoinformationen oder einem Fehler.
    """
    try:
        st.write("Initialisiere einen virtuellen Browser (dies kann einen Moment dauern)...")
        
        # Selenium WebDriver Optionen einrichten
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Browser ohne UI ausführen
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        # Automatische Installation und Verwaltung von ChromeDriver
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        st.write(f"Öffne {nanoo_url} im virtuellen Browser...")
        driver.get(nanoo_url)

        # Gib der Seite etwas Zeit, um zu laden und den Videoplayer zu initialisieren
        time.sleep(8) 
        
        st.write("Analysiere den Netzwerkverkehr auf Videodateien...")
        
        # Performance-Logs des Browsers abrufen
        logs = driver.get_log("performance")
        
        driver.quit() # Schliesse den Browser so schnell wie möglich

        stream_url = None
        for entry in logs:
            log = json.loads(entry["message"])["message"]
            if (
                "Network.responseReceived" in log["method"]
                and "params" in log
                and "response" in log["params"]
                and "url" in log["params"]["response"]
                and ".mp4" in log["params"]["response"]["url"]
            ):
                stream_url = log["params"]["response"]["url"]
                # Wir nehmen den ersten gefundenen .mp4-Link
                break 
        
        if stream_url:
            video_id_match = re.search(r'/(\d+)_stream', urlparse(stream_url).path)
            video_id = video_id_match.group(1) if video_id_match else "Unknown"
            
            return {
                "status": "success",
                "stream_url": stream_url,
                "video_id": video_id,
                "message": "Direkter Videostream über Netzwerkanalyse gefunden!"
            }
        else:
            return {
                "status": "error",
                "message": "Konnte auch mit der Netzwerkanalyse keinen .mp4-Stream finden. Möglicherweise wird ein anderes Videoformat (z.B. .m3u8) verwendet oder die Seite benötigt mehr Interaktion."
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Ein Fehler bei der Browser-Automatisierung ist aufgetreten: {e}"
        }

# --- Download-Funktion (unverändert) ---
def download_video(url, filename):
    """
    Downloads a video from a URL and saves it locally.
    Displays a progress bar in the Streamlit app.
    """
    try:
        with st.spinner(f'"{filename}" wird heruntergeladen...'):
            # Manchmal enthalten die URLs HTML-Entities wie &amp;, die ersetzt werden müssen
            url = url.replace("&amp;", "&")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            r = requests.get(url, headers=headers, stream=True, timeout=20)
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            block_size = 1024 * 1024 # 1 MB
            progress_bar = st.progress(0)
            written_bytes = 0
            
            # Zeige eine Warnung, wenn die Dateigrösse unbekannt ist
            if total_size == 0:
                st.warning("Dateigrösse ist unbekannt. Fortschrittsanzeige wird nicht exakt sein.")

            with open(filename, 'wb') as f:
                for data in r.iter_content(block_size):
                    written_bytes += len(data)
                    f.write(data)
                    if total_size > 0:
                        progress = int((written_bytes / total_size) * 100)
                        progress_bar.progress(min(progress, 100))

        st.success(f'Video "{filename}" erfolgreich heruntergeladen!')
        # Biete die Datei direkt im Browser zum Download an
        with open(filename, "rb") as fp:
            st.download_button(
                label="Gespeicherte Datei hier herunterladen",
                data=fp,
                file_name=filename,
                mime="video/mp4"
            )
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Download-Fehler: {e}")
        return False
    except Exception as e:
        st.error(f"Ein Fehler ist beim Speichern der Datei aufgetreten: {e}")
        return False

# --- Streamlit App UI ---
st.set_page_config(page_title="Advanced Video Downloader", page_icon="🕵️‍♂️", layout="centered")

st.title("Advanced Video Downloader")
st.write("""
Diese App verwendet eine fortgeschrittene Methode (Browser-Automatisierung), um Video-Links von Webseiten zu extrahieren und sie herunterzuladen.
""")

# --- Instructions ---
with st.expander("Wie es funktioniert und wichtige Hinweise"):
    st.markdown("""
    1.  **URL einfügen:** Geben Sie die URL der Seite mit dem Video ein.
    2.  **Link extrahieren:** Die App startet im Hintergrund einen Chrome-Browser, lädt die Seite und **analysiert den Netzwerkverkehr**, um die `.mp4`-Videodatei zu finden. Dieser Vorgang dauert etwas länger.
    3.  **Herunterladen:** Wenn ein Link gefunden wird, können Sie das Video herunterladen.

    **Zusätzliche Installationen erforderlich:**
    Diese Methode benötigt zusätzliche Bibliotheken. Führen Sie diesen Befehl in Ihrem Terminal aus:
    ```bash
    pip install streamlit requests selenium webdriver-manager
    ```
    Stellen Sie ausserdem sicher, dass **Google Chrome** auf Ihrem System installiert ist.
    
    **Rechtlicher Hinweis:** Bitte stellen Sie sicher, dass Sie die Erlaubnis des Rechteinhabers haben, bevor Sie Videos herunterladen. Dieses Tool ist für Bildungszwecke und für das Herunterladen Ihrer eigenen Inhalte gedacht.
    """)

# --- Main App Logic ---
url_input = st.text_input("Video-URL eingeben:", "https://www.nanoo.tv/link/w/PrzEXXhn")

if st.button("Video-Link extrahieren (Advanced)"):
    if url_input:
        video_info = get_video_info_selenium(url_input)

        if video_info["status"] == "success":
            st.success(video_info["message"])
            st.session_state.video_info = video_info

            st.markdown(f"**Video-ID:** `{video_info['video_id']}`")
            st.markdown("**Gefundener Stream-Link:**")
            st.code(video_info['stream_url'], language='text')

        else:
            st.error(video_info["message"])
            st.session_state.video_info = None
    else:
        st.warning("Bitte geben Sie eine URL ein.")

# --- Download Button ---
if 'video_info' in st.session_state and st.session_state.video_info:
    video_info = st.session_state.video_info
    st.markdown("---")
    
    file_name = f"video_{video_info['video_id']}.mp4"
    
    download_video(video_info['stream_url'], file_name)
