import logging
import time
import asyncio
from typing import Dict, List, Union, Optional, Tuple, Any
from pyrogram import (
    types
)
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    Message
)

logger = logging.getLogger(__name__)

# Button text constants
PLAY_BUTTON = "▶️ Play"
PAUSE_BUTTON = "⏸ Pause"
RESUME_BUTTON = "▶️ Resume"
SKIP_BUTTON = "⏭️ Skip"
STOP_BUTTON = "⏹️ Stop"
VOLUME_UP_BUTTON = "🔊 Vol+"
VOLUME_DOWN_BUTTON = "🔉 Vol-"
QUEUE_BUTTON = "📋 Queue"
SEARCH_BUTTON = "🔍 Search"
REFRESH_BUTTON = "🔄 Refresh"
BACK_BUTTON = "⬅️ Back"

def create_ui_components(bot):
    """Register UI components and handlers."""
    
    @bot.on_callback_query(filters=lambda query: query.data.startswith("quiz_"))
    async def handle_quiz_callback(client, callback_query):
        """Handle callback queries for music quiz."""
        data = callback_query.data
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.id
        user_id = callback_query.from_user.id
        
        from .music_quiz import MusicQuiz
        
        # Get instance from bot
        quiz_manager = getattr(client, "quiz_manager", None)
        
        if not quiz_manager:
            logger.error("Quiz manager not initialized")
            await callback_query.answer("Quiz functionality is not available at the moment.")
            return
        
        # Get active quiz for this chat
        active_quiz = quiz_manager.get_quiz(chat_id)
        
        # Handle different quiz callback actions
        if data == "quiz_new":
            if active_quiz and active_quiz.is_active():
                await callback_query.answer("A quiz is already in progress!")
                return
            
            # Create a new quiz with default settings
            await callback_query.answer("Creating new quiz...")
            
            # Get user info for username mapping
            usernames = {}
            try:
                chat = await client.get_chat(chat_id)
                if chat.type != "private":
                    async for member in client.get_chat_members(chat_id):
                        if member.user and not member.user.is_bot:
                            usernames[member.user.id] = member.user.username or member.user.first_name
            except Exception as e:
                logger.error(f"Error getting chat members: {e}")
            
            # Create new quiz
            new_quiz = await quiz_manager.create_quiz(
                chat_id=chat_id,
                creator_id=user_id,
                num_questions=5  # Default number of questions
            )
            
            if new_quiz:
                # Send first question
                await new_quiz.send_question(client, chat_id, usernames)
                await callback_query.message.delete()
            else:
                await callback_query.answer("Failed to create a new quiz. Please try again later.")
        
        elif data.startswith("quiz_answer_"):
            if not active_quiz:
                await callback_query.answer("No active quiz in this chat.")
                return
                
            # Extract answer option index
            try:
                option_index = int(data.split("_")[-1])
            except ValueError:
                await callback_query.answer("Invalid option.")
                return
            
            # Record the user's answer
            answer_added, is_correct, points = active_quiz.add_answer(user_id, option_index)
            
            if not answer_added:
                await callback_query.answer("You already answered this question!")
                return
            
            # Inform the user about their answer
            if is_correct:
                await callback_query.answer(f"Correct! +{points} points")
            else:
                await callback_query.answer("Incorrect!")
                
            # Check if all users have answered or time is up
            # If this is the last person to answer, move to next question
            users_answered = len(active_quiz.get_current_question().answered_by)
            
            # Get user info for username mapping
            usernames = {}
            try:
                chat = await client.get_chat(chat_id)
                if chat.type != "private":
                    async for member in client.get_chat_members(chat_id):
                        if member.user and not member.user.is_bot:
                            usernames[member.user.id] = member.user.username or member.user.first_name
            except Exception as e:
                logger.error(f"Error getting chat members: {e}")
            
            # Move to next question if we've hit the threshold
            # For simplicity, we'll continue after a certain number of answers or a fixed time delay
            chat_participants = len(usernames) or 5
            answer_threshold = min(chat_participants, 5)  # Either all users or max 5
            
            if users_answered >= answer_threshold:
                # Show correct answer
                correct_answer = active_quiz.get_current_question().get_correct_answer()
                correct_details = active_quiz.get_current_question().get_correct_answer_details()
                
                await client.send_message(
                    chat_id=chat_id,
                    text=f"⏱ Time's up!\n\n✅ The correct answer is: **{correct_answer}**\n{correct_details}"
                )
                
                # Delay for a moment to let users see the correct answer
                await asyncio.sleep(3)
                
                # Move to next question
                next_question = active_quiz.next_question()
                
                if next_question:
                    # Send next question
                    await active_quiz.send_question(client, chat_id, usernames)
                else:
                    # End of quiz, show results
                    await active_quiz.send_results(client, chat_id, usernames)
                    quiz_manager.end_quiz(chat_id)
        
        elif data == "quiz_end":
            if not active_quiz:
                await callback_query.answer("No active quiz to end.")
                return
            
            # Get user info for username mapping
            usernames = {}
            try:
                chat = await client.get_chat(chat_id)
                if chat.type != "private":
                    async for member in client.get_chat_members(chat_id):
                        if member.user and not member.user.is_bot:
                            usernames[member.user.id] = member.user.username or member.user.first_name
            except Exception as e:
                logger.error(f"Error getting chat members: {e}")
            
            # Show results and end quiz
            await active_quiz.send_results(client, chat_id, usernames)
            quiz_manager.end_quiz(chat_id)
            await callback_query.answer("Quiz ended.")
            
            # Delete the callback message
            try:
                await callback_query.message.delete()
            except Exception as e:
                logger.error(f"Failed to delete message: {e}")
    
    @bot.on_callback_query(filters=lambda query: query.data.startswith("music_"))
    async def handle_music_callback(client, callback_query):
        """Handle callback queries for music controls."""
        data = callback_query.data
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.id
        user_id = callback_query.from_user.id
        
        from .voice_chat import VoiceChat
        from .queue_manager import QueueManager
        
        # Get instances from bot
        voice_chat = getattr(client, "voice_chat", None)
        queue_manager = getattr(client, "queue_manager", None)
        
        if not voice_chat or not queue_manager:
            logger.error("Voice chat or queue manager not initialized")
            await callback_query.answer("Bot is not fully initialized, please try again later.")
            return
        
        # Handle different callback actions
        if data == "music_pause":
            success, message = await voice_chat.pause(chat_id)
            if success:
                await update_player_controls(client, chat_id, message_id, is_paused=True)
            await callback_query.answer(message)
            
        elif data == "music_resume":
            success, message = await voice_chat.resume(chat_id)
            if success:
                await update_player_controls(client, chat_id, message_id, is_paused=False)
            await callback_query.answer(message)
            
        elif data == "music_skip":
            success, message = await voice_chat.skip(chat_id)
            if success:
                current_track = voice_chat.active_calls[chat_id]["current_track"]
                await update_now_playing(client, chat_id, message_id, current_track)
            await callback_query.answer(message)
            
        elif data == "music_stop":
            success, message = await voice_chat.leave_voice_chat(chat_id)
            if success:
                await callback_query.message.edit_text(
                    "⏹️ Playback stopped and left voice chat",
                    reply_markup=None
                )
            await callback_query.answer(message)
            
        elif data == "music_volume_up":
            current_volume = voice_chat.active_calls.get(chat_id, {}).get("volume", 100)
            new_volume = min(current_volume + 10, 200)
            success, message = await voice_chat.set_volume(chat_id, new_volume)
            await callback_query.answer(message)
            
        elif data == "music_volume_down":
            current_volume = voice_chat.active_calls.get(chat_id, {}).get("volume", 100)
            new_volume = max(current_volume - 10, 0)
            success, message = await voice_chat.set_volume(chat_id, new_volume)
            await callback_query.answer(message)
            
        elif data == "music_queue":
            queue = queue_manager.get_queue(chat_id)
            if not queue:
                await callback_query.answer("Queue is empty")
                return
            
            # Show first page of queue
            await show_queue_page(client, chat_id, message_id, queue, 0)
            await callback_query.answer("Queue loaded")
            
        elif data.startswith("music_queue_page_"):
            # Handle queue pagination
            page = int(data.split("_")[-1])
            queue = queue_manager.get_queue(chat_id)
            await show_queue_page(client, chat_id, message_id, queue, page)
            await callback_query.answer(f"Page {page+1}")
            
        elif data == "music_back_to_player":
            # Return to player view
            current_track = voice_chat.active_calls.get(chat_id, {}).get("current_track")
            if current_track:
                is_paused = False  # We would need to track this state
                await update_now_playing(client, chat_id, message_id, current_track, is_paused)
            else:
                await callback_query.message.edit_text(
                    "No track currently playing",
                    reply_markup=get_main_keyboard()
                )
            await callback_query.answer("Back to player")
            
        elif data == "music_refresh":
            # Refresh the player UI
            current_track = voice_chat.active_calls.get(chat_id, {}).get("current_track")
            if current_track:
                is_paused = False  # We would need to track this state
                await update_now_playing(client, chat_id, message_id, current_track, is_paused)
                await callback_query.answer("Player refreshed")
            else:
                await callback_query.message.edit_text(
                    "No track currently playing",
                    reply_markup=get_main_keyboard()
                )
                await callback_query.answer("No active playback")
                
        elif data == "music_lyrics":
            # Get lyrics for the current track
            current_track = voice_chat.active_calls.get(chat_id, {}).get("current_track")
            if not current_track:
                await callback_query.answer("No track currently playing")
                return
            
            # Get instances from bot
            lyrics_client = getattr(client, "lyrics_client", None)
            if not lyrics_client:
                logger.error("Lyrics client not initialized")
                await callback_query.answer("Lyrics functionality is not available")
                return
            
            await callback_query.answer("Searching for lyrics...")
            
            # Get song name and artist
            song_name = current_track["name"]
            artist_name = current_track["artists"]
            
            # Get lyrics
            lyrics_data = await lyrics_client.get_lyrics_by_search(song_name, artist_name)
            
            # Create back button
            back_button = InlineKeyboardMarkup([
                [InlineKeyboardButton(BACK_BUTTON, callback_data="music_back_to_player")]
            ])
            
            # Send enhanced lyrics display
            await send_lyrics_with_visual(client, chat_id, lyrics_data, current_track, back_button)
        
        else:
            await callback_query.answer("Unknown action")

