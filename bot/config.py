import os
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class UserConfig:
    """Configuration class for individual users."""
    
    user_id: int
    preferred_volume: int = 100
    preferred_quality: str = "medium"  # low, medium, high
    favorite_tracks: List[str] = field(default_factory=list)
    language: str = "en"
    notifications_enabled: bool = True
    last_active: int = 0  # Unix timestamp
    
    def to_dict(self):
        """Convert the user config to a dictionary."""
        return {
            "user_id": self.user_id,
            "preferred_volume": self.preferred_volume,
            "preferred_quality": self.preferred_quality,
            "favorite_tracks": self.favorite_tracks,
            "language": self.language,
            "notifications_enabled": self.notifications_enabled,
            "last_active": self.last_active
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create a UserConfig from a dictionary."""
        return cls(
            user_id=data.get("user_id", 0),
            preferred_volume=data.get("preferred_volume", 100),
            preferred_quality=data.get("preferred_quality", "medium"),
            favorite_tracks=data.get("favorite_tracks", []),
            language=data.get("language", "en"),
            notifications_enabled=data.get("notifications_enabled", True),
            last_active=data.get("last_active", 0)
        )

@dataclass
class ChatConfig:
    """Configuration class for individual chats."""
    
    chat_id: int
    default_volume: int = 100
    auto_play_next: bool = True
    allowed_users: List[int] = field(default_factory=list)  # Empty list means all users allowed
    banned_users: List[int] = field(default_factory=list)
    admin_only_controls: bool = False
    last_active: int = 0  # Unix timestamp
    
    def to_dict(self):
        """Convert the chat config to a dictionary."""
        return {
            "chat_id": self.chat_id,
            "default_volume": self.default_volume,
            "auto_play_next": self.auto_play_next,
            "allowed_users": self.allowed_users,
            "banned_users": self.banned_users,
            "admin_only_controls": self.admin_only_controls,
            "last_active": self.last_active
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create a ChatConfig from a dictionary."""
        return cls(
            chat_id=data.get("chat_id", 0),
            default_volume=data.get("default_volume", 100),
            auto_play_next=data.get("auto_play_next", True),
            allowed_users=data.get("allowed_users", []),
            banned_users=data.get("banned_users", []),
            admin_only_controls=data.get("admin_only_controls", False),
            last_active=data.get("last_active", 0)
        )

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
    
    # Genius API credentials for lyrics (optional)
    GENIUS_API_TOKEN: str = os.getenv("GENIUS_API_TOKEN", "")
    
    # MongoDB connection string (optional)
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/music_bot")
    
    # Bot settings
    DURATION_LIMIT: int = int(os.getenv("DURATION_LIMIT", "180"))  # Max duration in minutes
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "/")
    
    # Cache directory for downloaded songs
    CACHE_DIR: str = os.getenv("CACHE_DIR", "cache")
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    
    # Admin user IDs (comma-separated)
    ADMIN_IDS: List[int] = field(default_factory=lambda: [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()])
    
    # Default volume level (0-200)
    DEFAULT_VOLUME: int = int(os.getenv("DEFAULT_VOLUME", "100"))
    
    # Owner information and update channel
    OWNER_USERNAME: str = os.getenv("OWNER_USERNAME", "")
    OWNER_NAME: str = os.getenv("OWNER_NAME", "Bot Owner")
    OWNER_URL: str = os.getenv("OWNER_URL", "")
    UPDATES_CHANNEL: str = os.getenv("UPDATES_CHANNEL", "")
    UPDATES_CHANNEL_URL: str = os.getenv("UPDATES_CHANNEL_URL", "")
    
    # User and chat configs
    user_configs: Dict[int, UserConfig] = field(default_factory=dict)
    chat_configs: Dict[int, ChatConfig] = field(default_factory=dict)
    
    def __post_init__(self):
        """Create necessary directories and load saved configurations."""
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        os.makedirs(self.DATA_DIR, exist_ok=True)
        
        # Load saved user and chat configurations
        self.load_user_configs()
        self.load_chat_configs()
    
    def get_user_config(self, user_id: int) -> UserConfig:
        """Get configuration for a specific user. Creates new config if not exists."""
        if user_id not in self.user_configs:
            self.user_configs[user_id] = UserConfig(user_id=user_id)
            self.save_user_configs()
        return self.user_configs[user_id]
    
    def update_user_config(self, user_id: int, **kwargs) -> UserConfig:
        """Update configuration for a specific user."""
        if user_id not in self.user_configs:
            self.user_configs[user_id] = UserConfig(user_id=user_id)
        
        user_config = self.user_configs[user_id]
        for key, value in kwargs.items():
            if hasattr(user_config, key):
                setattr(user_config, key, value)
        
        self.save_user_configs()
        return user_config
    
    def get_chat_config(self, chat_id: int) -> ChatConfig:
        """Get configuration for a specific chat. Creates new config if not exists."""
        if chat_id not in self.chat_configs:
            self.chat_configs[chat_id] = ChatConfig(chat_id=chat_id)
            self.save_chat_configs()
        return self.chat_configs[chat_id]
    
    def update_chat_config(self, chat_id: int, **kwargs) -> ChatConfig:
        """Update configuration for a specific chat."""
        if chat_id not in self.chat_configs:
            self.chat_configs[chat_id] = ChatConfig(chat_id=chat_id)
        
        chat_config = self.chat_configs[chat_id]
        for key, value in kwargs.items():
            if hasattr(chat_config, key):
                setattr(chat_config, key, value)
        
        self.save_chat_configs()
        return chat_config
    
    def load_user_configs(self):
        """Load user configurations from file."""
        user_config_path = os.path.join(self.DATA_DIR, "user_configs.json")
        if os.path.exists(user_config_path):
            try:
                with open(user_config_path, "r") as f:
                    user_configs_data = json.load(f)
                
                for user_id_str, config_data in user_configs_data.items():
                    user_id = int(user_id_str)
                    self.user_configs[user_id] = UserConfig.from_dict(config_data)
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                print(f"Error loading user configs: {e}")
    
    def save_user_configs(self):
        """Save user configurations to file."""
        user_config_path = os.path.join(self.DATA_DIR, "user_configs.json")
        try:
            user_configs_data = {str(user_id): config.to_dict() for user_id, config in self.user_configs.items()}
            with open(user_config_path, "w") as f:
                json.dump(user_configs_data, f, indent=2)
        except Exception as e:
            print(f"Error saving user configs: {e}")
    
    def load_chat_configs(self):
        """Load chat configurations from file."""
        chat_config_path = os.path.join(self.DATA_DIR, "chat_configs.json")
        if os.path.exists(chat_config_path):
            try:
                with open(chat_config_path, "r") as f:
                    chat_configs_data = json.load(f)
                
                for chat_id_str, config_data in chat_configs_data.items():
                    chat_id = int(chat_id_str)
                    self.chat_configs[chat_id] = ChatConfig.from_dict(config_data)
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                print(f"Error loading chat configs: {e}")
    
    def save_chat_configs(self):
        """Save chat configurations to file."""
        chat_config_path = os.path.join(self.DATA_DIR, "chat_configs.json")
        try:
            chat_configs_data = {str(chat_id): config.to_dict() for chat_id, config in self.chat_configs.items()}
            with open(chat_config_path, "w") as f:
                json.dump(chat_configs_data, f, indent=2)
        except Exception as e:
            print(f"Error saving chat configs: {e}")
