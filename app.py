import streamlit as st
import subprocess
import os
import io

def download_video_with_yt_dlp(video_url: str):
    """
    Uses the powerful yt-dlp library to download video from a given URL.
    This function will show the download progress in the Streamlit interface.

    Args:
        video_url (str): The URL of the video page to download.
    """
    st.write("🚀 Starting video download process...")
    
    # Define a temporary path for the downloaded file
    # We use a sub-directory to keep things tidy.
    temp_dir = "temp_downloads"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    # We'll use the video's ID as the filename to avoid special characters
    output_template = os.path.join(temp_dir, "%(id)s.%(ext)s")
    
    # Construct the yt-dlp command
    # -o: specifies the output template
    # -f 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best': tells yt-dlp to find the best quality MP4 video and audio, or the best single MP4 file if separate streams aren't available.
    command = [
        "yt-dlp",
        "-f",
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_template,
        video_url
    ]
    
    st.markdown("**Executing Command:**")
    st.code(" ".join(command))
    
    progress_bar_placeholder = st.empty()
    status_text_placeholder = st.empty()
    
    # Run the command as a subprocess
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    
    # Read the output line by line to show progress
    for line in iter(process.stdout.readline, ""):
        st.text(line.strip()) # Show the raw output from yt-dlp
        if "[download]" in line and "%" in line:
            try:
                # Extract percentage from yt-dlp's output
                progress_str = line.split('%')[0].split()[-1]
                progress = int(float(progress_str))
                progress_bar_placeholder.progress(progress)
                status_text_placeholder.info(f"Downloading... {progress}%")
            except (ValueError, IndexError):
                # Ignore lines that don't have a clear percentage
                pass
    
    process.wait() # Wait for the download to complete
    
    if process.returncode == 0:
        status_text_placeholder.success("✅ Download and processing complete!")
        
        # Find the downloaded file
        try:
            downloaded_file = max([os.path.join(temp_dir, f) for f in os.listdir(temp_dir)], key=os.path.getctime)
            file_name = os.path.basename(downloaded_file)

            st.markdown("---")
            st.write("Your video is ready for download:")

            with open(downloaded_file, "rb") as fp:
                st.download_button(
                    label=f"⬇️ Download {file_name}",
                    data=fp,
                    file_name=file_name,
                    mime="video/mp4"
                )
            # Clean up the temp file
            os.remove(downloaded_file)
        except (ValueError, FileNotFoundError):
             st.error("Could not find the downloaded file after processing.")

    else:
        status_text_placeholder.error("❌ An error occurred during the download process. See logs above for details.")


def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(page_title="Universal Video Downloader", page_icon="💾", layout="centered")

    st.title("Universal Video Downloader")
    st.write("This app uses the powerful `yt-dlp` library to download videos from a wide variety of websites, including those using M3U8 streams.")

    with st.expander("Instructions & Supported Sites"):
        st.markdown("""
        1.  **Paste URL:** Enter the URL of the page containing the video (e.g., the SRF Play page, a YouTube link, etc.).
        2.  **Click Download:** The app will call `yt-dlp` in the background. You will see the live output from the tool.
        3.  **Be Patient:** Downloading and merging video can take several minutes depending on the video length and quality.
        4.  **Save:** Once complete, a download button for the final `.mp4` file will appear.
        
        This tool supports hundreds of websites. You can check the full list on the [yt-dlp supported sites page](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).
        """)

    url_input = st.text_input("Enter the video page URL:", value="https://www.srf.ch/play/embed?urn=urn:srf:video:5b477667-1d20-414d-8ab0-2d0f6ac565a1")

    if st.button("Download Video", type="primary"):
        if url_input:
            download_video_with_yt_dlp(url_input)
        else:
            st.warning("Please enter a URL.")

if __name__ == "__main__":
    main()
