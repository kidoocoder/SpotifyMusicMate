import os
import aiohttp
import asyncio
import logging
import base64
import time
import json
import aiofiles
from urllib.parse import quote
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)

class SpotifyClient:
    """Client for interacting with Spotify API."""
    
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expiry = 0
        self.base_url = "https://api.spotify.com/v1"
        self.auth_url = "https://accounts.spotify.com/api/token"
        self.session = None
        self.cache_dir = os.getenv("CACHE_DIR", "cache")
        
        # Create cache directory
        os.makedirs(self.cache_dir, exist_ok=True)
    
    async def initialize(self):
        """Initialize the client by getting an access token."""
        self.session = aiohttp.ClientSession()
        await self.get_access_token()
    
    async def get_access_token(self):
        """Get an access token from Spotify."""
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode("utf-8")
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {"grant_type": "client_credentials"}
        
        try:
            async with self.session.post(self.auth_url, headers=headers, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to get Spotify access token: {error_text}")
                    return None
                
                result = await response.json()
                self.access_token = result["access_token"]
                self.token_expiry = time.time() + result["expires_in"]
                logger.info("Got new Spotify access token")
                return self.access_token
        except Exception as e:
            logger.error(f"Error getting Spotify access token: {e}", exc_info=True)
            return None
    
    async def _make_request(self, endpoint, params=None):
        """Make a request to the Spotify API."""
        if not self.session:
            logger.error("Session not initialized. Call initialize() first.")
            return None
        
        await self.get_access_token()
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"{self.base_url}/{endpoint}"
        
        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Spotify API error: {error_text}")
                    if response.status == 401:
                        # Token expired, try refreshing
                        self.access_token = None
                        await self.get_access_token()
                        return await self._make_request(endpoint, params)
                    return None
                
                return await response.json()
        except Exception as e:
            logger.error(f"Error making Spotify request: {e}", exc_info=True)
            return None
    
    async def search(self, query, limit=10):
        """Search for tracks on Spotify."""
        encoded_query = quote(query)
        endpoint = f"search?q={encoded_query}&type=track&limit={limit}"
        result = await self._make_request(endpoint)
        
        if not result or "tracks" not in result:
            return []
        
        tracks = result["tracks"]["items"]
        formatted_tracks = []
        
        for track in tracks:
            artists = ", ".join([artist["name"] for artist in track["artists"]])
            formatted_tracks.append({
                "id": track["id"],
                "name": track["name"],
                "artists": artists,
                "album": track["album"]["name"],
                "duration_ms": track["duration_ms"],
                "uri": track["uri"],
                "preview_url": track["preview_url"],
                "external_url": track["external_urls"]["spotify"],
                "album_art": track["album"]["images"][0]["url"] if track["album"]["images"] else None
            })
        
        return formatted_tracks
    
    async def get_track(self, track_id):
        """Get track details by ID."""
        endpoint = f"tracks/{track_id}"
        track = await self._make_request(endpoint)
        
        if not track:
            return None
        
        artists = ", ".join([artist["name"] for artist in track["artists"]])
        return {
            "id": track["id"],
            "name": track["name"],
            "artists": artists,
            "album": track["album"]["name"],
            "duration_ms": track["duration_ms"],
            "uri": track["uri"],
            "preview_url": track["preview_url"],
            "external_url": track["external_urls"]["spotify"],
            "album_art": track["album"]["images"][0]["url"] if track["album"]["images"] else None
        }
    
    async def download_track(self, track_info):
        """Download track audio for playback in voice chats."""
        # This is a simplified implementation that uses the preview URL
        # In a real implementation, you would use a proper Spotify API download method
        # or a third-party service for full tracks
        
        if not track_info.get("preview_url"):
            logger.error(f"No preview URL available for track: {track_info['name']}")
            return None
        
        # Create a cache filename based on track ID
        cache_file = os.path.join(self.cache_dir, f"{track_info['id']}.mp3")
        
        # Check if file already exists in cache
        if os.path.exists(cache_file):
            logger.info(f"Using cached track: {track_info['name']}")
            return {
                "file_path": cache_file,
                "duration": self.get_audio_duration(cache_file),
                **track_info
            }
        
        # Download the preview
        try:
            async with self.session.get(track_info["preview_url"]) as response:
                if response.status != 200:
                    logger.error(f"Failed to download track: {await response.text()}")
                    return None
                
                content = await response.read()
                
                async with aiofiles.open(cache_file, "wb") as f:
                    await f.write(content)
                
                logger.info(f"Downloaded track: {track_info['name']}")
                
                return {
                    "file_path": cache_file,
                    "duration": self.get_audio_duration(cache_file),
                    **track_info
                }
        except Exception as e:
            logger.error(f"Error downloading track: {e}", exc_info=True)
            return None
    
    def get_audio_duration(self, file_path):
        """Get the duration of an audio file in seconds."""
        try:
            audio = MP3(file_path)
            return audio.info.length
        except Exception as e:
            logger.error(f"Error getting audio duration: {e}")
            return 0
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
