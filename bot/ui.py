import logging
from typing import Dict, List, Union
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
            
            # Format lyrics
            formatted_lyrics = lyrics_client.format_lyrics_for_telegram(lyrics_data)
            
            # Create back button
            back_button = InlineKeyboardMarkup([
                [InlineKeyboardButton(BACK_BUTTON, callback_data="music_back_to_player")]
            ])
            
            # Send lyrics as a new message to avoid character limits
            await client.send_message(
                chat_id=chat_id,
                text=formatted_lyrics,
                reply_markup=back_button,
                disable_web_page_preview=False
            )
        
        else:
            await callback_query.answer("Unknown action")

async def show_queue_page(client, chat_id, message_id, queue, page):
    """Show a page of the queue."""
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

def get_player_controls(is_paused=False):
    """Get inline keyboard markup for player controls."""
    play_pause_button = InlineKeyboardButton(
        RESUME_BUTTON if is_paused else PAUSE_BUTTON,
        callback_data="music_resume" if is_paused else "music_pause"
    )
    
    return InlineKeyboardMarkup([
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
    ])

def get_main_keyboard():
    """Get main inline keyboard with basic options."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(PLAY_BUTTON, callback_data="music_play")],
        [InlineKeyboardButton(SEARCH_BUTTON, callback_data="music_search")],
        [InlineKeyboardButton(QUEUE_BUTTON, callback_data="music_queue")]
    ])

async def update_now_playing(client, chat_id, message_id, track, is_paused=False):
    """Update the now playing message with track info and controls."""
    from .helpers import format_duration
    
    text = f"🎵 **Now Playing**\n\n"
    text += f"**{track['name']}**\n"
    text += f"👤 {track['artists']}\n"
    text += f"💽 {track['album']}\n"
    text += f"⏱️ {format_duration(track['duration_ms'])}\n"
    
    # Add link to Spotify
    if track.get('external_url'):
        text += f"\n[Listen on Spotify]({track['external_url']})"
    
    await client.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=get_player_controls(is_paused),
        disable_web_page_preview=False
    )

async def update_player_controls(client, chat_id, message_id, is_paused=False):
    """Update just the player controls without changing the message text."""
    await client.edit_message_reply_markup(
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=get_player_controls(is_paused)
    )

async def send_now_playing(client, message, track, is_paused=False):
    """Send a new now playing message with track info and controls."""
    from .helpers import format_duration
    
    text = f"🎵 **Now Playing**\n\n"
    text += f"**{track['name']}**\n"
    text += f"👤 {track['artists']}\n"
    text += f"💽 {track['album']}\n"
    text += f"⏱️ {format_duration(track['duration_ms'])}\n"
    
    # Add link to Spotify
    if track.get('external_url'):
        text += f"\n[Listen on Spotify]({track['external_url']})"
    
    await message.reply(
        text,
        reply_markup=get_player_controls(is_paused)
    )

async def send_search_results(message, results):
    """Send search results as an inline keyboard."""
    if not results:
        await message.reply("No results found.")
        return
    
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
    
    await message.reply(
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
