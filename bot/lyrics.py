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
    
    async def get_lyrics_with_translations(self, song_name, artist_name=None, target_language=None):
        """Get lyrics with translation if available.
        
        Args:
            song_name: Name of the song
            artist_name: Optional artist name
            target_language: ISO language code for translation (e.g., 'es', 'fr')
            
        Returns:
            Dict with lyrics info including translations if available
        """
        lyrics_data = await self.get_lyrics_by_search(song_name, artist_name)
        if not lyrics_data:
            return None
            
        # If target language is specified, try to get translation
        if target_language and self.api_token:
            # The actual translation would require a proper translation service API
            # This is a placeholder for where you would integrate with a translation API
            try:
                # Create a cleaned version of lyrics for translation (limit to a reasonable size)
                orig_lyrics = lyrics_data.get("lyrics", "")
                lyrics_for_translation = orig_lyrics[:5000]  # Limit to 5000 chars
                
                # Note: In a real implementation, you would call a translation API here
                translated_lyrics = f"Translation to {target_language} would go here in a real implementation."
                
                # Add translation to lyrics data
                lyrics_data["translated_lyrics"] = translated_lyrics
                lyrics_data["translation_language"] = target_language
            except Exception as e:
                logger.error(f"Error translating lyrics: {e}")
                # Continue without translation
        
        return lyrics_data
    
    async def get_synchronized_lyrics(self, song_name, artist_name=None):
        """Get time-synchronized lyrics if available.
        
        Args:
            song_name: Name of the song
            artist_name: Optional artist name
            
        Returns:
            Dict with lyrics info including time-synchronized lines if available
        """
        # First get normal lyrics
        lyrics_data = await self.get_lyrics_by_search(song_name, artist_name)
        if not lyrics_data:
            return None
            
        # Try to get synchronized lyrics
        await self.initialize()
        
        try:
            # In a real implementation, we would need to find a service that provides
            # synchronized lyrics data. This could be a specialized LRC file API
            # or scraping from a service that provides time-synced lyrics.
            
            # This is just a placeholder to show the structure
            # For a real implementation, you'd need to integrate with a service like Musixmatch
            # or another provider that offers time-synced lyrics
            
            # Example structure for synchronized lyrics
            synced_lyrics = [
                {"time": 0, "text": "♪ (Intro music) ♪"},
                {"time": 12500, "text": "First line of lyrics"},
                {"time": 15800, "text": "Second line of lyrics"},
                # And so on...
            ]
            
            # Just create a demo structure based on the regular lyrics
            if lyrics_data.get("lyrics"):
                lines = lyrics_data["lyrics"].split('\n')
                fake_synced_lyrics = []
                current_time = 0
                
                for line in lines:
                    if line.strip():
                        fake_synced_lyrics.append({
                            "time": current_time,
                            "text": line
                        })
                        # Add a random time increment (2-5 seconds) for demo purposes
                        current_time += 2000 + (len(line) * 50)  # Longer lines take longer
                
                lyrics_data["synchronized_lyrics"] = fake_synced_lyrics
                lyrics_data["has_real_sync"] = False  # Mark as not real synchronized data
            
        except Exception as e:
            logger.error(f"Error getting synchronized lyrics: {e}")
            # Continue without synchronized lyrics
        
        return lyrics_data
    
    def format_lyrics_for_telegram(self, lyrics_data, max_length=4000, show_translation=False):
        """Format lyrics data for Telegram message.
        
        Args:
            lyrics_data: Dict containing lyrics info
            max_length: Maximum message length (Telegram has a 4096 char limit)
            show_translation: Whether to show translation if available
            
        Returns:
            Formatted string with lyrics
        """
        if not lyrics_data:
            return "❌ Lyrics not found for this song."
        
        title = lyrics_data.get("title", "Unknown")
        artist = lyrics_data.get("artist", "Unknown Artist")
        lyrics = lyrics_data.get("lyrics", "Lyrics not available")
        url = lyrics_data.get("source_url", "")
        
        # Create header with more info
        header = f"🎵 **{title}**\n👤 {artist}\n\n"
        
        # Check if we should show translation
        if show_translation and "translated_lyrics" in lyrics_data:
            # In a dual-language format
            orig_lines = lyrics.split('\n')
            trans_lines = lyrics_data["translated_lyrics"].split('\n')
            
            # Match lines as best we can
            combined_lyrics = ""
            for i in range(min(len(orig_lines), len(trans_lines))):
                if orig_lines[i].strip():
                    combined_lyrics += f"{orig_lines[i]}\n"
                    if trans_lines[i].strip():
                        combined_lyrics += f"➤ {trans_lines[i]}\n"
                    combined_lyrics += "\n"  # Extra space between verse lines
            
            lyrics = combined_lyrics.strip()
            header += f"🌍 With translation to {lyrics_data.get('translation_language', 'another language')}\n\n"
        
        # Truncate lyrics if too long
        lyrics_length = len(lyrics)
        if lyrics_length > max_length:
            lyrics = lyrics[:max_length-100] + "...\n\n(Lyrics truncated due to length)"
        
        # Add footer with source and enhanced info
        footer = f"\n\n🔍 [View full lyrics on Genius]({url})"
        
        # Add karaoke info if available
        if "synchronized_lyrics" in lyrics_data:
            if lyrics_data.get("has_real_sync", False):
                footer += "\n🎤 Time-synchronized lyrics available - perfect for karaoke!"
            else:
                footer += "\n🎤 Basic time alignments available for sing-along."
                
        return header + lyrics + footer
    
    def create_lyrics_pages(self, lyrics_data, page_size=900):
        """Split lyrics into paginated chunks for better reading.
        
        Args:
            lyrics_data: Dict containing lyrics info
            page_size: Maximum size of each page (in characters)
            
        Returns:
            List of strings, each representing a page of lyrics
        """
        if not lyrics_data:
            return ["❌ Lyrics not found for this song."]
            
        title = lyrics_data.get("title", "Unknown")
        artist = lyrics_data.get("artist", "Unknown Artist")
        lyrics = lyrics_data.get("lyrics", "Lyrics not available")
        url = lyrics_data.get("source_url", "")
        
        # Create header
        header = f"🎵 **{title}**\n👤 {artist}\n\n"
        
        # Split lyrics by line and create reasonably sized pages
        lines = lyrics.split('\n')
        pages = []
        current_page = header
        
        for line in lines:
            # If adding this line would make the page too long, start a new page
            if len(current_page) + len(line) + 1 > page_size and len(current_page) > len(header):
                current_page += "\n(Continued on next page...)"
                pages.append(current_page)
                current_page = f"**{title}** (Continued)\n\n"
            
            current_page += line + "\n"
        
        # Add the last page if not empty
        if len(current_page) > len(header):
            # Add footer to the last page
            current_page += f"\n\n🔍 [View full lyrics on Genius]({url})"
            pages.append(current_page)
        
        return pages