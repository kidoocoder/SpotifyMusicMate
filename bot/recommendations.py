"""Module for handling music recommendations."""
import logging
import asyncio
import random
from typing import List, Dict, Any, Optional

from bot.database import Database
from bot.spotify import SpotifyClient

logger = logging.getLogger(__name__)

class RecommendationEngine:
    """Engine for generating music recommendations."""
    
    def __init__(self, spotify: SpotifyClient, database: Database):
        self.spotify = spotify
        self.database = database
        
    async def get_recommendations_from_track(self, track_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recommendations based on a specific track.
        
        Args:
            track_id: The Spotify track ID.
            limit: The maximum number of recommendations to get.
            
        Returns:
            A list of track info dictionaries.
        """
        try:
            # Use Spotify's recommendation API
            recommendations = await self.spotify.get_recommendations_by_track(track_id, limit=limit)
            
            # Format the response
            formatted = []
            for track in recommendations:
                formatted.append({
                    "id": track.get("id", ""),
                    "name": track.get("name", "Unknown"),
                    "artists": track.get("artists", [{"name": "Unknown"}]),
                    "album": track.get("album", {}).get("name", "Unknown"),
                    "duration_ms": track.get("duration_ms", 0),
                    "preview_url": track.get("preview_url", None),
                    "recommendation_reason": "Based on your recent listening"
                })
            
            return formatted
        except Exception as e:
            logger.error(f"Error getting recommendations for track {track_id}: {e}", exc_info=True)
            return []
    
    async def get_personalized_recommendations(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get personalized recommendations based on user's listening history.
        
        Args:
            user_id: The Telegram user ID.
            limit: The maximum number of recommendations.
            
        Returns:
            A list of track info dictionaries.
        """
        try:
            # Get user's recent listening history from database
            stats = await self.database.get_user_stats(user_id)
            top_tracks = stats.get("most_played_tracks", [])
            
            if not top_tracks:
                # If no history, try getting user's favorites
                favorites = await self.database.get_user_favorites(user_id, limit=5)
                if favorites:
                    # Use first favorite track as seed
                    seed_track = favorites[0].get("track_id", "")
                    if seed_track:
                        return await self.get_recommendations_from_track(seed_track, limit=limit)
                return []  # No history or favorites
            
            # Use top track as seed
            top_track_id = top_tracks[0].get("_id", "")
            if not top_track_id:
                return []
                
            recommendations = await self.get_recommendations_from_track(top_track_id, limit=limit)
            
            # Add personalized recommendation reason
            for rec in recommendations:
                rec["recommendation_reason"] = f"Based on your top played track: {top_tracks[0].get('name', 'Unknown')}"
                
            return recommendations
        except Exception as e:
            logger.error(f"Error getting personalized recommendations for user {user_id}: {e}", exc_info=True)
            return []
    
    async def get_group_recommendations(self, chat_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recommendations for a group based on its listening history.
        
        Args:
            chat_id: The Telegram chat ID.
            limit: The maximum number of recommendations.
            
        Returns:
            A list of track info dictionaries.
        """
        try:
            # Get top tracks for the chat
            top_tracks = await self.database.get_top_tracks(chat_id, limit=3)
            
            if not top_tracks:
                return []  # No history
            
            # Use the top track as seed
            seed_track = top_tracks[0].get("_id", "")
            if not seed_track:
                return []
                
            recommendations = await self.get_recommendations_from_track(seed_track, limit=limit)
            
            # Add group-specific recommendation reason
            for rec in recommendations:
                rec["recommendation_reason"] = f"Based on this group's top track: {top_tracks[0].get('name', 'Unknown')}"
                
            return recommendations
        except Exception as e:
            logger.error(f"Error getting group recommendations for chat {chat_id}: {e}", exc_info=True)
            return []
            
    async def get_trending_recommendations(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get trending song recommendations.
        
        Args:
            limit: The maximum number of recommendations.
            
        Returns:
            A list of track info dictionaries.
        """
        try:
            # Get trending tracks from Spotify
            trending = await self.spotify.get_trending_tracks(limit=limit)
            
            # Format the response
            formatted = []
            for track in trending:
                formatted.append({
                    "id": track.get("id", ""),
                    "name": track.get("name", "Unknown"),
                    "artists": track.get("artists", [{"name": "Unknown"}]),
                    "album": track.get("album", {}).get("name", "Unknown"),
                    "duration_ms": track.get("duration_ms", 0),
                    "preview_url": track.get("preview_url", None),
                    "recommendation_reason": "Currently trending"
                })
            
            return formatted
        except Exception as e:
            logger.error(f"Error getting trending recommendations: {e}", exc_info=True)
            return []