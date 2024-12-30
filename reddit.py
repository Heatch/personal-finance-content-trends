import praw
from google import genai
from google.genai import types
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
import textwrap
from dotenv import load_dotenv
import os


load_dotenv()
# Get API keys from the environment
client_id = os.getenv("REDDIT_CLIENT_ID")
client_secret = os.getenv("REDDIT_CLIENT_SECRET")
gemini_key = os.getenv("GEMINI_KEY")

reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent="windows:trends-script:v1.0 (by /u/bitesh9)",
)

class topics(BaseModel):
    topic1: str
    topic2: str
    topic3: str
    topic4: str
    topic5: str
    topic6: str
    topic7: str

subs = [
    "personalfinance", 
    "PersonalFinanceCanada", 
    "investing", 
    "stocks", 
    "Fire", 
    "fatFIRE", 
    "FinancialPlanning", 
    "Money",              
    "leanfire",          
    "financialindependence", 
    "Frugal",           
    "CanadianInvestor",  
    "ValueInvesting"     
]

posts = []

for sub in subs:
    for submission in reddit.subreddit(sub).top(time_filter="week", limit=10):
        post = {
            "subreddit": submission.subreddit.display_name,
            "title": submission.title,
            "url": submission.url,
            "body": submission.selftext,
            "score": submission.score,
        }
        posts.append(post)


# Sort posts by score in descending order
sorted_posts = sorted(posts, key=lambda x: x['score'], reverse=True)
top_10 = sorted_posts[:10]

# Create a client for Gemini
client = genai.Client(api_key=gemini_key)

key_topics = client.models.generate_content(model='gemini-2.0-flash-exp', contents="The following are the 10 of the top posts personal finance related posts from the past week on Reddit. Please, identify common themes and come up with 7 key topics that are discussed in these posts: \n\n" + "\n\n".join([post['title'] + "\n" + post['body'] for post in top_10]), config=types.GenerateContentConfig(response_mime_type='application/json', response_schema=topics, temperature=0.5))

def create_trends_visualization(top_10, key_topics):
    # Set up image dimensions
    WIDTH = 2000
    MARGIN = 80
    BAR_HEIGHT = 40
    BAR_SPACING = 30
    MAX_BAR_WIDTH = 1000
    
    # Colors
    BLUE = '#0066CC'
    DARK_GRAY = '#1a1a1a'
    GRAY = '#404040'

    # Load fonts

    title_font = ImageFont.truetype("./Helvetica-Bold.ttf", 60)
    header_font = ImageFont.truetype("./Helvetica.ttf", 40)
    body_font = ImageFont.truetype("./Helvetica.ttf", 30)
    subreddit_font = ImageFont.truetype("./Helvetica.ttf", 26) 

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
    y += (topics_lines * 40) + 60  # Topics text + spacing

    # Space for posts header
    y += 80

    # Calculate space needed for posts
    for post in top_10:
        wrapped_title = textwrap.fill(post['title'], width=85)
        title_lines = wrapped_title.count('\n') + 1
        y += BAR_HEIGHT + 50 + (title_lines * 35) + 30  # Added extra space for subreddit

    # Add final margin
    HEIGHT = y + MARGIN

    # Create image
    img = Image.new('RGB', (WIDTH, HEIGHT), (250, 250, 250))
    draw = ImageDraw.Draw(img)

    # Reset y for actual drawing
    y = MARGIN

    # Draw title and date range
    draw.text((MARGIN, y), "Reddit Personal Finance Trends", font=title_font, fill=DARK_GRAY)
    y += 80

    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    date_range = f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"
    draw.text((MARGIN, y), date_range, font=header_font, fill=GRAY)
    y += 90

    # Draw key topics in a single line
    draw.text((MARGIN, y), "Trending Topics:", font=header_font, fill=GRAY)
    y += 60
    draw.text((MARGIN, y), wrapped_topics, font=body_font, fill=BLUE)  # Topics in blue
    y += (topics_lines * 40) + 60

    # Draw top posts section
    draw.text((MARGIN, y), "Most Popular Posts This Week:", font=header_font, fill=GRAY)
    y += 80

    # Find maximum score for scaling
    max_score = max(post['score'] for post in top_10)

    # Draw bars and titles
    for i, post in enumerate(top_10, 1):
        # Calculate bar width
        bar_width = int((post['score'] / max_score) * MAX_BAR_WIDTH)
        
        # Draw rank number
        draw.text((MARGIN - 50, y + 5), f"{i}.", font=body_font, fill=GRAY)
        
        # Draw bar with gradient effect
        for x in range(bar_width):
            color = (
                min(255, int(255 - (x/bar_width) * 40)),
                min(128, int(69 - (x/bar_width) * 20)),
                min(0, int(0 + (x/bar_width) * 10))
            )
            draw.line([(MARGIN + x, y), (MARGIN + x, y + BAR_HEIGHT)], fill=color)
        
        # Draw score
        score_text = f"{post['score']:,}"
        score_width = draw.textlength(score_text, font=body_font)
        draw.text((MARGIN + bar_width + 15, y + 5), score_text, font=body_font, fill=GRAY)
        
        # Wrap and draw title in blue
        wrapped_title = textwrap.fill(post['title'], width=85)
        draw.text((MARGIN, y + BAR_HEIGHT + 10), wrapped_title, font=body_font, fill=BLUE)
        
        # Draw subreddit info
        subreddit_text = f"posted on r/{post['subreddit']}"
        title_lines = wrapped_title.count('\n') + 1
        subreddit_y = y + BAR_HEIGHT + 15 + (title_lines * 35)
        draw.text((MARGIN, subreddit_y), subreddit_text, font=subreddit_font, fill=GRAY)
        
        # Calculate space for next entry
        y += BAR_HEIGHT + 50 + (title_lines * 35) + 30  # Added extra space for subreddit

    return img

# Create and save the visualization
viz = create_trends_visualization(top_10, key_topics)
viz.save('reddit_trends.png', dpi=(300, 300))
