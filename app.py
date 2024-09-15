import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

# Function to extract video URL from Nanoo.tv page
def get_video_url(page_url):
    try:
        # Fetch the page content
        response = requests.get(page_url)
        response.raise_for_status()
        
        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check for a direct video URL in 'video' or 'source' tags
        video_tag = soup.find('video')
        if video_tag:
            source_tag = video_tag.find('source')
            if source_tag and 'src' in source_tag.attrs:
                return source_tag['src']

        # Search for any other <source> tags in the page
        source_tag = soup.find('source')
        if source_tag and 'src' in source_tag.attrs:
            return source_tag['src']

        # If there's an iframe, check if it's hosting a video
        iframe_tag = soup.find('iframe')
        if iframe_tag and 'src' in iframe_tag.attrs:
            iframe_url = iframe_tag['src']
            return get_video_url(iframe_url)  # Recursive call to handle iframes
        
        # Search in <script> tags for potential video URLs (e.g., sometimes embedded in JS)
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string:
                # Check if there's any mention of an .mp4 file in the script text
                mp4_match = re.search(r'https?://.*\.mp4', script.string)
                if mp4_match:
                    return mp4_match.group(0)
        
        # If nothing found, return None
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
                
                # Save video file
                with open(video_path, 'wb') as video_file:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            video_file.write(chunk)

                # Provide download button for the user
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
