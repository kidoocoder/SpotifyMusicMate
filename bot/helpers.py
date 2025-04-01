import logging
import re
import asyncio
import html
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def format_duration(milliseconds):
    """Format duration from milliseconds to MM:SS format."""
    seconds = int(milliseconds / 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

def format_time(timestamp):
    """Format a Unix timestamp to a readable time."""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%H:%M:%S")

def format_date(timestamp):
    """Format a Unix timestamp to a readable date."""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def escape_markdown(text):
    """Escape markdown characters in a text string."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

def extract_user_and_text(message):
    """Extract user ID and text from a message."""
    user_id = None
    text = None
    
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id
        text = message.text.split(" ", 1)[1] if len(message.text.split(" ", 1)) > 1 else ""
    else:
        entities = message.entities if hasattr(message, 'entities') else []
        text = message.text or message.caption or ""
        
        for entity in entities:
            if entity.type == "text_mention":
                user_id = entity.user.id
            elif entity.type == "mention":
                username = text[entity.offset + 1:entity.offset + entity.length]
                # In real implementation, you'd need to resolve username to ID
        
        if not user_id and len(text.split(" ", 1)) > 1:
            text = text.split(" ", 1)[1]
    
    return user_id, text

def create_progress_bar(current, total, length=10):
    """Create a text-based progress bar."""
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '░' * (length - filled_length)
    return bar

async def get_readable_time(seconds):
    """Get human-readable time from seconds."""
    count = 0
    up_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    
    for i in range(len(time_list)):
        time_list[i] = str(time_list[i]) + time_suffix_list[i]
    
    if len(time_list) == 4:
        up_time += f"{time_list.pop()}, "
    
    time_list.reverse()
    up_time += ":".join(time_list)
    
    return up_time

def clean_html(raw_html):
    """Remove HTML tags from a string."""
    cleanr = re.compile('<.*?>')
    clean_text = re.sub(cleanr, '', raw_html)
    return html.unescape(clean_text)

async def rate_limiter(user_id, command, limit=3, time_window=10):
    """Rate limiter for commands."""
    # This is a simple in-memory rate limiter
    if not hasattr(rate_limiter, "usage"):
        rate_limiter.usage = {}
    
    key = f"{user_id}:{command}"
    current_time = datetime.now()
    
    # Initialize or clean up old entries
    if key not in rate_limiter.usage:
        rate_limiter.usage[key] = []
    else:
        # Remove entries older than time_window
        rate_limiter.usage[key] = [t for t in rate_limiter.usage[key] 
                                 if current_time - t < timedelta(seconds=time_window)]
    
    # Check if limit reached
    if len(rate_limiter.usage[key]) >= limit:
        return False
    
    # Add new usage
    rate_limiter.usage[key].append(current_time)
    return True

async def is_admin(client, chat_id, user_id, include_creator=True):
    """Check if a user is an admin in a chat."""
    try:
        chat_member = await client.get_chat_member(chat_id, user_id)
        
        # Define admin statuses based on include_creator flag
        admin_statuses = ['administrator']
        if include_creator:
            admin_statuses.append('creator')
        
        return chat_member.status in admin_statuses
    except Exception as e:
        logger.error(f"Error checking admin status: {e}", exc_info=True)
        return False
