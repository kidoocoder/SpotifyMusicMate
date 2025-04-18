import asyncio
import logging
import os
import time
import re
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from .helpers import (
    format_duration,
    rate_limiter,
    is_admin,
    extract_user_and_text,
    format_time
)
from .ui import send_now_playing, send_search_results
from .start import handle_start_command, handle_owner_command

logger = logging.getLogger(__name__)

def register_commands(bot, voice_chat, queue_manager, spotify, database, lyrics_client, config=None):
    """Register command handlers for the bot."""
    # Store instances for callback query handlers
    bot.voice_chat = voice_chat
    bot.queue_manager = queue_manager
    bot.spotify = spotify
    bot.database = database
    bot.lyrics_client = lyrics_client
    bot.config = config
    
    # Voice overlay callbacks
    @bot.on_callback_query(filters=lambda query: query.data == "join_voice_chat" or query.data.startswith("react_"))
    async def voice_overlay_callbacks(client, callback_query):
        """Handle callbacks for voice overlay reactions and actions."""
        if not hasattr(client, "voice_overlay"):
            await callback_query.answer("Voice overlay not available")
            return
            
        # Delegate to the voice overlay handler
        await client.voice_overlay.handle_voice_callback(callback_query)
    
    @bot.on_message(filters.command(["start"]))
    async def cmd_start(client, message: Message):
        """Enhanced handler for /start command showing user profile picture."""
        # Send immediate typing action for better user experience
        await client.send_chat_action(message.chat.id, "typing")
        
        user_id = message.from_user.id if message.from_user else None
        
        # Record user activity in background
        if user_id:
            asyncio.create_task(database.record_user_activity(user_id, "start"))
        
        # Use the enhanced start command handler
        await handle_start_command(client, message, config)
    
    @bot.on_message(filters.command(["help"]))
    async def cmd_help(client, message: Message):
        """Handler for /help command."""
        # Send immediate typing action for better user experience
        await client.send_chat_action(message.chat.id, "typing")
        
        user_id = message.from_user.id if message.from_user else None
        
        # Record user activity in background to avoid delay
        if user_id:
            asyncio.create_task(database.record_user_activity(user_id, "help"))
        
        help_text = """
🎵 **Music Bot Help** 🎵

**Basic Commands:**
/play [song name or Spotify URL] - Play a song in voice chat
/pause - Pause the current song
/resume - Resume the current song
/skip - Skip to the next song
/stop - Stop playback and leave voice chat
/queue - Show the current queue
/current - Show the current song
/search [query] - Search for a song
/lyrics [optional: song name] - Get lyrics for current song

**User Commands:**
/profile - View your user profile
/settings - Configure your preferences
/favorite - Add current song to favorites
/favorites - Show your favorite songs

**Advanced Commands:**
/volume [0-200] - Set the volume (default: 100)
/listeners - See who's listening in the voice chat
/ping - Check bot latency
/stats - Show bot statistics

**Fun & Games:**
/quiz [num_questions] [difficulty] [genre] - Start a music quiz
    • num_questions: 1-10 (default: 5)
    • difficulty: easy, medium, hard (default: medium)
    • genre: (optional) specify a music genre

Start by using /play command to play music in a voice chat!
        """
        await message.reply(help_text)
    
    @bot.on_message(filters.command("play"))
    async def cmd_play(client, message: Message):
        """Handler for /play command."""
        # Send immediate typing action for better user experience
        await client.send_chat_action(message.chat.id, "typing")
        
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Check for rate limiting (more lenient for better user experience)
        if not await rate_limiter(user_id, "play", limit=5, time_window=10):
            await message.reply("You're using this command too frequently! Please wait a bit.")
            return
        
        # Get the query
        query = message.text.split(" ", 1)
        if len(query) < 2:
            await message.reply("Please provide a song name or Spotify link.\nUsage: `/play song name or link`")
            return
        
        query = query[1].strip()
        
        # Send a temporary message immediately
        status_msg = await message.reply("🔍 Searching...")
        
        # Optimize the search process
        # Check if it's a Spotify link for faster processing
        is_spotify_link = "spotify.com/track/" in query
        
        # Create task for searching
        search_task = None
        if is_spotify_link:
            track_id = query.split("spotify.com/track/")[1].split("?")[0]
            search_task = asyncio.create_task(spotify.get_track(track_id))
        else:
            search_task = asyncio.create_task(spotify.search(query))
        
        # Check if we're already in a voice chat while waiting for search results
        voice_check_task = None
        if chat_id not in voice_chat.active_calls:
            # Prepare to join voice chat in parallel
            voice_check_task = asyncio.create_task(voice_chat.join_voice_chat(chat_id, user_id))
        
        # Wait for search results
        result = await search_task
        
        # Process search results
        if is_spotify_link:
            if not result:
                await status_msg.edit_text("❌ Failed to get track information from Spotify.")
                return
            tracks = [result]
        else:
            tracks = result
            
        if not tracks:
            await status_msg.edit_text("❌ No tracks found matching your query.")
            return
        
        # Get the first track
        track = tracks[0]
        
        # Check voice chat status
        if chat_id not in voice_chat.active_calls:
            # If we started joining earlier, wait for the result
            if voice_check_task:
                await status_msg.edit_text("🔄 Joining voice chat...")
                success = await voice_check_task
                if not success:
                    await status_msg.edit_text("❌ Failed to join voice chat. Make sure I have the right permissions and there's an active voice chat.")
                    return
            else:
                # Otherwise join now
                await status_msg.edit_text("🔄 Joining voice chat...")
                success = await voice_chat.join_voice_chat(chat_id, user_id)
                if not success:
                    await status_msg.edit_text("❌ Failed to join voice chat. Make sure I have the right permissions and there's an active voice chat.")
                    return
                
        # Check if something is already playing and add to queue if needed
        if voice_chat.active_calls[chat_id].get("current_track"):
            await status_msg.edit_text(f"🔄 Adding **{track['name']}** to the queue...")
            success, message_text = await queue_manager.add_to_queue(chat_id, track, user_id)
            await status_msg.edit_text(message_text)
            
            # Record activity in background
            asyncio.create_task(database.record_user_activity(user_id, "play", chat_id))
            return
        
        # Otherwise, play the track
        await status_msg.edit_text(f"🔄 Downloading **{track['name']}**...")
        
        # Download track 
        downloaded_track = await spotify.download_track(track)
        if not downloaded_track:
            await status_msg.edit_text(f"❌ Failed to download **{track['name']}**. Spotify preview might not be available.")
            return
        
        # Play the track
        success, message_text = await voice_chat.play_track(chat_id, downloaded_track, user_id)
        
        if success:
            # Start database updates in background to speed up response
            asyncio.create_task(database.add_played_track(chat_id, downloaded_track, user_id))
            asyncio.create_task(database.record_user_activity(user_id, "play", chat_id))
            
            # Update UI
            await status_msg.delete()
            await send_now_playing(client, message, downloaded_track)
        else:
            await status_msg.edit_text(f"❌ Error: {message_text}")
    
    @bot.on_message(filters.command("search"))
    async def cmd_search(client, message: Message):
        """Handler for /search command."""
        user_id = message.from_user.id
        
        # Check for rate limiting
        if not await rate_limiter(user_id, "search", limit=2, time_window=10):
            await message.reply("You're using this command too frequently! Please wait a bit.")
            return
        
        # Get the query
        query = message.text.split(" ", 1)
        if len(query) < 2:
            await message.reply("Please provide a search query.\nUsage: `/search song name`")
            return
        
        query = query[1].strip()
        
        # Send a temporary message
        status_msg = await message.reply("🔍 Searching...")
        
        # Search for tracks
        tracks = await spotify.search(query, limit=8)
        
        if not tracks:
            await status_msg.edit_text("❌ No tracks found matching your query.")
            return
        
        # Delete the status message
        await status_msg.delete()
        
        # Send search results
        await send_search_results(message, tracks)
    
    @bot.on_callback_query(filters=lambda query: query.data.startswith("play_"))
    async def callback_play_song(client, callback_query):
        """Handle callback for playing a song from search results."""
        # Immediately acknowledge that we received the callback
        await callback_query.answer("Processing your selection...")
        
        track_id = callback_query.data.split("_")[1]
        chat_id = callback_query.message.chat.id
        user_id = callback_query.from_user.id
        message_id = callback_query.message.id
        
        # Edit the message immediately to show we're processing
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🔄 Processing your selection..."
        )
        
        # Start asynchronous tasks in parallel
        # 1. Get track information
        track_task = asyncio.create_task(spotify.get_track(track_id))
        
        # 2. Check if we need to join voice chat and start that process
        voice_check_task = None
        if chat_id not in voice_chat.active_calls:
            voice_check_task = asyncio.create_task(voice_chat.join_voice_chat(chat_id, user_id))
        
        # Wait for track info first
        track = await track_task
        if not track:
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ Failed to get track information from Spotify."
            )
            return
        
        # Edit the message with track details
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"🔄 Selected: **{track['name']}** by {track['artists']}"
        )
        
        # Check voice chat status
        if chat_id not in voice_chat.active_calls:
            # If we started joining earlier, wait for result
            if voice_check_task:
                await client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"🔄 Joining voice chat..."
                )
                success = await voice_check_task
                if not success:
                    await client.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ Failed to join voice chat. Make sure I have the right permissions and there's an active voice chat."
                    )
                    return
            else:
                # Otherwise join now
                await client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"🔄 Joining voice chat..."
                )
                success = await voice_chat.join_voice_chat(chat_id, user_id)
                if not success:
                    await client.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ Failed to join voice chat. Make sure I have the right permissions and there's an active voice chat."
                    )
                    return
        
        # Check if something is already playing and add to queue if needed
        if voice_chat.active_calls[chat_id].get("current_track"):
            # Add to queue
            success, message_text = await queue_manager.add_to_queue(chat_id, track, user_id)
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text
            )
            
            # Record activity in background
            asyncio.create_task(database.record_user_activity(user_id, "play", chat_id))
            await callback_query.answer("Added to queue!")
            return
        
        # Otherwise, play the track
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"🔄 Downloading **{track['name']}**..."
        )
        
        # Download track
        downloaded_track = await spotify.download_track(track)
        if not downloaded_track:
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ Failed to download **{track['name']}**. Spotify preview might not be available."
            )
            return
        
        # Play the track
        success, message_text = await voice_chat.play_track(chat_id, downloaded_track, user_id)
        
        if success:
            # Start database updates in background
            asyncio.create_task(database.add_played_track(chat_id, downloaded_track, user_id))
            asyncio.create_task(database.record_user_activity(user_id, "play", chat_id))
            
            # Delete the message or update to now playing
            await client.delete_messages(chat_id, message_id)
            
            # Send now playing message
            await send_now_playing(client, callback_query.message, downloaded_track)
            await callback_query.answer("Playing now!")
        else:
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ Error: {message_text}"
            )
            await callback_query.answer("Failed to play track")
    
    @bot.on_callback_query(filters=lambda query: query.data == "cancel_search")
    async def callback_cancel_search(client, callback_query):
        """Handle callback for canceling a search."""
        await callback_query.message.delete()
        await callback_query.answer("Search cancelled")
    
    @bot.on_message(filters.command("pause"))
    async def cmd_pause(client, message: Message):
        """Handler for /pause command."""
        # Send immediate feedback
        await client.send_chat_action(message.chat.id, "typing")
        
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else None
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Send the initial acknowledgment immediately
        reply_msg = await message.reply("⏸️ Pausing...")
        
        # Pause the track
        success, message_text = await voice_chat.pause(chat_id)
        
        # Update reply message with result
        await reply_msg.edit_text(message_text)
        
        # Record activity in background
        if user_id:
            asyncio.create_task(database.record_user_activity(user_id, "pause", chat_id))
    
    @bot.on_message(filters.command("resume"))
    async def cmd_resume(client, message: Message):
        """Handler for /resume command."""
        # Send immediate feedback
        await client.send_chat_action(message.chat.id, "typing")
        
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else None
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Send the initial acknowledgment immediately
        reply_msg = await message.reply("▶️ Resuming...")
        
        # Resume the track
        success, message_text = await voice_chat.resume(chat_id)
        
        # Update reply message with result
        await reply_msg.edit_text(message_text)
        
        # Record activity in background
        if user_id:
            asyncio.create_task(database.record_user_activity(user_id, "resume", chat_id))
    
    @bot.on_message(filters.command("skip"))
    async def cmd_skip(client, message: Message):
        """Handler for /skip command."""
        # Send immediate feedback
        await client.send_chat_action(message.chat.id, "typing")
        
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Send the initial acknowledgment immediately
        reply_msg = await message.reply("⏭️ Skipping the current track...")
        
        # Skip the track
        success, message_text = await voice_chat.skip(chat_id)
        
        if success:
            current_track = voice_chat.active_calls[chat_id]["current_track"]
            await reply_msg.edit_text(f"⏭️ Skipped to: **{current_track['name']}** by {current_track['artists']}")
        else:
            await reply_msg.edit_text(message_text)
        
        # Record activity in background
        if user_id:
            asyncio.create_task(database.record_user_activity(user_id, "skip", chat_id))
    
    @bot.on_message(filters.command("stop"))
    async def cmd_stop(client, message: Message):
        """Handler for /stop command."""
        # Send immediate feedback
        await client.send_chat_action(message.chat.id, "typing")
        
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else None
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Send the initial acknowledgment immediately
        reply_msg = await message.reply("🛑 Stopping playback and leaving voice chat...")
        
        # Leave the voice chat
        success, message_text = await voice_chat.leave_voice_chat(chat_id)
        
        # Update reply message with result
        await reply_msg.edit_text(message_text)
        
        # Record activity in background
        if user_id:
            asyncio.create_task(database.record_user_activity(user_id, "stop", chat_id))
    
    @bot.on_message(filters.command("volume"))
    async def cmd_volume(client, message: Message):
        """Handler for /volume command."""
        chat_id = message.chat.id
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Get the volume
        args = message.text.split(" ", 1)
        if len(args) < 2:
            current_volume = voice_chat.active_calls[chat_id].get("volume", 100)
            await message.reply(f"🔊 Current volume: {current_volume}%\nUse `/volume [0-200]` to change.")
            return
        
        try:
            volume = int(args[1].strip())
            if not 0 <= volume <= 200:
                await message.reply("❌ Volume must be between 0 and 200.")
                return
        except ValueError:
            await message.reply("❌ Volume must be a number between 0 and 200.")
            return
        
        # Set the volume
        success, message_text = await voice_chat.set_volume(chat_id, volume)
        await message.reply(message_text)
    
    @bot.on_message(filters.command("queue"))
    async def cmd_queue(client, message: Message):
        """Handler for /queue command."""
        chat_id = message.chat.id
        
        # Get the queue
        queue = queue_manager.get_queue(chat_id)
        
        if not queue:
            await message.reply("📋 Queue is empty.")
            return
        
        # Format the queue
        text = "📋 **Music Queue**\n\n"
        
        for i, track in enumerate(queue[:10], start=1):
            text += f"{i}. **{track['name']}** - {track['artists']}\n"
        
        if len(queue) > 10:
            text += f"\n... and {len(queue) - 10} more"
        
        # Send the queue
        await message.reply(text)
    
    @bot.on_message(filters.command("current"))
    async def cmd_current(client, message: Message):
        """Handler for /current command."""
        chat_id = message.chat.id
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Get the current track
        current_track = voice_chat.active_calls[chat_id].get("current_track")
        
        if not current_track:
            await message.reply("❌ No track is currently playing.")
            return
        
        # Send now playing message
        await send_now_playing(client, message, current_track)
    
    @bot.on_message(filters.command("ping"))
    async def cmd_ping(client, message: Message):
        """Handler for /ping command."""
        start_time = time.time()
        msg = await message.reply("Pong!")
        end_time = time.time()
        
        # Calculate ping
        ping_time = (end_time - start_time) * 1000
        
        await msg.edit_text(f"🏓 Pong! `{ping_time:.2f}ms`")
    
    @bot.on_message(filters.command("stats"))
    async def cmd_stats(client, message: Message):
        """Handler for /stats command."""
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else None
        
        # Get top tracks
        top_tracks = await database.get_top_tracks(chat_id, limit=5)
        
        # Format stats
        text = "📊 **Music Bot Stats**\n\n"
        
        # Add current voice chat status
        if chat_id in voice_chat.active_calls:
            current_track = voice_chat.active_calls[chat_id].get("current_track")
            if current_track:
                text += f"🎵 Now Playing: **{current_track['name']}** by {current_track['artists']}\n"
            
            text += f"🔊 Volume: {voice_chat.active_calls[chat_id].get('volume', 100)}%\n"
            text += f"📋 Queue Length: {queue_manager.queue_length(chat_id)}\n\n"
        
        # Add top tracks
        if top_tracks:
            text += "**Top Played Tracks:**\n"
            for i, track in enumerate(top_tracks, start=1):
                text += f"{i}. **{track['name']}** - {track['artists']} ({track['count']} plays)\n"
        else:
            text += "No tracks have been played yet."
        
        # Record user activity
        if user_id:
            await database.record_user_activity(user_id, "stats", chat_id)
        
        await message.reply(text)
        
    @bot.on_message(filters.command("profile"))
    async def cmd_profile(client, message: Message):
        """Handler for /profile command."""
        user_id = message.from_user.id if message.from_user else None
        
        if not user_id:
            await message.reply("❌ Could not identify user.")
            return
        
        # Record user activity
        await database.record_user_activity(user_id, "profile")
        
        # Get user config
        user_config = await database.get_user_config(user_id)
        
        # Get user stats
        user_stats = await database.get_user_stats(user_id)
        
        # Format profile message
        text = f"👤 **User Profile**\n\n"
        text += f"🆔 User ID: `{user_id}`\n"
        text += f"🔊 Preferred Volume: {user_config.get('preferred_volume', 100)}%\n"
        text += f"🎵 Preferred Quality: {user_config.get('preferred_quality', 'medium')}\n"
        text += f"🌐 Language: {user_config.get('language', 'en')}\n\n"
        
        # Add statistics
        text += "📊 **Statistics**\n"
        text += f"▶️ Total Plays: {user_stats.get('total_plays', 0)}\n"
        
        if user_stats.get('first_seen'):
            text += f"🕒 First Seen: {format_time(user_stats['first_seen'])}\n"
        
        if user_stats.get('last_active'):
            text += f"🕒 Last Active: {format_time(user_stats['last_active'])}\n\n"
        
        # Add favorite tracks section
        favorites = await database.get_user_favorites(user_id, limit=5)
        if favorites:
            text += "❤️ **Favorite Tracks**\n"
            for i, track in enumerate(favorites, start=1):
                track_name = track.get('name', 'Unknown')
                track_artists = track.get('artists', [])
                text += f"{i}. **{track_name}** - {track_artists}\n"
        
        # Create settings buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Change Volume", callback_data=f"settings_volume_{user_id}"),
                InlineKeyboardButton("Change Quality", callback_data=f"settings_quality_{user_id}")
            ],
            [
                InlineKeyboardButton("Change Language", callback_data=f"settings_language_{user_id}"),
                InlineKeyboardButton("Toggle Notifications", callback_data=f"settings_notifications_{user_id}")
            ]
        ])
        
        await message.reply(text, reply_markup=keyboard)
    
    @bot.on_callback_query(filters=lambda query: query.data.startswith("settings_"))
    async def callback_user_settings(client, callback_query):
        """Handle callback for user settings."""
        parts = callback_query.data.split("_")
        if len(parts) < 3:
            await callback_query.answer("Invalid settings option")
            return
        
        setting_type = parts[1]
        user_id_str = parts[2]
        
        try:
            user_id = int(user_id_str)
        except ValueError:
            await callback_query.answer("Invalid user ID")
            return
        
        # Check if the callback is for the user who pressed the button
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You can only change your own settings")
            return
        
        # Handle different settings
        if setting_type == "volume":
            # Create volume selection keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("50%", callback_data=f"set_volume_{user_id}_50"),
                    InlineKeyboardButton("75%", callback_data=f"set_volume_{user_id}_75"),
                    InlineKeyboardButton("100%", callback_data=f"set_volume_{user_id}_100")
                ],
                [
                    InlineKeyboardButton("125%", callback_data=f"set_volume_{user_id}_125"),
                    InlineKeyboardButton("150%", callback_data=f"set_volume_{user_id}_150"),
                    InlineKeyboardButton("200%", callback_data=f"set_volume_{user_id}_200")
                ],
                [
                    InlineKeyboardButton("« Back to Profile", callback_data=f"back_to_profile_{user_id}")
                ]
            ])
            
            await client.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.id,
                text="🔊 **Select Preferred Volume**\n\nThis will be used as your default volume when playing music.",
                reply_markup=keyboard
            )
        
        elif setting_type == "quality":
            # Create quality selection keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Low", callback_data=f"set_quality_{user_id}_low"),
                    InlineKeyboardButton("Medium", callback_data=f"set_quality_{user_id}_medium"),
                    InlineKeyboardButton("High", callback_data=f"set_quality_{user_id}_high")
                ],
                [
                    InlineKeyboardButton("« Back to Profile", callback_data=f"back_to_profile_{user_id}")
                ]
            ])
            
            await client.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.id,
                text="🎵 **Select Preferred Audio Quality**\n\nHigher quality uses more bandwidth.",
                reply_markup=keyboard
            )
        
        elif setting_type == "language":
            # Create language selection keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("English", callback_data=f"set_language_{user_id}_en"),
                    InlineKeyboardButton("Español", callback_data=f"set_language_{user_id}_es")
                ],
                [
                    InlineKeyboardButton("Français", callback_data=f"set_language_{user_id}_fr"),
                    InlineKeyboardButton("Deutsch", callback_data=f"set_language_{user_id}_de")
                ],
                [
                    InlineKeyboardButton("« Back to Profile", callback_data=f"back_to_profile_{user_id}")
                ]
            ])
            
            await client.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.id,
                text="🌐 **Select Language**\n\nChoose your preferred language for bot messages.",
                reply_markup=keyboard
            )
        
        elif setting_type == "notifications":
            # Toggle notifications
            user_config = await database.get_user_config(user_id)
            current_state = user_config.get("notifications_enabled", True)
            new_state = not current_state
            
            # Update config
            await database.update_user_config(user_id, {"notifications_enabled": new_state})
            
            await callback_query.answer(f"Notifications {'enabled' if new_state else 'disabled'}")
            
            # Trigger profile refresh
            await callback_query.data.replace(setting_type, "refresh")
            await callback_back_to_profile(client, callback_query)
        
        else:
            await callback_query.answer("Setting not implemented yet")
    
    @bot.on_callback_query(filters=lambda query: query.data.startswith("set_volume_"))
    async def callback_set_volume(client, callback_query):
        """Handle callback for setting volume."""
        parts = callback_query.data.split("_")
        if len(parts) < 4:
            await callback_query.answer("Invalid volume setting")
            return
        
        user_id_str = parts[2]
        volume_str = parts[3]
        
        try:
            user_id = int(user_id_str)
            volume = int(volume_str)
        except ValueError:
            await callback_query.answer("Invalid values")
            return
        
        # Check if the callback is for the user who pressed the button
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You can only change your own settings")
            return
        
        # Update user config
        await database.update_user_config(user_id, {"preferred_volume": volume})
        
        await callback_query.answer(f"Volume set to {volume}%")
        
        # Return to profile
        await callback_back_to_profile(client, callback_query)
    
    @bot.on_callback_query(filters=lambda query: query.data.startswith("set_quality_"))
    async def callback_set_quality(client, callback_query):
        """Handle callback for setting quality."""
        parts = callback_query.data.split("_")
        if len(parts) < 4:
            await callback_query.answer("Invalid quality setting")
            return
        
        user_id_str = parts[2]
        quality = parts[3]
        
        try:
            user_id = int(user_id_str)
        except ValueError:
            await callback_query.answer("Invalid user ID")
            return
        
        # Check if the callback is for the user who pressed the button
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You can only change your own settings")
            return
        
        # Update user config
        await database.update_user_config(user_id, {"preferred_quality": quality})
        
        await callback_query.answer(f"Quality set to {quality}")
        
        # Return to profile
        await callback_back_to_profile(client, callback_query)
    
    @bot.on_callback_query(filters=lambda query: query.data.startswith("set_language_"))
    async def callback_set_language(client, callback_query):
        """Handle callback for setting language."""
        parts = callback_query.data.split("_")
        if len(parts) < 4:
            await callback_query.answer("Invalid language setting")
            return
        
        user_id_str = parts[2]
        language = parts[3]
        
        try:
            user_id = int(user_id_str)
        except ValueError:
            await callback_query.answer("Invalid user ID")
            return
        
        # Check if the callback is for the user who pressed the button
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You can only change your own settings")
            return
        
        # Update user config
        await database.update_user_config(user_id, {"language": language})
        
        await callback_query.answer(f"Language set to {language}")
        
        # Return to profile
        await callback_back_to_profile(client, callback_query)
    
    @bot.on_callback_query(filters=lambda query: query.data.startswith("back_to_profile_"))
    async def callback_back_to_profile(client, callback_query):
        """Handle callback for going back to profile."""
        parts = callback_query.data.split("_")
        if len(parts) < 4:
            await callback_query.answer("Invalid profile callback")
            return
        
        user_id_str = parts[3]
        
        try:
            user_id = int(user_id_str)
        except ValueError:
            await callback_query.answer("Invalid user ID")
            return
        
        # Check if the callback is for the user who pressed the button
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You can only view your own profile")
            return
        
        # Get updated user config
        user_config = await database.get_user_config(user_id)
        
        # Get user stats
        user_stats = await database.get_user_stats(user_id)
        
        # Format profile message
        text = f"👤 **User Profile**\n\n"
        text += f"🆔 User ID: `{user_id}`\n"
        text += f"🔊 Preferred Volume: {user_config.get('preferred_volume', 100)}%\n"
        text += f"🎵 Preferred Quality: {user_config.get('preferred_quality', 'medium')}\n"
        text += f"🌐 Language: {user_config.get('language', 'en')}\n\n"
        
        # Add statistics
        text += "📊 **Statistics**\n"
        text += f"▶️ Total Plays: {user_stats.get('total_plays', 0)}\n"
        
        if user_stats.get('first_seen'):
            text += f"🕒 First Seen: {format_time(user_stats['first_seen'])}\n"
        
        if user_stats.get('last_active'):
            text += f"🕒 Last Active: {format_time(user_stats['last_active'])}\n\n"
        
        # Add favorite tracks section
        favorites = await database.get_user_favorites(user_id, limit=5)
        if favorites:
            text += "❤️ **Favorite Tracks**\n"
            for i, track in enumerate(favorites, start=1):
                track_name = track.get('name', 'Unknown')
                track_artists = track.get('artists', [])
                text += f"{i}. **{track_name}** - {track_artists}\n"
        
        # Create settings buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Change Volume", callback_data=f"settings_volume_{user_id}"),
                InlineKeyboardButton("Change Quality", callback_data=f"settings_quality_{user_id}")
            ],
            [
                InlineKeyboardButton("Change Language", callback_data=f"settings_language_{user_id}"),
                InlineKeyboardButton("Toggle Notifications", callback_data=f"settings_notifications_{user_id}")
            ]
        ])
        
        await client.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.id,
            text=text,
            reply_markup=keyboard
        )
        
        await callback_query.answer("Profile updated")
    
    @bot.on_message(filters.command("favorite"))
    async def cmd_favorite(client, message: Message):
        """Handler for /favorite command to add current song to favorites."""
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else None
        
        if not user_id:
            await message.reply("❌ Could not identify user.")
            return
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Get the current track
        current_track = voice_chat.active_calls[chat_id].get("current_track")
        
        if not current_track:
            await message.reply("❌ No track is currently playing.")
            return
        
        # Add to favorites
        track_id = current_track.get("id", "unknown")
        await database.add_user_favorite(user_id, track_id, current_track)
        
        # Record activity
        await database.record_user_activity(user_id, "favorite", chat_id)
        
        await message.reply(f"❤️ Added **{current_track['name']}** to your favorites!")
    
    @bot.on_message(filters.command("favorites"))
    async def cmd_favorites(client, message: Message):
        """Handler for /favorites command to show favorite songs."""
        user_id = message.from_user.id if message.from_user else None
        
        if not user_id:
            await message.reply("❌ Could not identify user.")
            return
        
        # Get favorites
        favorites = await database.get_user_favorites(user_id)
        
        if not favorites:
            await message.reply("❌ You don't have any favorite tracks yet.")
            return
        
        # Format favorites
        text = "❤️ **Your Favorite Tracks**\n\n"
        
        for i, track in enumerate(favorites[:10], start=1):
            track_name = track.get('name', 'Unknown')
            track_artists = track.get('artists', [])
            text += f"{i}. **{track_name}** - {track_artists}\n"
        
        if len(favorites) > 10:
            text += f"\n... and {len(favorites) - 10} more"
        
        # Create keyboard with play buttons
        buttons = []
        row = []
        
        for i, track in enumerate(favorites[:5]):
            track_id = track.get('track_id', 'unknown')
            row.append(InlineKeyboardButton(f"Play #{i+1}", callback_data=f"play_{track_id}"))
            
            if len(row) == 2 or i == len(favorites[:5]) - 1:
                buttons.append(row)
                row = []
        
        keyboard = InlineKeyboardMarkup(buttons)
        
        # Record activity
        await database.record_user_activity(user_id, "list_favorites")
        
        await message.reply(text, reply_markup=keyboard)
    
    @bot.on_message(filters.command("lyrics"))
    async def cmd_lyrics(client, message: Message):
        """Handler for /lyrics command to get lyrics for the current or specified song."""
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else None
        
        # Record user activity
        if user_id:
            await database.record_user_activity(user_id, "lyrics", chat_id)
        
        # Check if we have a song name in the message
        query = message.text.split(" ", 1)
        
        # If there's a specific song requested
        if len(query) > 1:
            song_name = query[1].strip()
            artist_name = None
            
            # Check if format is "Artist - Song"
            if " - " in song_name:
                artist_name, song_name = song_name.split(" - ", 1)
            
            # Send a temporary message
            status_msg = await message.reply("🔍 Searching for lyrics...")
            
            # Get lyrics
            lyrics_data = await lyrics_client.get_lyrics_by_search(song_name, artist_name)
            
            # Format and send lyrics
            formatted_lyrics = lyrics_client.format_lyrics_for_telegram(lyrics_data)
            await status_msg.edit_text(formatted_lyrics, disable_web_page_preview=False)
            return
        
        # If no song specified, use current playing song
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat. Please specify a song name:\n/lyrics song name\nor\n/lyrics artist - song name")
            return
        
        current_track = voice_chat.active_calls[chat_id].get("current_track")
        if not current_track:
            await message.reply("❌ No track is currently playing. Please specify a song name:\n/lyrics song name\nor\n/lyrics artist - song name")
            return
        
        # Send a temporary message
        status_msg = await message.reply("🔍 Searching for lyrics...")
        
        # Get lyrics for current song
        song_name = current_track["name"]
        artist_name = current_track["artists"]
        
        # Get lyrics
        lyrics_data = await lyrics_client.get_lyrics_by_search(song_name, artist_name)
        
        # Format and send lyrics
        formatted_lyrics = lyrics_client.format_lyrics_for_telegram(lyrics_data)
        await status_msg.edit_text(formatted_lyrics, disable_web_page_preview=False)
    
    @bot.on_message(filters.command("settings"))
    async def cmd_settings(client, message: Message):
        """Handler for /settings command to show and edit user settings."""
        user_id = message.from_user.id if message.from_user else None
        
        if not user_id:
            await message.reply("❌ Could not identify user.")
            return
        
        # Get user config
        user_config = await database.get_user_config(user_id)
        
        # Format settings message
        text = "⚙️ **User Settings**\n\n"
        text += f"🔊 Preferred Volume: {user_config.get('preferred_volume', 100)}%\n"
        text += f"🎵 Preferred Quality: {user_config.get('preferred_quality', 'medium')}\n"
        text += f"🌐 Language: {user_config.get('language', 'en')}\n"
        text += f"🔔 Notifications: {'Enabled' if user_config.get('notifications_enabled', True) else 'Disabled'}\n"
        
        # Create settings buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Change Volume", callback_data=f"settings_volume_{user_id}"),
                InlineKeyboardButton("Change Quality", callback_data=f"settings_quality_{user_id}")
            ],
            [
                InlineKeyboardButton("Change Language", callback_data=f"settings_language_{user_id}"),
                InlineKeyboardButton("Toggle Notifications", callback_data=f"settings_notifications_{user_id}")
            ]
        ])
        
        # Record activity
        await database.record_user_activity(user_id, "settings")
        
        await message.reply(text, reply_markup=keyboard)
    
    # Owner commands
    @bot.on_message(filters.command(["broadcast", "stats", "reload", "clearqueue"], prefixes=config.COMMAND_PREFIX if config else "/"))
    async def cmd_owner(client, message: Message):
        """Handler for owner commands like broadcast, stats, reload, etc."""
        # Extract command and arguments
        full_command = message.text.split(" ", 1)
        command = full_command[0][1:]  # Remove prefix
        args = full_command[1] if len(full_command) > 1 else ""
        
        # Pass to handler for owner commands
        await handle_owner_command(client, message, command, args, config, database)
        
    @bot.on_message(filters.command(["listeners"]))
    async def cmd_listeners(client, message: Message):
        """Handler for /listeners command to show active participants in the voice chat."""
        # Send immediate typing action for better user experience
        await client.send_chat_action(message.chat.id, "typing")
        
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else None
        
        # Record user activity in background to avoid delay
        if user_id:
            asyncio.create_task(database.record_user_activity(user_id, "listeners"))
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat in this chat.")
            return
        
        # Check if voice overlay is available
        if not hasattr(client, "voice_overlay"):
            await message.reply("⚠️ Voice participant tracking is not available.")
            return
        
        # Get active participants
        active_participants = await client.voice_overlay.get_active_participants(chat_id)
        
        if not active_participants:
            await message.reply("📢 No active listeners detected in the voice chat.")
            return
        
        # Get participant info
        participants_info = []
        for participant_id in active_participants:
            try:
                user = await client.get_users(participant_id)
                if user:
                    username = user.username or f"{user.first_name} {user.last_name or ''}"
                    participants_info.append(f"• {username.strip()} (`{participant_id}`)")
            except Exception as e:
                logger.error(f"Error getting user info: {e}")
        
        # Create a UI image with the current track and participants if possible
        current_track = voice_chat.active_calls[chat_id].get("current_track")
        if current_track and hasattr(client, "voice_overlay"):
            # Get or create the image
            image_path = await client.voice_overlay.create_participants_image(chat_id, current_track)
            
            if image_path:
                # Create a caption with listeners
                caption = f"🎧 **Current Listeners ({len(active_participants)})**\n\n"
                caption += f"**Now Playing:** {current_track.get('name', 'Unknown')}\n"
                caption += f"**By:** {current_track.get('artists', 'Unknown')}\n\n"
                caption += "\n".join(participants_info[:10])  # Limit to 10 participants in text
                
                if len(participants_info) > 10:
                    caption += f"\n\n...and {len(participants_info) - 10} more"
                
                # Send the image with participant information
                await message.reply_photo(
                    photo=image_path,
                    caption=caption
                )
                return
        
        # Fallback to text only if no image was created
        text = f"🎧 **Voice Chat Listeners ({len(active_participants)})**\n\n"
        if participants_info:
            text += "\n".join(participants_info[:20])  # Limit to 20 participants
            
            if len(participants_info) > 20:
                text += f"\n\n...and {len(participants_info) - 20} more"
        else:
            text += "No listener information available."
            
        await message.reply(text)
            
    @bot.on_message(filters.command(["quiz", "musicquiz"]))
    # Rate limiting will be applied inside the handler
    async def cmd_quiz(client, message: Message):
        """Start a music quiz in the current chat."""
        # Apply rate limiting (once every 5 seconds per user)
        user_id = message.from_user.id
        if not await rate_limiter(user_id, "quiz", limit=1, time_window=5):
            await message.reply("⏱ Please wait before starting another quiz")
            return
            
        # Send immediate typing action
        await client.send_chat_action(message.chat.id, "typing")
        
        # Get quiz manager instance
        quiz_manager = getattr(client, "quiz_manager", None)
        if not quiz_manager:
            logger.error("Quiz manager not initialized")
            await message.reply("❌ Quiz functionality is not available at the moment. Please try again later.")
            return
            
        # Check if there's already an active quiz
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        active_quiz = quiz_manager.get_quiz(chat_id)
        if active_quiz and active_quiz.is_active():
            await message.reply("❌ A quiz is already in progress in this chat!")
            return
            
        # Parse arguments
        try:
            args = message.text.split()[1:]
            num_questions = 5  # Default
            genre = None
            difficulty = "medium"  # Default
            
            if args:
                for arg in args:
                    if arg.isdigit():
                        num_questions = min(max(int(arg), 1), 10)  # Limit to 1-10 questions
                    elif arg.lower() in ["easy", "medium", "hard"]:
                        difficulty = arg.lower()
                    else:
                        genre = arg.lower()
        except Exception as e:
            logger.error(f"Error parsing quiz arguments: {e}")
            # Use defaults if parsing fails
            num_questions = 5
            genre = None
            difficulty = "medium"
            
        # Send acknowledgment
        await message.reply(f"🎮 Creating a music quiz with {num_questions} questions" + 
                          (f" in the {genre} genre" if genre else "") +
                          f" ({difficulty} difficulty)...")
                          
        # Get user info for username mapping
        usernames = {}
        try:
            if message.chat.type != "private":
                async for member in client.get_chat_members(chat_id):
                    if member.user and not member.user.is_bot:
                        usernames[member.user.id] = member.user.username or member.user.first_name
        except Exception as e:
            logger.error(f"Error getting chat members: {e}")
            
        # Create the quiz
        new_quiz = await quiz_manager.create_quiz(
            chat_id=chat_id,
            creator_id=user_id,
            num_questions=num_questions,
            genre=genre,
            difficulty=difficulty
        )
        
        if new_quiz:
            # Start the quiz by sending the first question
            await new_quiz.send_question(client, chat_id, usernames)
        else:
            await message.reply("❌ Failed to create quiz. Please try again later.")
