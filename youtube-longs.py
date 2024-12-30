from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz
from pydantic import BaseModel
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
import textwrap
import csv
import os
from dotenv import load_dotenv

load_dotenv()
# Get API keys from the environment
api_key = os.getenv("YOUTUBE_READ_KEY")
gemini_key = os.getenv("GEMINI_KEY")

youtube = build('youtube', 'v3', developerKey=api_key)

class topics(BaseModel):
    topic1: str
    topic2: str
    topic3: str
    topic4: str
    topic5: str
    topic6: str
    topic7: str

channels = [
    {"name": "Daniel Iles", "id": "UCXl0djQ2IljcG-shgv-hIEA"},
    {"name": "Erika2", "id": "UC-XDksokwZfLwnYNULNOeEg"},
    {"name": "Humphrey Yang", "id": "UCiFpmeoDVc3O01LnrKW9VcQ"},
    {"name": "Legacy Investing Show", "id": "UCJbOZAqwsdna6kjBZ0UcJmw"},
    {"name": "Nick Talks Money", "id": "UC8i8OTwJW7vXjfcfd6PVPLQ"},
    {"name": "Nischa", "id": "UCQpPo9BNwezg54N9hMFQp6Q"},
    {"name": "Sean Loves Real Estate", "id": "UCxTnM9iMhQnTLUvGcwsgaEQ"},
    {"name": "The Finance Engineer", "id": "UCjNmQ6frYwP0WDE7GJrn_WA"},
    {"name": "Finance with Sharan", "id": "UCBI57iTXtmJoaI6Ht7MgcfA"},
    {"name": "Ankur Warikoo", "id": "UCRzYN32xtBf3Yxsx5BvJWJw"},
    {"name": "Mark Tilbury", "id": "UCxgAuX3XZROujMmGphN_scA"},
    {"name": "Cara Chanaranade", "id": "UCD-qZSqFPqyx43L6gAR8qfQ"},
    {"name": "Pranjal Kamra", "id": "UCNXapAc8mXTwW82MTncdfzQ"},
    {"name": "Graham Stephan", "id": "UCa-ckhlKL98F8YXKQ-BALiw"},
    {"name": "Andrei Jikh", "id": "UCGy7SkBjcIAgTiwkXEtPnYg"},
    {"name": "Money Guy Show", "id": "UC9vUu4vlIlMC0dHQCTvQPbg"},
    {"name": "Erin Talks Money", "id": "UCpXipTyhIY9kprpvVd-lu0A"},
    {"name": "Parallel Wealth", "id": "UCwY3ZvNc_qCU-WuIKh-aulA"},
    {"name": "Steph and Den", "id": "UC_vOw_uMG0TBad8PxOD-R2w"}
]

def get_recent_videos_with_stats(channel_id, channel_name, max_results=10):
    # Convert channel ID to uploads playlist ID
    if channel_id.startswith('UC'):
        uploads_playlist_id = 'UU' + channel_id[2:]  # Using UU prefix for regular uploads
    else:
        raise ValueError("Invalid channel ID format. Must start with 'UC'")
    
    # Calculate date one month ago
    one_month_ago = datetime.now(pytz.UTC) - timedelta(days=30)
    
    try:
        videos = []
        request = youtube.playlistItems().list(
            part='snippet,contentDetails',
            playlistId=uploads_playlist_id,
            maxResults=50
        )
        
        while request and len(videos) < max_results:
            response = request.execute()
            
            for item in response['items']:
                published_at = datetime.strptime(
                    item['snippet']['publishedAt'], 
                    '%Y-%m-%dT%H:%M:%SZ'
                ).replace(tzinfo=pytz.UTC)
                
                if published_at < one_month_ago:
                    continue
                
                video_id = item['snippet']['resourceId']['videoId']
                
                # Get video details including duration
                video_response = youtube.videos().list(
                    part='statistics,contentDetails',
                    id=video_id
                ).execute()
                
                if video_response['items']:
                    video_details = video_response['items'][0]
                    duration = video_details['contentDetails']['duration']
                    
                    # Skip shorts (typically less than 60 seconds)
                    if 'M' not in duration and int(duration.replace('PT', '').replace('S', '')) < 60:
                        continue
                    
                    statistics = video_details['statistics']
                    
                    video = {
                        'channel': channel_name,
                        'title': item['snippet']['title'],
                        'url': f'https://www.youtube.com/watch?v={video_id}',
                        'view_count': int(statistics.get('viewCount', 0)),
                        'like_count': int(statistics.get('likeCount', 0)),
                        'duration': duration
                    }
                    videos.append(video)
                    
                    if len(videos) >= max_results:
                        break
            
            request = youtube.playlistItems().list_next(request, response)
            if not request or published_at < one_month_ago:
                break
                
        videos.sort(key=lambda x: x['view_count'], reverse=True)
        return videos
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("Channel ID:", channel_id)
        return []

# Collect videos from all channels
videos = []
for channel in channels:
    channel_videos = get_recent_videos_with_stats(channel['id'], channel['name'])
    videos.extend(channel_videos)

# Sort all videos by view count
videos.sort(key=lambda x: x['view_count'], reverse=True)
top_10_videos = videos[:10]

