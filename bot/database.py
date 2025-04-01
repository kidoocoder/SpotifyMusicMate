import asyncio
import logging
import os
import json
import time
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

class Database:
    """Database handler for the bot."""
    
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "")
        self.client = None
        self.db = None
        self.connected = False
        
        # Fallback to file-based storage if MongoDB URI not provided
        self.fallback_dir = "data"
        os.makedirs(self.fallback_dir, exist_ok=True)
        
        # Initialize connection
        asyncio.create_task(self.init_connection())
    
    async def init_connection(self):
        """Initialize the database connection."""
        if not self.mongo_uri:
            logger.info("MongoDB URI not provided, using file-based storage")
            self.connected = False
            return
        
        try:
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client.music_bot
            # Test connection
            await self.db.command("ping")
            self.connected = True
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
            self.connected = False
    
    async def get_user_settings(self, user_id):
        """Get user settings from the database."""
        if self.connected:
            result = await self.db.user_settings.find_one({"user_id": user_id})
            return result or {"user_id": user_id}
        else:
            return await self._get_from_file(f"user_{user_id}", {"user_id": user_id})
    
    async def update_user_settings(self, user_id, settings):
        """Update user settings in the database."""
        if self.connected:
            await self.db.user_settings.update_one(
                {"user_id": user_id},
                {"$set": settings},
                upsert=True
            )
        else:
            await self._save_to_file(f"user_{user_id}", settings)
    
    async def get_chat_settings(self, chat_id):
        """Get chat settings from the database."""
        if self.connected:
            result = await self.db.chat_settings.find_one({"chat_id": chat_id})
            return result or {"chat_id": chat_id}
        else:
            return await self._get_from_file(f"chat_{chat_id}", {"chat_id": chat_id})
    
    async def update_chat_settings(self, chat_id, settings):
        """Update chat settings in the database."""
        if self.connected:
            await self.db.chat_settings.update_one(
                {"chat_id": chat_id},
                {"$set": settings},
                upsert=True
            )
        else:
            await self._save_to_file(f"chat_{chat_id}", settings)
    
    async def add_played_track(self, chat_id, track_info, user_id=None):
        """Add a track to the played tracks history."""
        track_data = {
            "chat_id": chat_id,
            "track_id": track_info["id"],
            "track_name": track_info["name"],
            "artists": track_info["artists"],
            "played_at": time.time(),
            "played_by": user_id
        }
        
        if self.connected:
            await self.db.played_tracks.insert_one(track_data)
        else:
            # Get existing history
            history = await self._get_from_file(f"history_{chat_id}", {"chat_id": chat_id, "tracks": []})
            
            # Add new track
            history["tracks"].append(track_data)
            
            # Limit history size
            if len(history["tracks"]) > 100:
                history["tracks"] = history["tracks"][-100:]
            
            # Save updated history
            await self._save_to_file(f"history_{chat_id}", history)
    
    async def get_top_tracks(self, chat_id, limit=10):
        """Get the top played tracks for a chat."""
        if self.connected:
            pipeline = [
                {"$match": {"chat_id": chat_id}},
                {"$group": {
                    "_id": "$track_id",
                    "name": {"$first": "$track_name"},
                    "artists": {"$first": "$artists"},
                    "count": {"$sum": 1},
                    "last_played": {"$max": "$played_at"}
                }},
                {"$sort": {"count": -1, "last_played": -1}},
                {"$limit": limit}
            ]
            
            result = await self.db.played_tracks.aggregate(pipeline).to_list(length=limit)
            return result
        else:
            history = await self._get_from_file(f"history_{chat_id}", {"chat_id": chat_id, "tracks": []})
            
            # Count track occurrences
            track_counts = {}
            for track in history["tracks"]:
                track_id = track["track_id"]
                if track_id not in track_counts:
                    track_counts[track_id] = {
                        "_id": track_id,
                        "name": track["track_name"],
                        "artists": track["artists"],
                        "count": 0,
                        "last_played": 0
                    }
                
                track_counts[track_id]["count"] += 1
                track_counts[track_id]["last_played"] = max(
                    track_counts[track_id]["last_played"],
                    track.get("played_at", 0)
                )
            
            # Sort and limit
            top_tracks = sorted(
                track_counts.values(),
                key=lambda x: (x["count"], x["last_played"]),
                reverse=True
            )[:limit]
            
            return top_tracks
    
    async def _save_to_file(self, file_name, data):
        """Save data to a file."""
        file_path = os.path.join(self.fallback_dir, f"{file_name}.json")
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving data to file {file_path}: {e}", exc_info=True)
    
    async def _get_from_file(self, file_name, default=None):
        """Get data from a file."""
        file_path = os.path.join(self.fallback_dir, f"{file_name}.json")
        try:
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    return json.load(f)
            return default or {}
        except Exception as e:
            logger.error(f"Error reading data from file {file_path}: {e}", exc_info=True)
            return default or {}
    
    async def close(self):
        """Close the database connection."""
        if self.client:
            self.client.close()
