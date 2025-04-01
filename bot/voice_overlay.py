import asyncio
import logging
import time
import os
from typing import Dict, List, Optional, Set
from pyrogram import types
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

class VoiceOverlay:
    """
    Manages voice chat overlay features including:
    - Live participant tracking
    - Now playing overlay with reactions
    - Voice chat announcements
    """
    
    def __init__(self, client):
        self.client = client
        self.voice_participants = {}  # chat_id -> {user_id: last_active_time}
        self.reaction_counts = {}  # chat_id -> {track_id: {'👍': count, '👎': count, etc}}
        self.announcement_messages = {}  # chat_id -> message_id
        self.fonts = self._load_fonts()
        self.update_task = None
        
    def _load_fonts(self):
        """Load fonts for overlay images."""
        fonts = {}
        try:
            fonts_dir = os.path.join("assets", "fonts")
            fonts["regular"] = ImageFont.truetype(os.path.join(fonts_dir, "OpenSans-Regular.ttf"), 20)
            fonts["bold"] = ImageFont.truetype(os.path.join(fonts_dir, "OpenSans-Bold.ttf"), 22)
            fonts["light"] = ImageFont.truetype(os.path.join(fonts_dir, "OpenSans-Light.ttf"), 18)
        except Exception as e:
            logger.error(f"Failed to load fonts: {e}")
            # Use default font as fallback
            fonts["regular"] = ImageFont.load_default()
            fonts["bold"] = ImageFont.load_default()
            fonts["light"] = ImageFont.load_default()
        return fonts
        
    async def start(self):
        """Start background tasks for the overlay."""
        if self.update_task is None:
            self.update_task = asyncio.create_task(self._periodic_update())
            logger.info("Voice overlay background task started")

    async def stop(self):
        """Stop background tasks for the overlay."""
        if self.update_task:
            self.update_task.cancel()
            self.update_task = None
            logger.info("Voice overlay background task stopped")
            
    async def track_participant(self, chat_id: int, user_id: int):
        """Track a participant in a voice chat."""
        if chat_id not in self.voice_participants:
            self.voice_participants[chat_id] = {}
        
        self.voice_participants[chat_id][user_id] = time.time()
        
    async def remove_participant(self, chat_id: int, user_id: int):
        """Remove a participant from tracking."""
        if chat_id in self.voice_participants:
            self.voice_participants[chat_id].pop(user_id, None)
            
    async def clear_chat_participants(self, chat_id: int):
        """Clear all participants for a chat."""
        self.voice_participants.pop(chat_id, None)
        
    async def get_active_participants(self, chat_id: int, max_idle_time: int = 60) -> List[int]:
        """Get active participants in the voice chat."""
        if chat_id not in self.voice_participants:
            return []
            
        current_time = time.time()
        active_participants = []
        
        # Remove idle participants and collect active ones
        for user_id, last_active in list(self.voice_participants[chat_id].items()):
            if current_time - last_active > max_idle_time:
                self.voice_participants[chat_id].pop(user_id, None)
            else:
                active_participants.append(user_id)
                
        return active_participants
        
    async def add_reaction(self, chat_id: int, track_id: str, reaction: str, user_id: int):
        """Add a reaction to the current track."""
        if chat_id not in self.reaction_counts:
            self.reaction_counts[chat_id] = {}
            
        if track_id not in self.reaction_counts[chat_id]:
            self.reaction_counts[chat_id][track_id] = {
                "👍": set(),
                "👎": set(),
                "❤️": set(),
                "🔥": set(),
                "🎵": set()
            }
            
        # Valid reactions only
        if reaction not in self.reaction_counts[chat_id][track_id]:
            return False
            
        # Add user to the reaction set (one user = one reaction count)
        self.reaction_counts[chat_id][track_id][reaction].add(user_id)
        return True
        
    async def get_reactions(self, chat_id: int, track_id: str) -> Dict[str, int]:
        """Get reaction counts for a track."""
        if (chat_id not in self.reaction_counts or 
            track_id not in self.reaction_counts[chat_id]):
            return {
                "👍": 0,
                "👎": 0,
                "❤️": 0,
                "🔥": 0,
                "🎵": 0
            }
            
        # Convert sets to counts
        return {
            reaction: len(users) 
            for reaction, users in self.reaction_counts[chat_id][track_id].items()
        }
        
    async def create_participants_image(self, chat_id: int, track_info: Dict) -> Optional[str]:
        """Create an image showing active participants."""
        active_user_ids = await self.get_active_participants(chat_id)
        
        if not active_user_ids:
            return None
            
        # Try to get user information from Telegram
        participants_info = []
        try:
            for user_id in active_user_ids:
                try:
                    user = await self.client.get_users(user_id)
                    if user:
                        participants_info.append({
                            "id": user.id,
                            "name": user.first_name,
                            "username": user.username,
                            "photo": user.photo.small_file_id if user.photo else None
                        })
                except Exception as e:
                    logger.error(f"Failed to get user {user_id} info: {e}")
        except Exception as e:
            logger.error(f"Failed to get participants info: {e}")
            
        if not participants_info:
            return None
            
        # Create the image with participants and now playing info
        try:
            # Create a background image (800x400)
            image = Image.new('RGBA', (800, 400), (30, 30, 30, 240))
            draw = ImageDraw.Draw(image)
            
            # Draw now playing section
            draw.rectangle((0, 0, 800, 80), fill=(20, 20, 20, 255))
            draw.text((20, 15), "Now Playing:", fill=(255, 255, 255), font=self.fonts["bold"])
            draw.text((20, 45), track_info.get("name", "Unknown"), fill=(200, 200, 200), font=self.fonts["regular"])
            
            # Draw participants section
            draw.text((20, 100), f"Listeners: {len(participants_info)}", fill=(255, 255, 255), font=self.fonts["bold"])
            
            y_pos = 140
            for i, participant in enumerate(participants_info[:10]):  # Limit to 10 participants
                draw.text((40, y_pos), participant["name"], fill=(200, 200, 200), font=self.fonts["regular"])
                y_pos += 30
                
            # Add reactions if available
            reactions = await self.get_reactions(chat_id, track_info.get("id", ""))
            if any(reactions.values()):
                y_pos += 20
                draw.text((20, y_pos), "Reactions:", fill=(255, 255, 255), font=self.fonts["bold"])
                y_pos += 40
                
                x_pos = 40
                for reaction, count in reactions.items():
                    if count > 0:
                        reaction_text = f"{reaction} {count}"
                        draw.text((x_pos, y_pos), reaction_text, fill=(200, 200, 200), font=self.fonts["regular"])
                        x_pos += 80
            
            # Save the image
            file_path = f"cache/voice_overlay_{chat_id}_{int(time.time())}.png"
            os.makedirs("cache", exist_ok=True)
            image.save(file_path)
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to create participants image: {e}")
            return None
            
    async def send_voice_announcement(self, chat_id: int, track_info: Dict, replace_existing: bool = True):
        """Send or update an announcement message about the current voice chat."""
        try:
            # Create participants image
            image_path = await self.create_participants_image(chat_id, track_info)
            
            if not image_path:
                # If we can't create an image, don't send/update the announcement
                return None
                
            # Prepare buttons for reactions
            buttons = [
                [
                    types.InlineKeyboardButton("👍", callback_data=f"react_{track_info.get('id', '')}:👍"),
                    types.InlineKeyboardButton("❤️", callback_data=f"react_{track_info.get('id', '')}:❤️"),
                    types.InlineKeyboardButton("🔥", callback_data=f"react_{track_info.get('id', '')}:🔥"),
                ],
                [
                    types.InlineKeyboardButton("🎵 Join Voice Chat", callback_data="join_voice_chat")
                ]
            ]
            
            # Get active participants
            active_user_ids = await self.get_active_participants(chat_id)
            
            # Caption for the announcement
            caption = f"🎵 **Live Music Session**\n\n"
            caption += f"**Now Playing:** {track_info.get('name', 'Unknown')}\n"
            caption += f"**By:** {track_info.get('artists', 'Unknown')}\n\n"
            caption += f"**Listeners:** {len(active_user_ids)}\n\n"
            caption += "React to the song or join the voice chat!"
            
            # Send new message or update existing
            if replace_existing and chat_id in self.announcement_messages:
                try:
                    # Update existing message
                    await self.client.edit_message_media(
                        chat_id=chat_id,
                        message_id=self.announcement_messages[chat_id],
                        media=types.InputMediaPhoto(
                            media=image_path,
                            caption=caption
                        ),
                        reply_markup=types.InlineKeyboardMarkup(buttons)
                    )
                    return self.announcement_messages[chat_id]
                except Exception as e:
                    logger.error(f"Failed to update announcement: {e}")
                    # If updating fails, send a new message
                    
            # Send new announcement
            message = await self.client.send_photo(
                chat_id=chat_id,
                photo=image_path,
                caption=caption,
                reply_markup=types.InlineKeyboardMarkup(buttons)
            )
            
            if message:
                self.announcement_messages[chat_id] = message.id
                return message.id
                
            return None
            
        except Exception as e:
            logger.error(f"Failed to send voice announcement: {e}")
            return None
    
    async def _periodic_update(self):
        """Periodically update the voice overlay."""
        while True:
            try:
                # Update all active chat announcements every 30 seconds
                for chat_id in list(self.voice_participants.keys()):
                    # Only update if we have active participants
                    active_participants = await self.get_active_participants(chat_id)
                    if active_participants and chat_id in self.announcement_messages:
                        # Get the voice chat instance and current track
                        voice_chat = getattr(self.client, "voice_chat", None)
                        if voice_chat and chat_id in voice_chat.active_calls:
                            current_track = voice_chat.active_calls[chat_id].get("current_track")
                            if current_track:
                                # Update the announcement
                                await self.send_voice_announcement(chat_id, current_track, True)
                                
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                break
            except Exception as e:
                logger.error(f"Error in voice overlay update task: {e}")
                
            # Sleep for 30 seconds
            await asyncio.sleep(30)

    async def handle_voice_callback(self, callback_query):
        """Handle callback queries for voice chat overlay."""
        data = callback_query.data
        chat_id = callback_query.message.chat.id
        user_id = callback_query.from_user.id
        
        if data == "join_voice_chat":
            # Track the user as a participant
            await self.track_participant(chat_id, user_id)
            await callback_query.answer("Joining voice chat... You are now being tracked as a listener.")
            return
            
        if data.startswith("react_"):
            # Handle reaction
            parts = data.split(":")
            if len(parts) != 2:
                return
                
            track_id = parts[0][6:]  # Remove "react_" prefix
            reaction = parts[1]
            
            # Add the reaction
            success = await self.add_reaction(chat_id, track_id, reaction, user_id)
            
            if success:
                await callback_query.answer(f"You reacted with {reaction}")
                
                # Update the announcement with new reaction counts
                voice_chat = getattr(self.client, "voice_chat", None)
                if voice_chat and chat_id in voice_chat.active_calls:
                    current_track = voice_chat.active_calls[chat_id].get("current_track")
                    if current_track:
                        await self.send_voice_announcement(chat_id, current_track, True)
            else:
                await callback_query.answer("Invalid reaction")