"""Image UI generation for visual interface components."""
import logging
import os
import io
import asyncio
import time
from typing import Optional, Dict, Any, Tuple, List, Union
from PIL import Image, ImageDraw, ImageFont
import aiofiles
import aiohttp

logger = logging.getLogger(__name__)

class ImageUI:
    """Generator for image-based UI elements."""
    
    def __init__(self, config=None):
        """
        Initialize the image UI generator.
        
        Args:
            config: Optional configuration object.
        """
        self.config = config
        self.assets_dir = "assets"
        self.cache_dir = os.path.join("cache", "image_ui")
        self.width = 600
        self.height = 315
        self.background_color = (30, 30, 40)
        self.text_color = (255, 255, 255)
        self.accent_color = (138, 43, 226)  # BlueViolet
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Load default fonts
        self.font_paths = {
            "regular": os.path.join(self.assets_dir, "fonts", "OpenSans-Regular.ttf"),
            "bold": os.path.join(self.assets_dir, "fonts", "OpenSans-Bold.ttf"),
            "light": os.path.join(self.assets_dir, "fonts", "OpenSans-Light.ttf")
        }
        
        # Load button assets
        self.button_paths = {
            "play": os.path.join(self.assets_dir, "play_button.svg"),
            "pause": os.path.join(self.assets_dir, "pause_button.svg"),
            "skip": os.path.join(self.assets_dir, "skip_button.svg"),
            "stop": os.path.join(self.assets_dir, "stop_button.svg")
        }
        
        # Initialize fonts (will be loaded when needed)
        self.fonts = {}
    
    def _get_font(self, size: int, font_type: str = "regular") -> ImageFont.FreeTypeFont:
        """
        Get a font of specified size and type.
        
        Args:
            size: Font size in points.
            font_type: Font type (regular, bold, light).
            
        Returns:
            PIL ImageFont object.
        """
        key = f"{font_type}_{size}"
        if key not in self.fonts:
            # Try to load from path
            try:
                font_path = self.font_paths.get(font_type, self.font_paths["regular"])
                if os.path.exists(font_path):
                    self.fonts[key] = ImageFont.truetype(font_path, size)
                else:
                    # Fallback to default font
                    logger.warning(f"Font file not found: {font_path}, using default")
                    self.fonts[key] = ImageFont.load_default()
            except Exception as e:
                logger.error(f"Error loading font: {e}", exc_info=True)
                self.fonts[key] = ImageFont.load_default()
        
        return self.fonts[key]
    
    async def create_now_playing_image(self, 
                                     track_info: Dict[str, Any],
                                     progress: float = 0.0) -> Optional[str]:
        """
        Create a 'Now Playing' image for the current song.
        
        Args:
            track_info: Track information dictionary.
            progress: Playback progress (0.0 to 1.0).
            
        Returns:
            Path to the generated image file, or None if generation failed.
        """
        track_id = track_info.get("id", "unknown")
        progress_str = f"{int(progress * 100):03d}"
        cache_key = f"now_playing_{track_id}_{progress_str}"
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.png")
        
        # Check if cached version exists and is recent (less than 30 seconds old)
        if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < 30:
            return cache_path
        
        try:
            # Create base image
            image = Image.new("RGB", (self.width, self.height), self.background_color)
            draw = ImageDraw.Draw(image)
            
            # Get track details
            title = track_info.get("name", "Unknown Track")
            artist = track_info.get("artists", "Unknown Artist")
            album = track_info.get("album", "")
            album_art_url = track_info.get("album_art")
            
            # Try to download album art
            album_art = None
            if album_art_url:
                try:
                    album_art = await self._download_image(album_art_url)
                except Exception as e:
                    logger.error(f"Error downloading album art: {e}")
            
            # Draw album art (left side)
            if album_art:
                # Resize to 250x250
                album_art = album_art.resize((250, 250), Image.LANCZOS)
                # Place on left side
                image.paste(album_art, (25, 32))
                
                # Add a border
                draw.rectangle((24, 31, 276, 283), outline=self.accent_color, width=2)
            else:
                # Draw placeholder if no album art
                draw.rectangle((25, 32, 275, 282), fill=(50, 50, 60))
                draw.text((150, 157), "🎵", fill=self.text_color, font=self._get_font(60), anchor="mm")
            
            # Draw track info (right side)
            title_font = self._get_font(28, "bold")
            artist_font = self._get_font(22)
            album_font = self._get_font(18, "light")
            
            # Title (truncate if too long)
            if len(title) > 25:
                title = title[:22] + "..."
            draw.text((295, 60), title, fill=self.text_color, font=title_font)
            
            # Artist
            if len(artist) > 30:
                artist = artist[:27] + "..."
            draw.text((295, 100), artist, fill=self.text_color, font=artist_font)
            
            # Album (if available)
            if album:
                if len(album) > 35:
                    album = album[:32] + "..."
                draw.text((295, 135), album, fill=(200, 200, 200), font=album_font)
            
            # Draw progress bar
            bar_width = 280
            bar_height = 6
            bar_x = 295
            bar_y = 180
            
            # Background bar
            draw.rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), 
                          fill=(60, 60, 70))
            
            # Progress bar
            progress_width = int(bar_width * progress)
            if progress_width > 0:
                draw.rectangle((bar_x, bar_y, bar_x + progress_width, bar_y + bar_height), 
                              fill=self.accent_color)
            
            # Draw playback time
            if "duration_ms" in track_info:
                duration_sec = track_info["duration_ms"] / 1000
                current_sec = duration_sec * progress
                
                time_text = f"{int(current_sec // 60):01d}:{int(current_sec % 60):02d} / {int(duration_sec // 60):01d}:{int(duration_sec % 60):02d}"
                time_font = self._get_font(16)
                draw.text((bar_x + bar_width, bar_y + 20), time_text, fill=self.text_color, font=time_font, anchor="rt")
            
            # Draw playback controls
            controls_y = 230
            
            # Draw control buttons
            button_positions = [
                ("play", 340),
                ("pause", 400),
                ("skip", 460),
                ("stop", 520)
            ]
            
            for button_name, x_pos in button_positions:
                # If we have the SVG, draw it; otherwise, use text
                if os.path.exists(self.button_paths.get(button_name, "")):
                    # This is a placeholder - in a real implementation, you'd render the SVG
                    # For now, we'll just draw a colored circle with text
                    draw.ellipse((x_pos - 20, controls_y - 20, x_pos + 20, controls_y + 20), 
                               fill=self.accent_color)
                    
                    # Add simple text label
                    labels = {"play": "▶", "pause": "⏸", "skip": "⏭", "stop": "⏹"}
                    draw.text((x_pos, controls_y), labels.get(button_name, "?"), 
                             fill=self.text_color, font=self._get_font(24), anchor="mm")
                else:
                    # Fallback to text
                    draw.text((x_pos, controls_y), button_name.title(), 
                             fill=self.text_color, font=self._get_font(16), anchor="mm")
            
            # Add footer text
            footer_text = "🎧 Powered by Telegram Music Bot"
            footer_font = self._get_font(14)
            draw.text((self.width // 2, self.height - 20), footer_text, 
                     fill=(180, 180, 180), font=footer_font, anchor="mm")
            
            # Save image
            image.save(cache_path)
            return cache_path
            
        except Exception as e:
            logger.error(f"Error creating now playing image: {e}", exc_info=True)
            return None
    
    async def create_playlist_image(self, 
                                  playlist_name: str, 
                                  track_count: int,
                                  created_by: Optional[str] = None) -> Optional[str]:
        """
        Create an image for a playlist.
        
        Args:
            playlist_name: Name of the playlist.
            track_count: Number of tracks in the playlist.
            created_by: Optional username of the playlist creator.
            
        Returns:
            Path to the generated image file, or None if generation failed.
        """
        cache_key = f"playlist_{playlist_name}_{track_count}"
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.png")
        
        try:
            # Create base image
            image = Image.new("RGB", (self.width, self.height), self.background_color)
            draw = ImageDraw.Draw(image)
            
            # Draw a decorative header
            draw.rectangle((0, 0, self.width, 60), fill=self.accent_color)
            
            # Draw playlist name
            title_font = self._get_font(36, "bold")
            if len(playlist_name) > 30:
                playlist_name = playlist_name[:27] + "..."
            draw.text((self.width // 2, 100), playlist_name, fill=self.text_color, font=title_font, anchor="mm")
            
            # Draw track count
            track_text = f"{track_count} {'tracks' if track_count != 1 else 'track'}"
            count_font = self._get_font(24)
            draw.text((self.width // 2, 150), track_text, fill=self.text_color, font=count_font, anchor="mm")
            
            # Draw created by (if provided)
            if created_by:
                created_font = self._get_font(18, "light")
                created_text = f"Created by: {created_by}"
                draw.text((self.width // 2, 190), created_text, fill=(200, 200, 200), font=created_font, anchor="mm")
            
            # Draw a decorative music note pattern
            notes = ["♪", "♫", "♬", "♩"]
            for i in range(20):
                x = 50 + (i * 30)
                y = 240 + (20 * (i % 3))
                note = notes[i % len(notes)]
                draw.text((x, y), note, fill=(100, 100, 120, 150), font=self._get_font(18), anchor="mm")
            
            # Save image
            image.save(cache_path)
            return cache_path
            
        except Exception as e:
            logger.error(f"Error creating playlist image: {e}", exc_info=True)
            return None
    
    async def create_quiz_question_image(self,
                                      question_number: int,
                                      total_questions: int,
                                      track_info: Dict[str, Any],
                                      question_type: str,
                                      options: List[str]) -> Optional[str]:
        """
        Create an image for a music quiz question.
        
        Args:
            question_number: Current question number.
            total_questions: Total number of questions.
            track_info: Track information dictionary.
            question_type: Type of question (e.g., 'guess_song', 'guess_artist').
            options: List of answer options.
            
        Returns:
            Path to the generated image file, or None if generation failed.
        """
        cache_key = f"quiz_{question_number}_{total_questions}_{track_info.get('id', 'unknown')}"
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.png")
        
        try:
            # Create base image
            image = Image.new("RGB", (self.width, self.height), self.background_color)
            draw = ImageDraw.Draw(image)
            
            # Draw quiz header
            draw.rectangle((0, 0, self.width, 50), fill=self.accent_color)
            header_font = self._get_font(24, "bold")
            draw.text((self.width // 2, 25), "🎵 MUSIC QUIZ 🎵", fill=self.text_color, font=header_font, anchor="mm")
            
            # Draw question number
            number_font = self._get_font(18)
            draw.text((self.width - 20, 25), f"Question {question_number}/{total_questions}", 
                     fill=self.text_color, font=number_font, anchor="rm")
            
            # Draw question type
            question_text = "Name this song"
            if question_type == "guess_artist":
                question_text = "Who is the artist of this song?"
            elif question_type == "finish_lyrics":
                question_text = "Complete the lyrics:"
                
            question_font = self._get_font(28, "bold")
            draw.text((self.width // 2, 90), question_text, fill=self.text_color, font=question_font, anchor="mm")
            
            # Try to download album art
            album_art = None
            album_art_url = track_info.get("album_art")
            if album_art_url:
                try:
                    album_art = await self._download_image(album_art_url)
                except Exception as e:
                    logger.error(f"Error downloading album art: {e}")
            
            # Draw album art (if available and appropriate for question type)
            if album_art and question_type in ["guess_song", "guess_artist"]:
                # Resize to 150x150
                album_art = album_art.resize((150, 150), Image.LANCZOS)
                # Place at top center
                image.paste(album_art, (self.width // 2 - 75, 120))
                
                # Add a border
                draw.rectangle((self.width // 2 - 76, 119, self.width // 2 + 76, 271), outline=self.accent_color, width=2)
            
            # Draw options
            option_start_y = 290
            option_height = 50
            option_margin = 10
            option_labels = ["A", "B", "C", "D"]
            option_font = self._get_font(20)
            
            for i, option in enumerate(options[:4]):  # Limit to 4 options
                y = option_start_y + (i * (option_height + option_margin))
                
                # Draw option background
                draw.rectangle((50, y, self.width - 50, y + option_height), 
                              fill=(60, 60, 70), outline=(100, 100, 120), width=2)
                
                # Draw option label (A, B, C, D)
                draw.rectangle((50, y, 80, y + option_height), fill=self.accent_color)
                draw.text((65, y + option_height // 2), option_labels[i], 
                         fill=self.text_color, font=option_font, anchor="mm")
                
                # Draw option text
                if len(option) > 50:
                    option = option[:47] + "..."
                draw.text((90, y + option_height // 2), option, 
                         fill=self.text_color, font=option_font, anchor="lm")
            
            # Save image
            image.save(cache_path)
            return cache_path
            
        except Exception as e:
            logger.error(f"Error creating quiz question image: {e}", exc_info=True)
            return None
    
    async def create_quiz_results_image(self,
                                     total_questions: int,
                                     correct_answers: int,
                                     total_participants: int,
                                     top_scorers: List[Tuple[str, int]]) -> Optional[str]:
        """
        Create an image for quiz results.
        
        Args:
            total_questions: Total number of questions.
            correct_answers: Number of correctly answered questions.
            total_participants: Number of quiz participants.
            top_scorers: List of (username, score) tuples for top scorers.
            
        Returns:
            Path to the generated image file, or None if generation failed.
        """
        cache_key = f"quiz_results_{total_questions}_{correct_answers}_{total_participants}"
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.png")
        
        try:
            # Create base image
            image = Image.new("RGB", (self.width, self.height), self.background_color)
            draw = ImageDraw.Draw(image)
            
            # Draw quiz header
            draw.rectangle((0, 0, self.width, 50), fill=self.accent_color)
            header_font = self._get_font(24, "bold")
            draw.text((self.width // 2, 25), "🎵 QUIZ RESULTS 🎵", fill=self.text_color, font=header_font, anchor="mm")
            
            # Draw statistics
            stats_font = self._get_font(22)
            accuracy = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
            
            draw.text((self.width // 2, 80), f"Questions: {total_questions}", 
                     fill=self.text_color, font=stats_font, anchor="mm")
            draw.text((self.width // 2, 110), f"Correct Answers: {correct_answers} ({accuracy:.1f}%)", 
                     fill=self.text_color, font=stats_font, anchor="mm")
            draw.text((self.width // 2, 140), f"Participants: {total_participants}", 
                     fill=self.text_color, font=stats_font, anchor="mm")
            
            # Draw a decorative divider
            draw.line((50, 170, self.width - 50, 170), fill=self.accent_color, width=2)
            
            # Draw top scorers header
            top_font = self._get_font(24, "bold")
            draw.text((self.width // 2, 190), "🏆 TOP SCORERS 🏆", 
                     fill=self.text_color, font=top_font, anchor="mm")
            
            # Draw top scorers
            score_font = self._get_font(20)
            score_start_y = 230
            score_height = 30
            
            for i, (username, score) in enumerate(top_scorers[:5]):  # Limit to top 5
                y = score_start_y + (i * score_height)
                
                # Draw ranking
                medal_icons = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                draw.text((80, y), medal_icons[i], fill=self.text_color, font=score_font, anchor="lm")
                
                # Draw username (truncate if too long)
                if len(username) > 20:
                    username = username[:17] + "..."
                draw.text((120, y), username, fill=self.text_color, font=score_font, anchor="lm")
                
                # Draw score
                draw.text((self.width - 80, y), str(score), fill=self.text_color, font=score_font, anchor="rm")
            
            # Draw footer
            footer_font = self._get_font(16, "light")
            draw.text((self.width // 2, self.height - 20), "Thanks for playing! 🎉", 
                     fill=(200, 200, 200), font=footer_font, anchor="mm")
            
            # Save image
            image.save(cache_path)
            return cache_path
            
        except Exception as e:
            logger.error(f"Error creating quiz results image: {e}", exc_info=True)
            return None
    
    async def _download_image(self, url: str) -> Optional[Image.Image]:
        """
        Download an image from a URL.
        
        Args:
            url: URL to download from.
            
        Returns:
            PIL Image object, or None if download failed.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download image: {response.status}")
                        return None
                    
                    image_data = await response.read()
                    return Image.open(io.BytesIO(image_data))
        except Exception as e:
            logger.error(f"Error downloading image: {e}", exc_info=True)
            return None