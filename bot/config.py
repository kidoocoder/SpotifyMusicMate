import os
from dataclasses import dataclass, field
from typing import List

@dataclass
class Config:
    """Configuration class for the Telegram bot."""
    
    # Telegram API credentials
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "")
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Assistant session string for voice chats
    SESSION_STRING: str = os.getenv("SESSION_STRING", "")
    
    # Spotify API credentials
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    
    # MongoDB connection string (optional)
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/music_bot")
    
    # Bot settings
    DURATION_LIMIT: int = int(os.getenv("DURATION_LIMIT", "180"))  # Max duration in minutes
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "/")
    
    # Cache directory for downloaded songs
    CACHE_DIR: str = os.getenv("CACHE_DIR", "cache")
    
    # Admin user IDs (comma-separated)
    ADMIN_IDS: List[int] = field(default_factory=lambda: [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()])
    
    # Default volume level (0-200)
    DEFAULT_VOLUME: int = int(os.getenv("DEFAULT_VOLUME", "100"))
    
    def __post_init__(self):
        """Create cache directory if it doesn't exist."""
        os.makedirs(self.CACHE_DIR, exist_ok=True)
