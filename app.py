import streamlit as st
import requests
from bs4 import BeautifulSoup

# Function to extract the video URL from a Nanoo.tv page
def get_video_url(page_url):
    try:
        # Get the page content
        response = requests.get(page_url)
        response.raise_for_status()

        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the video source link (you might need to inspect the actual HTML structure)
        video_tag = soup.find('video')
        if video_tag:
            video_url = video_tag['src']
            return video_url
        else:
            # Fallback to searching through known attributes if not in a <video> tag
            # e.g., looking for .mp4 files in all links
            video_link = soup.find('a', href=True, string='.mp4')
            if video_link:
                return video_link['href']
            else:
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