# Create a client for Gemini
client = genai.Client(api_key=gemini_key)

key_topics = client.models.generate_content(
    model='gemini-2.0-flash-exp',
    contents="The following are the 10 top personal finance related Youtube videos from the past month. Please identify common themes and come up with 7 key topics that are discussed in these videos: \n\n" + 
    "\n\n".join([video['title'] for video in top_10_videos]),
    config=types.GenerateContentConfig(response_mime_type='application/json', response_schema=topics, temperature=0.5)
)

# Date range calculation
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
date_range = f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"

def create_videos_visualization(top_10_videos, key_topics):
# Set up image dimensions
    WIDTH = 2000
    MARGIN = 80
    BAR_HEIGHT = 40
    MAX_BAR_WIDTH = 1000
    
    # Colors
    BLUE = '#0066CC'
    DARK_GRAY = '#1a1a1a'
    GRAY = '#404040'

    # Load fonts
    title_font = ImageFont.truetype("./Helvetica-Bold.ttf", 60)
    header_font = ImageFont.truetype("./Helvetica.ttf", 40)
    body_font = ImageFont.truetype("./Helvetica.ttf", 30)
    channel_font = ImageFont.truetype("./Helvetica.ttf", 26)

    # Calculate required height
    y = MARGIN

    # Space for title and date
    y += 80  # Title
    y += 90  # Date

    # Space for topics
    topics_list = list(key_topics.parsed.dict().values())
    topics_text = ", ".join(topics_list)
    wrapped_topics = textwrap.fill(topics_text, width=120)
    topics_lines = wrapped_topics.count('\n') + 1
    y += 60  # "Trending Topics" header
    y += (topics_lines * 40) + 60

    # Space for videos header
    y += 80

    # Calculate space needed for videos
    for video in top_10_videos:
        wrapped_title = textwrap.fill(video['title'], width=85)
        title_lines = wrapped_title.count('\n') + 1
        y += BAR_HEIGHT + 50 + (title_lines * 35) + 30

    # Add final margin
    HEIGHT = y + MARGIN

    # Create image
    img = Image.new('RGB', (WIDTH, HEIGHT), (250, 250, 250))
    draw = ImageDraw.Draw(img)

    # Reset y for actual drawing
    y = MARGIN

    # Draw title and date range
    draw.text((MARGIN, y), "Trending YouTube Videos - Personal Finance", font=title_font, fill=DARK_GRAY)
    y += 80

    draw.text((MARGIN, y), date_range, font=header_font, fill=GRAY)
    y += 90

    # Draw key topics in a single line
    draw.text((MARGIN, y), "Trending Topics:", font=header_font, fill=GRAY)
    y += 60
    draw.text((MARGIN, y), wrapped_topics, font=body_font, fill=BLUE)
    y += (topics_lines * 40) + 60

    # Draw top videos section
    draw.text((MARGIN, y), "Most Viewed Videos This Month:", font=header_font, fill=GRAY)
    y += 80

    # Find maximum views for scaling
    max_views = max(video['view_count'] for video in top_10_videos)

    # Draw bars and titles
    for i, video in enumerate(top_10_videos, 1):
        # Calculate bar width
        bar_width = int((video['view_count'] / max_views) * MAX_BAR_WIDTH)
        
        # Draw rank number
        draw.text((MARGIN - 50, y + 5), f"{i}.", font=body_font, fill=GRAY)
        
        # Draw bar with YouTube red gradient
        for x in range(bar_width):
            # Create a gradient from YouTube red to lighter red
            color = (
                min(255, int(255 - (x/bar_width) * 40)),
                min(0, int(0 + (x/bar_width) * 20)),
                min(0, int(0 + (x/bar_width) * 20))
            )
            draw.line([(MARGIN + x, y), (MARGIN + x, y + BAR_HEIGHT)], fill=color)
        
        # Draw view count
        view_count = f"{video['view_count']:,} views"
        draw.text((MARGIN + bar_width + 15, y + 5), view_count, font=body_font, fill=GRAY)
        
        # Wrap and draw title in blue
        wrapped_title = textwrap.fill(video['title'], width=85)
        draw.text((MARGIN, y + BAR_HEIGHT + 10), wrapped_title, font=body_font, fill=BLUE)
        
        # Draw channel info
        channel_text = f"posted by {video['channel']}"
        title_lines = wrapped_title.count('\n') + 1
        channel_y = y + BAR_HEIGHT + 15 + (title_lines * 35)
        draw.text((MARGIN, channel_y), channel_text, font=channel_font, fill=GRAY)
        
        # Calculate space for next entry
        y += BAR_HEIGHT + 50 + (title_lines * 35) + 30

    return img

# Create and save the visualization
viz = create_videos_visualization(top_10_videos, key_topics)
viz.save('youtube_videos_trends.png', dpi=(300, 300))

# Save all videos data to a CSV file
data = [[date_range], ['channel', 'title', 'url', 'view_count', 'like_count', 'duration']]
data.extend([
    video['channel'], 
    video['title'], 
    video['url'], 
    video['view_count'], 
    video['like_count'],
    video['duration']
] for video in videos)

with open('videos.csv', 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerows(data)
