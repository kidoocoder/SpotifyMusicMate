"""Voice command processing for the music bot."""
import logging
import os
import tempfile
import asyncio
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Try to import speech recognition libraries
try:
    import speech_recognition as sr
except ImportError:
    sr = None
    logger.warning("speech_recognition library not found. Voice commands will not be available.")


class VoiceCommandHandler:
    """Handler for voice commands using speech recognition."""
    
    def __init__(self, config=None):
        """
        Initialize the voice command handler.
        
        Args:
            config: Optional configuration object.
        """
        self.config = config
        self.available = sr is not None
        self.recognizer = sr.Recognizer() if sr else None
        self.language = "en-US"  # Default language
        self.confidence_threshold = 0.6  # Minimum confidence for commands
        
        # Define voice command keywords and their text equivalents
        self.commands = {
            "play": ["play", "start playing", "put on"],
            "pause": ["pause", "pause music", "pause playback"],
            "resume": ["resume", "continue", "continue playing"],
            "skip": ["skip", "next", "next song", "skip song"],
            "stop": ["stop", "stop music", "end playback"],
            "volume": ["volume", "change volume", "set volume"],
            "add": ["add", "add to queue", "queue"],
            "current": ["current", "what's playing", "what is playing", "now playing"]
        }
    
    def is_available(self) -> bool:
        """
        Check if voice command processing is available.
        
        Returns:
            True if available, False otherwise.
        """
        return self.available
    
    def set_language(self, language_code: str):
        """
        Set the language for speech recognition.
        
        Args:
            language_code: Language code (e.g., 'en-US', 'es-ES').
        """
        self.language = language_code
    
    async def process_voice_message(self, voice_file_path: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Process a voice message and extract commands.
        
        Args:
            voice_file_path: Path to the voice message file.
            
        Returns:
            Tuple of (success, command, command_data)
        """
        if not self.available:
            logger.warning("Voice command processing is not available.")
            return (False, None, None)
        
        try:
            # Voice messages in Telegram are typically in OGG format
            # We need to convert to a format compatible with speech_recognition
            # In a real implementation, you'd use a tool like ffmpeg for this conversion
            
            # This is a simplified example assuming the file is already in a compatible format
            # In a real implementation, you would convert the file first
            
            with sr.AudioFile(voice_file_path) as source:
                audio_data = self.recognizer.record(source)
                
                # Use Google's speech recognition (or another service if preferred)
                text = self.recognizer.recognize_google(
                    audio_data, 
                    language=self.language,
                    show_all=True  # Get full response with confidence scores
                )
                
                if not text or "alternative" not in text:
                    logger.info("No speech detected in voice message")
                    return (False, None, None)
                
                # Get the most likely transcription
                alternatives = text["alternative"]
                if not alternatives:
                    logger.info("No alternatives found in speech recognition")
                    return (False, None, None)
                
                top_result = alternatives[0]
                transcript = top_result.get("transcript", "").lower()
                confidence = top_result.get("confidence", 0)
                
                logger.info(f"Transcribed voice: '{transcript}' (confidence: {confidence})")
                
                # Check confidence threshold
                if confidence < self.confidence_threshold:
                    logger.info(f"Confidence too low: {confidence} < {self.confidence_threshold}")
                    return (False, None, None)
                
                # Parse the command
                return self._parse_command(transcript)
                
        except Exception as e:
            logger.error(f"Error processing voice command: {e}", exc_info=True)
            return (False, None, None)
    
    def _parse_command(self, text: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Parse a command from transcribed text.
        
        Args:
            text: Transcribed text from voice message.
            
        Returns:
            Tuple of (success, command, command_data)
        """
        text = text.lower().strip()
        
        # Check for each command type
        for cmd, keywords in self.commands.items():
            for keyword in keywords:
                if keyword in text:
                    # Found a command
                    command_data = {}
                    
                    # Extract additional data based on command type
                    if cmd == "play":
                        # Extract song name after "play"
                        for kw in keywords:
                            if kw in text:
                                parts = text.split(kw, 1)
                                if len(parts) > 1 and parts[1].strip():
                                    command_data["query"] = parts[1].strip()
                                break
                    
                    elif cmd == "volume":
                        # Try to extract volume level (0-100)
                        words = text.split()
                        for i, word in enumerate(words):
                            if word in ["volume", "set", "change"] and i < len(words) - 1:
                                try:
                                    volume = int(words[i+1])
                                    if 0 <= volume <= 100:
                                        command_data["volume"] = volume
                                except ValueError:
                                    # Not a number, try word-to-number conversion
                                    number_words = {
                                        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
                                        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                                        "ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
                                        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100
                                    }
                                    
                                    if words[i+1] in number_words:
                                        command_data["volume"] = number_words[words[i+1]]
                    
                    return (True, cmd, command_data)
        
        # No command found
        return (False, None, None)
    
    async def download_and_process_voice(self, message) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Download a voice message and process it.
        
        Args:
            message: The Telegram message containing the voice.
            
        Returns:
            Tuple of (success, command, command_data)
        """
        if not self.available:
            logger.warning("Voice command processing is not available.")
            return (False, None, None)
        
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
                temp_path = temp_file.name
            
            # Download the voice message
            await message.download(temp_path)
            
            # Process the voice message
            result = await self.process_voice_message(temp_path)
            
            # Clean up the temporary file
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.error(f"Error removing temporary file: {e}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error downloading and processing voice: {e}", exc_info=True)
            return (False, None, None)