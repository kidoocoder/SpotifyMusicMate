"""Module for handling user playlists."""
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional
import uuid

from bot.database import Database

logger = logging.getLogger(__name__)

class PlaylistManager:
    """Manager for user playlists."""
    
    def __init__(self, database: Database):
        """
        Initialize the playlist manager.
        
        Args:
            database: Database instance for storing playlists.
        """
        self.database = database
        self.max_tracks_per_playlist = 100
        self.max_playlists_per_user = 10
    
    async def create_playlist(self, user_id: int, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new playlist for a user.
        
        Args:
            user_id: The Telegram user ID.
            name: The playlist name.
            description: Optional playlist description.
            
        Returns:
            The created playlist object.
        """
        # Check if user has reached the playlist limit
        user_playlists = await self.get_user_playlists(user_id)
        if len(user_playlists) >= self.max_playlists_per_user:
            raise ValueError(f"You can only create up to {self.max_playlists_per_user} playlists")
        
        # Create a unique ID for the playlist
        playlist_id = str(uuid.uuid4())
        
        # Create the playlist object
        playlist = {
            "id": playlist_id,
            "user_id": user_id,
            "name": name,
            "description": description or "",
            "tracks": [],
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "is_public": False
        }
        
        # Save to database
        await self.database.create_playlist(playlist)
        
        return playlist
    
    async def add_track_to_playlist(self, user_id: int, playlist_id: str, track_info: Dict[str, Any]) -> bool:
        """
        Add a track to a playlist.
        
        Args:
            user_id: The Telegram user ID.
            playlist_id: The playlist ID.
            track_info: The track information.
            
        Returns:
            True if successful, False otherwise.
        """
        # Get the playlist
        playlist = await self.database.get_playlist(playlist_id)
        if not playlist:
            logger.error(f"Playlist not found: {playlist_id}")
            return False
        
        # Check if user owns the playlist
        if playlist.get("user_id") != user_id:
            logger.error(f"User {user_id} does not own playlist {playlist_id}")
            return False
        
        # Check if playlist is full
        if len(playlist.get("tracks", [])) >= self.max_tracks_per_playlist:
            logger.error(f"Playlist {playlist_id} is full")
            return False
        
        # Check if track already exists in playlist
        track_id = track_info.get("id")
        if track_id:
            for existing_track in playlist.get("tracks", []):
                if existing_track.get("id") == track_id:
                    logger.info(f"Track {track_id} already in playlist {playlist_id}")
                    return True
        
        # Add track to playlist
        track_to_add = {
            "id": track_info.get("id", ""),
            "name": track_info.get("name", "Unknown"),
            "artists": track_info.get("artists", "Unknown"),
            "album": track_info.get("album", "Unknown"),
            "duration_ms": track_info.get("duration_ms", 0),
            "added_at": int(time.time())
        }
        
        playlist["tracks"].append(track_to_add)
        playlist["updated_at"] = int(time.time())
        
        # Update the playlist in the database
        success = await self.database.update_playlist(playlist_id, playlist)
        
        return success
    
    async def remove_track_from_playlist(self, user_id: int, playlist_id: str, track_id: str) -> bool:
        """
        Remove a track from a playlist.
        
        Args:
            user_id: The Telegram user ID.
            playlist_id: The playlist ID.
            track_id: The track ID to remove.
            
        Returns:
            True if successful, False otherwise.
        """
        # Get the playlist
        playlist = await self.database.get_playlist(playlist_id)
        if not playlist:
            logger.error(f"Playlist not found: {playlist_id}")
            return False
        
        # Check if user owns the playlist
        if playlist.get("user_id") != user_id:
            logger.error(f"User {user_id} does not own playlist {playlist_id}")
            return False
        
        # Find and remove the track
        tracks = playlist.get("tracks", [])
        found = False
        for i, track in enumerate(tracks):
            if track.get("id") == track_id:
                found = True
                tracks.pop(i)
                break
        
        if not found:
            logger.error(f"Track {track_id} not found in playlist {playlist_id}")
            return False
        
        playlist["tracks"] = tracks
        playlist["updated_at"] = int(time.time())
        
        # Update the playlist in the database
        success = await self.database.update_playlist(playlist_id, playlist)
        
        return success
    
    async def get_playlist(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a playlist by ID.
        
        Args:
            playlist_id: The playlist ID.
            
        Returns:
            The playlist object if found, None otherwise.
        """
        return await self.database.get_playlist(playlist_id)
    
    async def get_user_playlists(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all playlists for a user.
        
        Args:
            user_id: The Telegram user ID.
            
        Returns:
            A list of playlist objects.
        """
        return await self.database.get_user_playlists(user_id)
    
    async def delete_playlist(self, user_id: int, playlist_id: str) -> bool:
        """
        Delete a playlist.
        
        Args:
            user_id: The Telegram user ID.
            playlist_id: The playlist ID.
            
        Returns:
            True if successful, False otherwise.
        """
        # Get the playlist
        playlist = await self.database.get_playlist(playlist_id)
        if not playlist:
            logger.error(f"Playlist not found: {playlist_id}")
            return False
        
        # Check if user owns the playlist
        if playlist.get("user_id") != user_id:
            logger.error(f"User {user_id} does not own playlist {playlist_id}")
            return False
        
        # Delete the playlist from the database
        success = await self.database.delete_playlist(playlist_id)
        
        return success
    
    async def update_playlist_details(self, user_id: int, playlist_id: str, name: Optional[str] = None, 
                                     description: Optional[str] = None, is_public: Optional[bool] = None) -> bool:
        """
        Update playlist details.
        
        Args:
            user_id: The Telegram user ID.
            playlist_id: The playlist ID.
            name: Optional new playlist name.
            description: Optional new playlist description.
            is_public: Optional flag to set playlist visibility.
            
        Returns:
            True if successful, False otherwise.
        """
        # Get the playlist
        playlist = await self.database.get_playlist(playlist_id)
        if not playlist:
            logger.error(f"Playlist not found: {playlist_id}")
            return False
        
        # Check if user owns the playlist
        if playlist.get("user_id") != user_id:
            logger.error(f"User {user_id} does not own playlist {playlist_id}")
            return False
        
        # Update the fields
        if name is not None:
            playlist["name"] = name
        
        if description is not None:
            playlist["description"] = description
        
        if is_public is not None:
            playlist["is_public"] = is_public
        
        playlist["updated_at"] = int(time.time())
        
        # Update the playlist in the database
        success = await self.database.update_playlist(playlist_id, playlist)
        
        return success
    
    async def get_public_playlists(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get public playlists.
        
        Args:
            limit: Maximum number of playlists to return.
            
        Returns:
            A list of public playlist objects.
        """
        return await self.database.get_public_playlists(limit)