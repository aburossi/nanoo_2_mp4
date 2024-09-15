import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

# Function to extract the video URL from the Nanoo.tv page
def get_video_url(page_url):
    try:
        # Fetch the page content
        response = requests.get(page_url)
        response.raise_for_status()

        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')

        # Search for any mp4 file in the HTML
        # Use a regex to match .mp4 URLs with possible tokens
        mp4_pattern = re.compile(r'https:\/\/http\.nanoo\.tv\/mediacontent\/export\/\d+\/\d+_stream_hi\.mp4\?st=[a-zA-Z0-9]+&e=\d+')
        script_tags = soup.find_all('script')

        # Search through all script tags to find the video link
        for script in script_tags:
            if script.string:
                video_url_match = mp4_pattern.search(script.string)
                if video_url_match:
                    return video_url_match.group(0)  # Return the first match

        # If no match is found, return None
        return None

    except Exception as e:
        st.error(f"Error occurred: {e}")
        return None

# Streamlit UI to accept user input
st.title('Nanoo.tv Video Downloader')

# Input field for Nanoo.tv video page URL
page_url = st.text_input('Enter Nanoo.tv video page URL', '')

if st.button('Find and Download MP4'):
    if page_url:
        # Fetch the correct video URL
        video_url = get_video_url(page_url)
        
        if video_url:
            st.success(f"Found video URL: {video_url}")

            # Offer to download the video
            try:
                response = requests.get(video_url, stream=True)
                video_path = "/tmp/video.mp4"
                
                # Save the video file
                with open(video_path, 'wb') as video_file:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            video_file.write(chunk)

                # Provide a download button for the user
                with open(video_path, 'rb') as file:
                    st.download_button(
                        label="Download MP4",
                        data=file,
                        file_name="video.mp4",
                        mime="video/mp4"
                    )
            except Exception as e:
                st.error(f"Error downloading video: {e}")
        else:
            st.error("Could not find the video URL.")
    else:
        st.warning("Please enter a valid Nanoo.tv video page URL.")