async def show_queue_page(client, chat_id, message_id, queue, page):
    """Show a page of the queue with visual elements."""
    from .image_ui import ImageUI
    
    items_per_page = 5
    total_pages = (len(queue) + items_per_page - 1) // items_per_page
    
    if not queue or page >= total_pages:
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Queue is empty",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(BACK_BUTTON, callback_data="music_back_to_player")
            ]])
        )
        return
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(queue))
    
    # Get image_ui instance
    image_ui = getattr(client, "image_ui", None)
    if not image_ui:
        image_ui = ImageUI()
        client.image_ui = image_ui
    
    # Try to create a visual representation of the queue
    if hasattr(image_ui, 'create_playlist_image'):
        try:
            image_path = await image_ui.create_playlist_image(
                playlist_name="Music Queue",
                track_count=len(queue),
                created_by=None
            )
            
            # Prepare caption text
            text = "🎵 **Music Queue**\n\n"
            for i, track in enumerate(queue[start_idx:end_idx], start=start_idx + 1):
                text += f"{i}. **{track['name']}** - {track['artists']}\n"
            
            text += f"\nPage {page+1}/{total_pages} | Total: {len(queue)} tracks"
            
            # Create pagination buttons
            buttons = []
            if total_pages > 1:
                pagination_row = []
                if page > 0:
                    pagination_row.append(
                        InlineKeyboardButton("⬅️", callback_data=f"music_queue_page_{page-1}")
                    )
                
                pagination_row.append(
                    InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="music_refresh")
                )
                
                if page < total_pages - 1:
                    pagination_row.append(
                        InlineKeyboardButton("➡️", callback_data=f"music_queue_page_{page+1}")
                    )
                
                buttons.append(pagination_row)
            
            # Add back button
            buttons.append([
                InlineKeyboardButton(BACK_BUTTON, callback_data="music_back_to_player")
            ])
            
            if image_path:
                # Edit message with image
                try:
                    await client.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id,
                        media=types.InputMediaPhoto(
                            media=image_path,
                            caption=text
                        ),
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                    return
                except Exception as e:
                    logger.error(f"Error updating queue with image: {e}")
                    # Fall back to text-only update below
            
        except Exception as e:
            logger.error(f"Failed to create playlist image: {e}")
            # Fall back to text-only update
    
    # Text-only fallback
    text = "🎵 **Music Queue**\n\n"
    for i, track in enumerate(queue[start_idx:end_idx], start=start_idx + 1):
        text += f"{i}. **{track['name']}** - {track['artists']}\n"
    
    text += f"\nPage {page+1}/{total_pages} | Total: {len(queue)} tracks"
    
    # Create pagination buttons
    buttons = []
    if total_pages > 1:
        pagination_row = []
        if page > 0:
            pagination_row.append(
                InlineKeyboardButton("⬅️", callback_data=f"music_queue_page_{page-1}")
            )
        
        pagination_row.append(
            InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="music_refresh")
        )
        
        if page < total_pages - 1:
            pagination_row.append(
                InlineKeyboardButton("➡️", callback_data=f"music_queue_page_{page+1}")
            )
        
        buttons.append(pagination_row)
    
    # Add back button
    buttons.append([
        InlineKeyboardButton(BACK_BUTTON, callback_data="music_back_to_player")
    ])
    
    await client.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def get_player_controls(is_paused=False, config=None):
    """Get inline keyboard markup for player controls."""
    play_pause_button = InlineKeyboardButton(
        RESUME_BUTTON if is_paused else PAUSE_BUTTON,
        callback_data="music_resume" if is_paused else "music_pause"
    )
    
    buttons = [
        [play_pause_button, InlineKeyboardButton(SKIP_BUTTON, callback_data="music_skip")],
        [
            InlineKeyboardButton(VOLUME_DOWN_BUTTON, callback_data="music_volume_down"),
            InlineKeyboardButton(STOP_BUTTON, callback_data="music_stop"),
            InlineKeyboardButton(VOLUME_UP_BUTTON, callback_data="music_volume_up")
        ],
        [
            InlineKeyboardButton(QUEUE_BUTTON, callback_data="music_queue"),
            InlineKeyboardButton("🎵 Lyrics", callback_data="music_lyrics")
        ],
        [InlineKeyboardButton(REFRESH_BUTTON, callback_data="music_refresh")]
    ]
    
    # Add owner and updates buttons if configured
    owner_updates_row = []
    if config:
        if config.OWNER_USERNAME and config.OWNER_URL:
            owner_updates_row.append(
                InlineKeyboardButton("👤 OWNER", url=config.OWNER_URL)
            )
        if config.UPDATES_CHANNEL and config.UPDATES_CHANNEL_URL:
            owner_updates_row.append(
                InlineKeyboardButton("📢 UPDATES", url=config.UPDATES_CHANNEL_URL)
            )
    
    if owner_updates_row:
        buttons.append(owner_updates_row)
    
    return InlineKeyboardMarkup(buttons)

