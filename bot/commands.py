import asyncio
import logging
import os
import time
from pyrogram import filters
from pyrogram.types import Message

from .helpers import (
    format_duration,
    rate_limiter,
    is_admin,
    extract_user_and_text
)
from .ui import send_now_playing, send_search_results

logger = logging.getLogger(__name__)

def register_commands(bot, voice_chat, queue_manager, spotify, database):
    """Register command handlers for the bot."""
    # Store instances for callback query handlers
    bot.voice_chat = voice_chat
    bot.queue_manager = queue_manager
    bot.spotify = spotify
    bot.database = database
    
    @bot.on_message(filters.command(["start", "help"]))
    async def cmd_start(client, message: Message):
        """Handler for /start and /help commands."""
        help_text = """
🎵 **Music Bot Help** 🎵

**Basic Commands:**
/play [song name or Spotify URL] - Play a song or add to queue
/pause - Pause the current song
/resume - Resume the current song
/skip - Skip to the next song
/stop - Stop playback and leave voice chat
/queue - Show the current queue
/current - Show the current song
/search [query] - Search for a song

**Advanced Commands:**
/volume [0-200] - Set the volume (default: 100)
/ping - Check bot latency
/stats - Show bot statistics

Start by using /play command to play music in a voice chat!
        """
        await message.reply(help_text)
    
    @bot.on_message(filters.command("play"))
    async def cmd_play(client, message: Message):
        """Handler for /play command."""
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Check for rate limiting
        if not await rate_limiter(user_id, "play", limit=3, time_window=10):
            await message.reply("You're using this command too frequently! Please wait a bit.")
            return
        
        # Get the query
        query = message.text.split(" ", 1)
        if len(query) < 2:
            await message.reply("Please provide a song name or Spotify link.\nUsage: `/play song name or link`")
            return
        
        query = query[1].strip()
        
        # Send a temporary message
        status_msg = await message.reply("🔍 Searching...")
        
        # Check if it's a Spotify link
        if "spotify.com/track/" in query:
            track_id = query.split("spotify.com/track/")[1].split("?")[0]
            track = await spotify.get_track(track_id)
            if not track:
                await status_msg.edit_text("❌ Failed to get track information from Spotify.")
                return
            
            tracks = [track]
        else:
            # Search for tracks
            tracks = await spotify.search(query)
        
        if not tracks:
            await status_msg.edit_text("❌ No tracks found matching your query.")
            return
        
        # Get the first track
        track = tracks[0]
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            # Join voice chat first
            await status_msg.edit_text("🔄 Joining voice chat...")
            success = await voice_chat.join_voice_chat(chat_id, user_id)
            if not success:
                await status_msg.edit_text("❌ Failed to join voice chat. Make sure I have the right permissions and there's an active voice chat.")
                return
        
        # Check if something is already playing
        if voice_chat.active_calls[chat_id].get("current_track"):
            # Add to queue
            await status_msg.edit_text(f"🔄 Adding **{track['name']}** to the queue...")
            success, message_text = await queue_manager.add_to_queue(chat_id, track, user_id)
            await status_msg.edit_text(message_text)
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
            # Add to database
            await database.add_played_track(chat_id, downloaded_track, user_id)
            
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
        track_id = callback_query.data.split("_")[1]
        chat_id = callback_query.message.chat.id
        user_id = callback_query.from_user.id
        message_id = callback_query.message.id
        
        # Get track information
        track = await spotify.get_track(track_id)
        if not track:
            await callback_query.answer("❌ Failed to get track information.")
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ Failed to get track information from Spotify."
            )
            return
        
        # Edit the message
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"🔄 Selected: **{track['name']}** by {track['artists']}"
        )
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            # Join voice chat first
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
        
        # Check if something is already playing
        if voice_chat.active_calls[chat_id].get("current_track"):
            # Add to queue
            success, message_text = await queue_manager.add_to_queue(chat_id, track, user_id)
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text
            )
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
            # Add to database
            await database.add_played_track(chat_id, downloaded_track, user_id)
            
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
        chat_id = message.chat.id
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Pause the track
        success, message_text = await voice_chat.pause(chat_id)
        await message.reply(message_text)
    
    @bot.on_message(filters.command("resume"))
    async def cmd_resume(client, message: Message):
        """Handler for /resume command."""
        chat_id = message.chat.id
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Resume the track
        success, message_text = await voice_chat.resume(chat_id)
        await message.reply(message_text)
    
    @bot.on_message(filters.command("skip"))
    async def cmd_skip(client, message: Message):
        """Handler for /skip command."""
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Skip the track
        success, message_text = await voice_chat.skip(chat_id)
        if success:
            current_track = voice_chat.active_calls[chat_id]["current_track"]
            await message.reply(f"⏭️ Skipped to: **{current_track['name']}** by {current_track['artists']}")
        else:
            await message.reply(message_text)
    
    @bot.on_message(filters.command("stop"))
    async def cmd_stop(client, message: Message):
        """Handler for /stop command."""
        chat_id = message.chat.id
        
        # Check if we're in a voice chat
        if chat_id not in voice_chat.active_calls:
            await message.reply("❌ I'm not in a voice chat.")
            return
        
        # Leave the voice chat
        success, message_text = await voice_chat.leave_voice_chat(chat_id)
        await message.reply(message_text)
    
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
        
        await message.reply(text)
