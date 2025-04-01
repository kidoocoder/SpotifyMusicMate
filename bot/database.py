import asyncio
import logging
import os
import json
import time
from typing import Dict, List, Optional, Union, Any
from motor.motor_asyncio import AsyncIOMotorClient

from bot.config import UserConfig, ChatConfig

logger = logging.getLogger(__name__)

class Database:
    """Database handler for the bot."""
    
    def __init__(self, config=None):
        self.config = config
        self.mongo_uri = os.getenv("MONGO_URI", "")
        self.client = None
        self.db = None
        self.connected = False
        
        # Fallback to file-based storage if MongoDB URI not provided
        self.fallback_dir = "data"
        os.makedirs(self.fallback_dir, exist_ok=True)
        
        # Caching for faster operations
        self._cache = {
            "user_config": {},  # user_id -> config
            "chat_config": {},  # chat_id -> config 
            "user_favorites": {},  # user_id -> favorites
            "top_tracks": {},  # chat_id -> top tracks
        }
        self._cache_ttl = {
            "user_config": 300,  # 5 minutes
            "chat_config": 300,  # 5 minutes
            "user_favorites": 120,  # 2 minutes
            "top_tracks": 180,  # 3 minutes
        }
        self._cache_timestamps = {
            "user_config": {},
            "chat_config": {},
            "user_favorites": {},
            "top_tracks": {},
        }
        
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
    
    def _is_cache_valid(self, cache_type, key):
        """Check if a cache entry is valid (not expired)."""
        if key not in self._cache_timestamps.get(cache_type, {}):
            return False
        
        timestamp = self._cache_timestamps[cache_type][key]
        ttl = self._cache_ttl[cache_type]
        
        return (time.time() - timestamp) < ttl
    
    def _get_cache(self, cache_type, key):
        """Get a value from cache if it exists and is valid."""
        if self._is_cache_valid(cache_type, key):
            return self._cache[cache_type].get(key)
        return None
    
    def _set_cache(self, cache_type, key, value):
        """Set a value in the cache."""
        self._cache[cache_type][key] = value
        self._cache_timestamps[cache_type][key] = time.time()
        return value
    
    def _invalidate_cache(self, cache_type, key=None):
        """Invalidate a cache entry or an entire cache type."""
        if key is None:
            # Invalidate all entries of this type
            self._cache[cache_type] = {}
            self._cache_timestamps[cache_type] = {}
        else:
            # Invalidate just one key
            if key in self._cache[cache_type]:
                del self._cache[cache_type][key]
            if key in self._cache_timestamps[cache_type]:
                del self._cache_timestamps[cache_type][key]
    
    async def get_user_config(self, user_id: int) -> Dict[str, Any]:
        """Get user configuration from the database."""
        # Try cache first for fast response
        cached = self._get_cache("user_config", user_id)
        if cached:
            return cached
        
        # If not in cache, proceed with normal lookup
        if self.config:
            # Use the in-memory config if available
            user_config = self.config.get_user_config(user_id)
            result = user_config.to_dict()
            return self._set_cache("user_config", user_id, result)
        
        if self.connected:
            result = await self.db.user_configs.find_one({"user_id": user_id})
            if result:
                return self._set_cache("user_config", user_id, result)
        
        # Fallback to file-based storage
        file_data = await self._get_from_file(f"user_{user_id}", None)
        if file_data:
            return self._set_cache("user_config", user_id, file_data)
        
        # Return default user config
        default_config = UserConfig(user_id=user_id).to_dict()
        return self._set_cache("user_config", user_id, default_config)
    
    async def update_user_config(self, user_id: int, config_data: Dict[str, Any]) -> None:
        """Update user configuration in the database."""
        # Invalidate cache for this user_id
        self._invalidate_cache("user_config", user_id)
        
        if self.config:
            # Update the in-memory config
            self.config.update_user_config(user_id, **config_data)
            return
        
        if self.connected:
            await self.db.user_configs.update_one(
                {"user_id": user_id},
                {"$set": config_data},
                upsert=True
            )
        else:
            # Fallback to file storage
            current_data = await self.get_user_config(user_id)
            current_data.update(config_data)
            await self._save_to_file(f"user_{user_id}", current_data)
    
    async def get_chat_config(self, chat_id: int) -> Dict[str, Any]:
        """Get chat configuration from the database."""
        # Try cache first for fast response
        cached = self._get_cache("chat_config", chat_id)
        if cached:
            return cached
        
        # If not in cache, proceed with normal lookup
        if self.config:
            # Use the in-memory config if available
            chat_config = self.config.get_chat_config(chat_id)
            result = chat_config.to_dict()
            return self._set_cache("chat_config", chat_id, result)
        
        if self.connected:
            result = await self.db.chat_configs.find_one({"chat_id": chat_id})
            if result:
                return self._set_cache("chat_config", chat_id, result)
        
        # Fallback to file-based storage
        file_data = await self._get_from_file(f"chat_{chat_id}", None)
        if file_data:
            return self._set_cache("chat_config", chat_id, file_data)
        
        # Return default chat config
        default_config = ChatConfig(chat_id=chat_id).to_dict()
        return self._set_cache("chat_config", chat_id, default_config)
    
    async def update_chat_config(self, chat_id: int, config_data: Dict[str, Any]) -> None:
        """Update chat configuration in the database."""
        # Invalidate cache for this chat_id
        self._invalidate_cache("chat_config", chat_id)
        
        if self.config:
            # Update the in-memory config
            self.config.update_chat_config(chat_id, **config_data)
            return
        
        if self.connected:
            await self.db.chat_configs.update_one(
                {"chat_id": chat_id},
                {"$set": config_data},
                upsert=True
            )
        else:
            # Fallback to file storage
            current_data = await self.get_chat_config(chat_id)
            current_data.update(config_data)
            await self._save_to_file(f"chat_{chat_id}", current_data)
    
    async def add_user_favorite(self, user_id: int, track_id: str, track_info: Dict[str, Any]) -> None:
        """Add a track to user's favorites."""
        # Invalidate cache
        self._invalidate_cache("user_favorites", user_id)
        
        favorite_data = {
            "track_id": track_id,
            "name": track_info.get("name", "Unknown"),
            "artists": track_info.get("artists", []),
            "added_at": time.time()
        }
        
        if self.config:
            # Update in-memory config
            user_config = self.config.get_user_config(user_id)
            if track_id not in user_config.favorite_tracks:
                user_config.favorite_tracks.append(track_id)
                self.config.save_user_configs()
        
        if self.connected:
            # First, check if the track is already a favorite
            result = await self.db.user_favorites.find_one({
                "user_id": user_id,
                "track_id": track_id
            })
            
            if not result:
                # Add to favorites
                await self.db.user_favorites.insert_one({
                    "user_id": user_id,
                    "track_id": track_id,
                    "track_info": track_info,
                    "added_at": time.time()
                })
        else:
            # Fallback to file storage
            favorites = await self._get_from_file(f"favorites_{user_id}", {"user_id": user_id, "tracks": []})
            
            # Check if already a favorite
            if not any(track["track_id"] == track_id for track in favorites["tracks"]):
                favorites["tracks"].append(favorite_data)
                await self._save_to_file(f"favorites_{user_id}", favorites)
    
    async def remove_user_favorite(self, user_id: int, track_id: str) -> bool:
        """Remove a track from user's favorites. Returns True if successful."""
        # Invalidate cache
        self._invalidate_cache("user_favorites", user_id)
        
        if self.config:
            # Update in-memory config
            user_config = self.config.get_user_config(user_id)
            if track_id in user_config.favorite_tracks:
                user_config.favorite_tracks.remove(track_id)
                self.config.save_user_configs()
                return True
        
        if self.connected:
            result = await self.db.user_favorites.delete_one({
                "user_id": user_id,
                "track_id": track_id
            })
            return result.deleted_count > 0
        else:
            # Fallback to file storage
            favorites = await self._get_from_file(f"favorites_{user_id}", {"user_id": user_id, "tracks": []})
            
            original_length = len(favorites["tracks"])
            favorites["tracks"] = [track for track in favorites["tracks"] if track["track_id"] != track_id]
            
            if len(favorites["tracks"]) < original_length:
                await self._save_to_file(f"favorites_{user_id}", favorites)
                return True
            
            return False
    
    async def get_user_favorites(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get user's favorite tracks."""
        # Try cache first for fast response
        cache_key = f"{user_id}_{limit}"
        cached = self._get_cache("user_favorites", cache_key)
        if cached:
            return cached
            
        # If not in cache, proceed with normal lookup
        result = None
        
        if self.config:
            # Get from in-memory config
            user_config = self.config.get_user_config(user_id)
            # Note: This only returns IDs, not full track info
            result = [{"track_id": track_id} for track_id in user_config.favorite_tracks[:limit]]
        elif self.connected:
            cursor = self.db.user_favorites.find({"user_id": user_id}).sort("added_at", -1).limit(limit)
            result = await cursor.to_list(length=limit)
        else:
            # Fallback to file storage
            favorites = await self._get_from_file(f"favorites_{user_id}", {"user_id": user_id, "tracks": []})
            result = sorted(favorites["tracks"], key=lambda x: x.get("added_at", 0), reverse=True)[:limit]
            
        # Cache the result
        return self._set_cache("user_favorites", cache_key, result)
    
    async def add_played_track(self, chat_id: int, track_info: Dict[str, Any], user_id: Optional[int] = None) -> None:
        """Add a track to the played tracks history."""
        # Invalidate any cached top tracks for this chat since we're adding a new play
        self._invalidate_cache("top_tracks", None)  # Clear all top_tracks cache entries
        
        track_data = {
            "chat_id": chat_id,
            "track_id": track_info.get("id", "unknown"),
            "track_name": track_info.get("name", "Unknown"),
            "artists": track_info.get("artists", []),
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
    
    async def get_top_tracks(self, chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the top played tracks for a chat."""
        # Try cache first for fast response
        cache_key = f"{chat_id}_{limit}"
        cached = self._get_cache("top_tracks", cache_key)
        if cached:
            return cached
        
        # If not in cache, proceed with normal lookup
        result = None
        
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
            result = sorted(
                track_counts.values(),
                key=lambda x: (x["count"], x["last_played"]),
                reverse=True
            )[:limit]
        
        # Cache the result before returning
        return self._set_cache("top_tracks", cache_key, result)
    
    async def record_user_activity(self, user_id: int, action: str, chat_id: Optional[int] = None) -> None:
        """Record user activity for analytics."""
        activity = {
            "user_id": user_id,
            "action": action,
            "timestamp": time.time(),
            "chat_id": chat_id
        }
        
        if self.config:
            # Update last_active in the user config
            self.config.update_user_config(user_id, last_active=int(time.time()))
            if chat_id:
                self.config.update_chat_config(chat_id, last_active=int(time.time()))
        
        if self.connected:
            await self.db.user_activity.insert_one(activity)
        else:
            # We'll keep a simplified log in file-based storage
            activities = await self._get_from_file("user_activities", {"activities": []})
            activities["activities"].append(activity)
            
            # Limit size
            if len(activities["activities"]) > 1000:
                activities["activities"] = activities["activities"][-1000:]
            
            await self._save_to_file("user_activities", activities)
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get statistics for a specific user."""
        stats = {
            "total_plays": 0,
            "favorite_chats": [],
            "most_played_tracks": [],
            "first_seen": None,
            "last_active": None
        }
        
        if self.connected:
            # Count total plays
            stats["total_plays"] = await self.db.played_tracks.count_documents({"played_by": user_id})
            
            # Get favorite chats
            pipeline = [
                {"$match": {"played_by": user_id}},
                {"$group": {
                    "_id": "$chat_id",
                    "count": {"$sum": 1},
                    "last_played": {"$max": "$played_at"}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            stats["favorite_chats"] = await self.db.played_tracks.aggregate(pipeline).to_list(length=5)
            
            # Get most played tracks
            pipeline = [
                {"$match": {"played_by": user_id}},
                {"$group": {
                    "_id": "$track_id",
                    "name": {"$first": "$track_name"},
                    "artists": {"$first": "$artists"},
                    "count": {"$sum": 1},
                    "last_played": {"$max": "$played_at"}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            stats["most_played_tracks"] = await self.db.played_tracks.aggregate(pipeline).to_list(length=5)
            
            # Get first and last activity
            first = await self.db.user_activity.find({"user_id": user_id}).sort("timestamp", 1).limit(1).to_list(length=1)
            if first:
                stats["first_seen"] = first[0]["timestamp"]
            
            last = await self.db.user_activity.find({"user_id": user_id}).sort("timestamp", -1).limit(1).to_list(length=1)
            if last:
                stats["last_active"] = last[0]["timestamp"]
        else:
            # For file-based storage, we'll compute simplified stats
            user_config = await self.get_user_config(user_id)
            stats["last_active"] = user_config.get("last_active", 0)
            
            # Get activities
            activities = await self._get_from_file("user_activities", {"activities": []})
            user_activities = [a for a in activities["activities"] if a["user_id"] == user_id]
            
            if user_activities:
                stats["total_plays"] = len([a for a in user_activities if a["action"] == "play"])
                stats["first_seen"] = min(a["timestamp"] for a in user_activities)
                stats["last_active"] = max(a["timestamp"] for a in user_activities)
                
                # Count plays by chat
                chat_counts = {}
                for activity in user_activities:
                    if activity["action"] == "play" and activity.get("chat_id"):
                        chat_id = activity["chat_id"]
                        if chat_id not in chat_counts:
                            chat_counts[chat_id] = {"_id": chat_id, "count": 0, "last_played": 0}
                        chat_counts[chat_id]["count"] += 1
                        chat_counts[chat_id]["last_played"] = max(
                            chat_counts[chat_id]["last_played"],
                            activity["timestamp"]
                        )
                
                stats["favorite_chats"] = sorted(
                    chat_counts.values(),
                    key=lambda x: (x["count"], x["last_played"]),
                    reverse=True
                )[:5]
        
        return stats
    
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
