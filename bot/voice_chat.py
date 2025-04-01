import asyncio
import logging
import os
import time
from pytgcalls import PyTgCalls, filters
from pytgcalls.types import Update
from pytgcalls.types.stream import MediaStream
from pytgcalls.types.stream.audio_quality import AudioQuality
from pytgcalls.exceptions import (
    NoActiveGroupCall,
    NotInCallError,
    PyTgCallsAlreadyRunning,
    UnsupportedMethod
)

logger = logging.getLogger(__name__)

class VoiceChat:
    """Manager for voice chat functionality."""
    
    def __init__(self, call_client, queue_manager, spotify):
        self.call_client = call_client
        self.queue_manager = queue_manager
        self.spotify = spotify
        self.active_calls = {}  # chat_id -> call_info
        
        # Register pytgcalls handlers
        self.call_client.add_handler(self._on_stream_end, filters.stream_end)
        # Add other handlers here when needed
    
    async def join_voice_chat(self, chat_id, user_id=None):
        """Join a voice chat in a specific chat."""
        if chat_id in self.active_calls:
            return True
        
        try:
            await self.call_client.join_group_call(
                chat_id,
                MediaStream(
                    os.path.join("assets", "silence.mp3"),
                    audio_parameters=AudioQuality.HIGH
                )
            )
            
            self.active_calls[chat_id] = {
                "started_by": user_id,
                "start_time": time.time(),
                "current_track": None,
                "volume": 100,
            }
            
            logger.info(f"Joined voice chat in {chat_id}")
            return True
        except PyTgCallsAlreadyRunning:
            # Already joined, update our state
            self.active_calls[chat_id] = {
                "started_by": user_id,
                "start_time": time.time(),
                "current_track": None,
                "volume": 100,
            }
            logger.info(f"Already in voice chat {chat_id}")
            return True
        except NoActiveGroupCall as e:
            logger.error(f"Failed to join voice chat in {chat_id}: {e}")
            return False
    
    async def leave_voice_chat(self, chat_id):
        """Leave a voice chat."""
        if chat_id not in self.active_calls:
            return True
        
        try:
            await self.call_client.leave_group_call(chat_id)
            self.active_calls.pop(chat_id, None)
            self.queue_manager.clear_queue(chat_id)
            logger.info(f"Left voice chat in {chat_id}")
            return True
        except NotInCallError:
            self.active_calls.pop(chat_id, None)
            self.queue_manager.clear_queue(chat_id)
            logger.info(f"Already left voice chat in {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error leaving voice chat in {chat_id}: {e}", exc_info=True)
            return False
    
    async def play_track(self, chat_id, track_info, user_id=None):
        """Play a track in a voice chat."""
        # Check if we're in the voice chat
        if chat_id not in self.active_calls:
            success = await self.join_voice_chat(chat_id, user_id)
            if not success:
                return False, "Failed to join voice chat"
        
        # Download the track if not already
        if "file_path" not in track_info:
            downloaded_track = await self.spotify.download_track(track_info)
            if not downloaded_track:
                return False, "Failed to download track"
            track_info = downloaded_track
        
        try:
            await self.call_client.change_stream(
                chat_id,
                MediaStream(
                    track_info["file_path"],
                    audio_parameters=AudioQuality.HIGH
                )
            )
            
            # Update active call info
            self.active_calls[chat_id]["current_track"] = track_info
            
            logger.info(f"Playing track {track_info['name']} in {chat_id}")
            return True, f"Now playing: {track_info['name']} by {track_info['artists']}"
        except Exception as e:
            logger.error(f"Error playing track in {chat_id}: {e}", exc_info=True)
            return False, f"Error playing track: {str(e)}"
    
    async def pause(self, chat_id):
        """Pause the current track."""
        if chat_id not in self.active_calls:
            return False, "Not in a voice chat"
        
        try:
            await self.call_client.pause_stream(chat_id)
            logger.info(f"Paused track in {chat_id}")
            return True, "Playback paused"
        except NotInCallError:
            self.active_calls.pop(chat_id, None)
            return False, "Not in voice chat"
        except Exception as e:
            logger.error(f"Error pausing track in {chat_id}: {e}", exc_info=True)
            return False, f"Error pausing track: {str(e)}"
    
    async def resume(self, chat_id):
        """Resume the current track."""
        if chat_id not in self.active_calls:
            return False, "Not in a voice chat"
        
        try:
            await self.call_client.resume_stream(chat_id)
            logger.info(f"Resumed track in {chat_id}")
            return True, "Playback resumed"
        except NotInCallError:
            self.active_calls.pop(chat_id, None)
            return False, "Not in voice chat"
        except Exception as e:
            logger.error(f"Error resuming track in {chat_id}: {e}", exc_info=True)
            return False, f"Error resuming track: {str(e)}"
    
    async def skip(self, chat_id):
        """Skip the current track and play the next in queue."""
        if chat_id not in self.active_calls:
            return False, "Not in a voice chat"
        
        # Get the next track from the queue
        next_track = self.queue_manager.get_next_track(chat_id)
        if not next_track:
            return False, "No more tracks in the queue"
        
        # Play the next track
        success, message = await self.play_track(chat_id, next_track)
        if success:
            return True, f"Skipped to: {next_track['name']} by {next_track['artists']}"
        else:
            return False, message
    
    async def set_volume(self, chat_id, volume):
        """Set the volume of the current stream."""
        if chat_id not in self.active_calls:
            return False, "Not in a voice chat"
        
        # Validate volume (0-200)
        volume = max(0, min(200, volume))
        
        try:
            await self.call_client.change_volume_call(chat_id, volume)
            self.active_calls[chat_id]["volume"] = volume
            logger.info(f"Set volume to {volume} in {chat_id}")
            return True, f"Volume set to {volume}%"
        except NotInCallError:
            self.active_calls.pop(chat_id, None)
            return False, "Not in voice chat"
        except Exception as e:
            logger.error(f"Error setting volume in {chat_id}: {e}", exc_info=True)
            return False, f"Error setting volume: {str(e)}"
    
    async def _on_stream_end(self, update):
        """Callback for when a stream ends."""
        logger.info(f"Stream end update: {update}")
        
        # Extract chat_id from the update object
        chat_id = None
        if hasattr(update, 'chat_id'):
            chat_id = update.chat_id
        elif hasattr(update, 'chat') and hasattr(update.chat, 'id'):
            chat_id = update.chat.id
        
        if not chat_id:
            logger.warning("Received stream_end without chat_id")
            return
        logger.info(f"Stream ended in {chat_id}")
        
        # Get the next track from the queue
        next_track = self.queue_manager.get_next_track(chat_id)
        if next_track:
            # Play the next track
            await asyncio.sleep(1)  # Small delay to avoid issues
            await self.play_track(chat_id, next_track)
        else:
            # No more tracks, leave the voice chat after a delay
            await asyncio.sleep(10)  # Wait 10 seconds before checking again
            
            # Check if a new track was added during the wait
            if not self.queue_manager.has_tracks(chat_id):
                logger.info(f"No more tracks in queue for {chat_id}, leaving voice chat")
                await self.leave_voice_chat(chat_id)
    
    async def _on_kicked(self, client, chat_id: int):
        """Callback for when the bot is kicked from a voice chat."""
        logger.info(f"Kicked from voice chat in {chat_id}")
        self.active_calls.pop(chat_id, None)
        self.queue_manager.clear_queue(chat_id)
    
    async def _on_closed_voice_chat(self, client, chat_id: int):
        """Callback for when a voice chat is closed."""
        logger.info(f"Voice chat closed in {chat_id}")
        self.active_calls.pop(chat_id, None)
        self.queue_manager.clear_queue(chat_id)