def get_main_keyboard():
    """Get main inline keyboard with basic options."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(PLAY_BUTTON, callback_data="music_play")],
        [InlineKeyboardButton(SEARCH_BUTTON, callback_data="music_search")],
        [InlineKeyboardButton(QUEUE_BUTTON, callback_data="music_queue")],
        [InlineKeyboardButton("🎮 Music Quiz", callback_data="quiz_new")]
    ])

async def update_now_playing(client, chat_id, message_id, track, is_paused=False):
    """Update the now playing message with track info and controls."""
    from .helpers import format_duration
    from .image_ui import ImageUI
    
    # Get instances from client
    image_ui = getattr(client, "image_ui", None)
    if not image_ui:
        image_ui = ImageUI()
        client.image_ui = image_ui
    
    # Get config from client
    config = getattr(client, "config", None)
    
    # Calculate progress (in a real implementation, this would come from the voice chat)
    progress = 0.0
    voice_chat = getattr(client, "voice_chat", None)
    if voice_chat and chat_id in voice_chat.active_calls:
        start_time = voice_chat.active_calls[chat_id].get("start_time", 0)
        duration = track.get("duration_ms", 0) / 1000
        if start_time > 0 and duration > 0:
            elapsed = time.time() - start_time
            progress = min(elapsed / duration, 1.0)
    
    # Generate the now playing image
    image_path = await image_ui.create_now_playing_image(track, progress)
    
    text = f"🎵 **Now Playing**\n\n"
    text += f"**{track['name']}**\n"
    text += f"👤 {track['artists']}\n"
    text += f"💽 {track['album']}\n"
    text += f"⏱️ {format_duration(track['duration_ms'])}\n"
    
    # Add link to Spotify
    if track.get('external_url'):
        text += f"\n[Listen on Spotify]({track['external_url']})"
    
    if image_path:
        # Send/update with the generated image
        try:
            await client.edit_message_media(
                chat_id=chat_id,
                message_id=message_id,
                media=types.InputMediaPhoto(
                    media=image_path,
                    caption=text
                ),
                reply_markup=get_player_controls(is_paused, config)
            )
        except Exception as e:
            logger.error(f"Error updating message with image: {e}")
            # Fallback to text-only update
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=get_player_controls(is_paused, config),
                disable_web_page_preview=False
            )
    else:
        # No image, just update text
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=get_player_controls(is_paused, config),
            disable_web_page_preview=False
        )

async def update_player_controls(client, chat_id, message_id, is_paused=False):
    """Update just the player controls without changing the message text."""
    # Get config from client
    config = getattr(client, "config", None)
    
    await client.edit_message_reply_markup(
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=get_player_controls(is_paused, config)
    )

async def send_now_playing(client, message, track, is_paused=False):
    """Send a new now playing message with track info and controls."""
    from .helpers import format_duration
    from .image_ui import ImageUI
    
    # Get instances from client
    image_ui = getattr(client, "image_ui", None)
    if not image_ui:
        image_ui = ImageUI()
        client.image_ui = image_ui
    
    # Get config from client
    config = getattr(client, "config", None)
    
    # Calculate initial progress
    progress = 0.0
    
    # Generate the now playing image
    image_path = await image_ui.create_now_playing_image(track, progress)
    
    text = f"🎵 **Now Playing**\n\n"
    text += f"**{track['name']}**\n"
    text += f"👤 {track['artists']}\n"
    text += f"💽 {track['album']}\n"
    text += f"⏱️ {format_duration(track['duration_ms'])}\n"
    
    # Add link to Spotify
    if track.get('external_url'):
        text += f"\n[Listen on Spotify]({track['external_url']})"
    
    if image_path:
        # Send with the generated image
        try:
            return await message.reply_photo(
                photo=image_path,
                caption=text,
                reply_markup=get_player_controls(is_paused, config)
            )
        except Exception as e:
            logger.error(f"Error sending message with image: {e}")
            # Fallback to text-only
            return await message.reply(
                text,
                reply_markup=get_player_controls(is_paused, config)
            )
    else:
        # No image, just send text
        return await message.reply(
            text,
            reply_markup=get_player_controls(is_paused, config)
        )

async def send_search_results(message, results):
    """Send search results as an inline keyboard with visual elements."""
    from .image_ui import ImageUI
    
    if not results:
        await message.reply("No results found.")
        return
    
    # Get client from message
    client = message._client
    
    # Get image_ui instance
    image_ui = getattr(client, "image_ui", None)
    if not image_ui:
        image_ui = ImageUI()
        client.image_ui = image_ui
    
    text = "🔍 **Search Results**\n\nSelect a track to play:"
    
    buttons = []
    for i, track in enumerate(results[:8]):  # Limit to 8 results
        buttons.append([
            InlineKeyboardButton(
                f"{i+1}. {track['name']} - {track['artists']}",
                callback_data=f"play_{track['id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")])
    
    # Try to create a visual representation of the top result
    try:
        if results and hasattr(image_ui, 'create_now_playing_image'):
            top_track = results[0]
            
            # Generate image for the top result
            image_path = await image_ui.create_now_playing_image(top_track, 0.0)
            
            if image_path:
                # Enhanced caption for the image
                caption = "🔍 **Search Results**\n\n"
                caption += f"**Top Result: {top_track['name']}**\n"
                caption += f"👤 {top_track['artists']}\n\n"
                caption += "Select a track to play:"
                
                # Send with image
                await message.reply_photo(
                    photo=image_path,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                return
    except Exception as e:
        logger.error(f"Error creating search results image: {e}")
        # Fall back to text-only response
    
    # Text-only fallback
    await message.reply(
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def send_lyrics_with_visual(client, chat_id, lyrics_data, track_info, reply_markup=None):
    """Send lyrics with visual enhancement."""
    from .image_ui import ImageUI
    
    if not lyrics_data:
        # No lyrics found
        await client.send_message(
            chat_id=chat_id,
            text="❌ No lyrics found for this track.",
            reply_markup=reply_markup
        )
        return
    
    # Format the lyrics
    lyrics_client = getattr(client, "lyrics_client", None)
    if lyrics_client and hasattr(lyrics_client, "format_lyrics_for_telegram"):
        formatted_lyrics = lyrics_client.format_lyrics_for_telegram(lyrics_data)
    else:
        # Basic formatting as fallback
        title = lyrics_data.get("title", "Unknown")
        artist = lyrics_data.get("artist", "Unknown")
        lyrics = lyrics_data.get("lyrics", "No lyrics available")
        
        formatted_lyrics = f"🎵 **{title}**\n👤 {artist}\n\n{lyrics}"
    
    # Get image_ui instance
    image_ui = getattr(client, "image_ui", None)
    if not image_ui:
        image_ui = ImageUI()
        client.image_ui = image_ui
    
    # Try to create a visual representation for the lyrics
    try:
        if hasattr(image_ui, 'create_now_playing_image'):
            # Use the now playing image (could be specialized for lyrics in a real implementation)
            image_path = await image_ui.create_now_playing_image(track_info, 0.0)
            
            if image_path:
                # Since lyrics can be long, we'll send a preview image first and then the full lyrics
                preview_text = f"🎵 **Lyrics for {track_info['name']}**\n"
                preview_text += f"👤 {track_info['artists']}\n\n"
                
                # Add a short preview of the lyrics (first few lines)
                lyrics_preview = lyrics_data.get("lyrics", "")
                if lyrics_preview:
                    # Get first few lines
                    preview_lines = lyrics_preview.split('\n')[:4]
                    preview_text += '\n'.join(preview_lines)
                    if len(preview_lines) < len(lyrics_preview.split('\n')):
                        preview_text += "\n\n[Full lyrics below...]"
                
                # Send the image with preview
                await client.send_photo(
                    chat_id=chat_id,
                    photo=image_path,
                    caption=preview_text
                )
                
                # Then send the full lyrics
                await client.send_message(
                    chat_id=chat_id,
                    text=formatted_lyrics,
                    reply_markup=reply_markup,
                    disable_web_page_preview=False
                )
                return
    except Exception as e:
        logger.error(f"Error creating lyrics visual: {e}")
        # Fall back to text-only response
    
    # Text-only fallback
    await client.send_message(
        chat_id=chat_id,
        text=formatted_lyrics,
        reply_markup=reply_markup,
        disable_web_page_preview=False
    )

async def send_quiz_results(client, chat_id, total_questions, correct_answers, 
                          total_participants, top_scorers, reply_markup=None):
    """Send quiz results with visual enhancement."""
    from .image_ui import ImageUI
    
    # Get image_ui instance
    image_ui = getattr(client, "image_ui", None)
    if not image_ui:
        image_ui = ImageUI()
        client.image_ui = image_ui
    
    # Try to create a visual representation of the quiz results
    try:
        if hasattr(image_ui, 'create_quiz_results_image'):
            # Generate an image for the quiz results
            image_path = await image_ui.create_quiz_results_image(
                total_questions=total_questions,
                correct_answers=correct_answers,
                total_participants=total_participants,
                top_scorers=top_scorers
            )
            
            if image_path:
                # Create caption text
                caption = f"🎵 **Music Quiz Results**\n\n"
                caption += f"**Questions:** {total_questions}\n"
                caption += f"**Correct Answers:** {correct_answers}\n"
                caption += f"**Participants:** {total_participants}\n\n"
                
                if top_scorers:
                    caption += "**Top Scorers:**\n"
                    for i, (username, score) in enumerate(top_scorers[:3], 1):
                        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                        caption += f"{medal} {username}: {score} points\n"
                
                # Send the image with caption
                await client.send_photo(
                    chat_id=chat_id,
                    photo=image_path,
                    caption=caption,
                    reply_markup=reply_markup
                )
                return
    except Exception as e:
        logger.error(f"Error creating quiz results image: {e}")
        # Fall back to text-only response
    
    # Text-only fallback
    text = f"🎵 **Music Quiz Results**\n\n"
    text += f"**Questions:** {total_questions}\n"
    text += f"**Correct Answers:** {correct_answers}\n"
    text += f"**Participants:** {total_participants}\n\n"
    
    if top_scorers:
        text += "**Top Scorers:**\n"
        for i, (username, score) in enumerate(top_scorers[:5], 1):
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            text += f"{medal} {username}: {score} points\n"
    
    await client.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup
    )

async def send_quiz_question(client, message, question_number, total_questions, track_info, 
                           question_type, options, reply_markup=None):
    """Send a music quiz question with visual enhancement."""
    from .image_ui import ImageUI
    
    # Get image_ui instance
    image_ui = getattr(client, "image_ui", None)
    if not image_ui:
        image_ui = ImageUI()
        client.image_ui = image_ui
    
    # Try to create a visual representation of the quiz question
    try:
        if hasattr(image_ui, 'create_quiz_question_image'):
            # Generate an image for the quiz question
            image_path = await image_ui.create_quiz_question_image(
                question_number=question_number,
                total_questions=total_questions,
                track_info=track_info,
                question_type=question_type,
                options=options
            )
            
            if image_path:
                # Create caption text
                if question_type == "guess_song":
                    caption = f"🎵 **Music Quiz - Question {question_number}/{total_questions}**\n\n"
                    caption += "**Name this song:**\n\n"
                elif question_type == "guess_artist":
                    caption = f"🎵 **Music Quiz - Question {question_number}/{total_questions}**\n\n"
                    caption += "**Who is the artist of this song?**\n\n"
                elif question_type == "finish_lyrics":
                    caption = f"🎵 **Music Quiz - Question {question_number}/{total_questions}**\n\n"
                    caption += "**Complete the lyrics:**\n\n"
                    if "lyrics_fragment" in track_info:
                        caption += f"*\"{track_info['lyrics_fragment']}...\"*\n\n"
                else:
                    caption = f"🎵 **Music Quiz - Question {question_number}/{total_questions}**\n\n"
                
                # List options in the caption
                caption += "**Options:**\n"
                option_labels = ["A", "B", "C", "D"]
                for i, option in enumerate(options[:4]):
                    caption += f"{option_labels[i]}. {option}\n"
                
                # Send the image with the caption
                return await message.reply_photo(
                    photo=image_path,
                    caption=caption,
                    reply_markup=reply_markup
                )
    except Exception as e:
        logger.error(f"Error creating quiz question image: {e}")
        # Fall back to text-only response
    
    # Text-only fallback
    if question_type == "guess_song":
        text = f"🎵 **Music Quiz - Question {question_number}/{total_questions}**\n\n"
        text += "**Name this song:**\n\n"
    elif question_type == "guess_artist":
        text = f"🎵 **Music Quiz - Question {question_number}/{total_questions}**\n\n"
        text += "**Who is the artist of this song?**\n\n"
    elif question_type == "finish_lyrics":
        text = f"🎵 **Music Quiz - Question {question_number}/{total_questions}**\n\n"
        text += "**Complete the lyrics:**\n\n"
        if "lyrics_fragment" in track_info:
            text += f"*\"{track_info['lyrics_fragment']}...\"*\n\n"
    else:
        text = f"🎵 **Music Quiz - Question {question_number}/{total_questions}**\n\n"
    
    # List options in the text
    text += "**Options:**\n"
    option_labels = ["A", "B", "C", "D"]
    for i, option in enumerate(options[:4]):
        text += f"{option_labels[i]}. {option}\n"
    
    return await message.reply(
        text,
        reply_markup=reply_markup
    )
