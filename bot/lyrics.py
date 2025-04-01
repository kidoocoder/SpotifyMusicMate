"""Lyrics module for fetching song lyrics from Genius API."""

import os
import re
import logging
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Configuration
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")
GENIUS_API_BASE_URL = "https://api.genius.com"
GENIUS_SEARCH_URL = f"{GENIUS_API_BASE_URL}/search"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


class LyricsClient:
    """Client for fetching song lyrics from Genius API."""

    def __init__(self, api_token=None):
        """Initialize the lyrics client.
        
        Args:
            api_token: Genius API token. If not provided, will try to use the GENIUS_API_TOKEN environment variable.
        """
        self.api_token = api_token or GENIUS_API_TOKEN
        if not self.api_token:
            logger.warning("Genius API token not provided. Some features may be limited.")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_token}" if self.api_token else "",
            "User-Agent": USER_AGENT
        }
        self.session = None
    
    async def initialize(self):
        """Initialize the aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=self.headers)
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def search_song(self, query, limit=5):
        """Search for songs on Genius.
        
        Args:
            query: Search query string (song name or artist + song)
            limit: Maximum number of results to return
            
        Returns:
            List of song info dicts with title, artist, id, url, etc.
        """
        await self.initialize()
        
        try:
            params = {"q": query}
            if self.api_token:
                # Use the Genius API if token is available
                async with self.session.get(GENIUS_SEARCH_URL, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Failed to search Genius: {response.status}")
                        return []
                    
                    data = await response.json()
                    hits = data.get("response", {}).get("hits", [])
                    
                    results = []
                    for hit in hits[:limit]:
                        result = hit.get("result", {})
                        song_data = {
                            "id": result.get("id"),
                            "title": result.get("title"),
                            "artist": result.get("primary_artist", {}).get("name"),
                            "url": result.get("url"),
                            "thumbnail": result.get("song_art_image_thumbnail_url"),
                            "full_title": result.get("full_title")
                        }
                        results.append(song_data)
                    
                    return results
            else:
                # Fallback to web scraping if no API token
                search_url = f"https://genius.com/api/search/song?q={quote(query)}"
                async with self.session.get(search_url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to search Genius (fallback): {response.status}")
                        return []
                    
                    data = await response.json()
                    hits = data.get("response", {}).get("sections", [{}])[0].get("hits", [])
                    
                    results = []
                    for hit in hits[:limit]:
                        result = hit.get("result", {})
                        song_data = {
                            "id": result.get("id"),
                            "title": result.get("title"),
                            "artist": result.get("primary_artist", {}).get("name"),
                            "url": result.get("url"),
                            "thumbnail": result.get("song_art_image_thumbnail_url"),
                            "full_title": result.get("title_with_featured")
                        }
                        results.append(song_data)
                    
                    return results
                
        except Exception as e:
            logger.error(f"Error searching for lyrics: {e}")
            return []
    
    async def get_lyrics_by_search(self, song_name, artist_name=None):
        """Get lyrics for a song by searching for it.
        
        Args:
            song_name: Name of the song
            artist_name: Optional artist name to improve search
            
        Returns:
            dict with lyrics info or None if not found
        """
        # Create search query
        query = song_name
        if artist_name:
            query = f"{artist_name} {song_name}"
            
        search_results = await self.search_song(query, limit=1)
        
        if not search_results:
            return None
        
        song_info = search_results[0]
        lyrics = await self.get_lyrics_by_url(song_info["url"])
        
        if lyrics:
            return {
                "title": song_info["title"],
                "artist": song_info["artist"],
                "lyrics": lyrics,
                "source_url": song_info["url"],
                "thumbnail": song_info.get("thumbnail")
            }
        
        return None
    
    async def get_lyrics_by_url(self, url):
        """Extract lyrics from a Genius song URL.
        
        Args:
            url: Genius song URL
            
        Returns:
            String containing the lyrics or None if extraction fails
        """
        await self.initialize()
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch lyrics page: {response.status}")
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                
                # Find lyrics div (this selector might need to be updated if Genius changes their page structure)
                lyrics_div = soup.select_one('div[data-lyrics-container="true"]') or soup.select_one('.lyrics')
                
                if lyrics_div:
                    # Extract and clean lyrics
                    lyrics = lyrics_div.get_text(separator="\n")
                    # Clean up lyrics
                    lyrics = re.sub(r'\[.*?\]', '', lyrics)  # Remove [Verse], [Chorus], etc.
                    lyrics = re.sub(r'\n{3,}', '\n\n', lyrics)  # Remove excessive line breaks
                    lyrics = lyrics.strip()
                    return lyrics
                else:
                    logger.warning(f"Could not find lyrics container in the page: {url}")
                    return None
                
        except Exception as e:
            logger.error(f"Error fetching lyrics: {e}")
            return None
    
    def format_lyrics_for_telegram(self, lyrics_data, max_length=4000):
        """Format lyrics data for Telegram message.
        
        Args:
            lyrics_data: Dict containing lyrics info
            max_length: Maximum message length (Telegram has a 4096 char limit)
            
        Returns:
            Formatted string with lyrics
        """
        if not lyrics_data:
            return "❌ Lyrics not found for this song."
        
        title = lyrics_data.get("title", "Unknown")
        artist = lyrics_data.get("artist", "Unknown Artist")
        lyrics = lyrics_data.get("lyrics", "Lyrics not available")
        url = lyrics_data.get("source_url", "")
        
        # Create header
        header = f"🎵 **{title}**\n👤 {artist}\n\n"
        
        # Truncate lyrics if too long
        lyrics_length = len(lyrics)
        if lyrics_length > max_length:
            lyrics = lyrics[:max_length-100] + "...\n\n(Lyrics truncated due to length)"
        
        # Add footer with source
        footer = f"\n\n🔍 [View full lyrics on Genius]({url})"
        
        return header + lyrics + footer