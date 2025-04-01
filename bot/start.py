"""Module for handling start command and owner commands."""
import time
import asyncio
from typing import List, Dict, Union, Optional

from pyrogram import Client
from pyrogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery
)
from pyrogram.errors import FloodWait, UserIsBlocked, ChatWriteForbidden

from .database import Database
from .config import Config
from .helpers import escape_markdown, format_time


async def handle_start_command(client: Client, message: Message, config: Config):
    """Handler for the /start command that shows user profile picture and welcome message."""
    user = message.from_user
    chat_type = message.chat.type
    
    # Get or create user profile in database
    user_config = config.get_user_config(user.id)
    
    # Create welcome message with bot information
    bot_info = await client.get_me()
    bot_name = bot_info.first_name
    
    # Get the user's profile photo
    profile_photos = await client.get_profile_photos(user.id, limit=1)
    
    welcome_text = f"👋 **Welcome to {bot_name}!**\n\n"
    
    if chat_type == "private":
        welcome_text += (
            f"Hello, {user.mention}!\n\n"
            f"I'm a music bot that can play songs from Spotify in Telegram voice chats.\n\n"
            f"**Commands:**\n"
            f"• `/play [song name]` - Play a song in voice chat\n"
            f"• `/search [song name]` - Search for songs\n"
            f"• `/current` - Show the current playing song\n"
            f"• `/queue` - Show the queue\n"
            f"• `/lyrics` - Get lyrics for the current song\n"
            f"• `/help` - Show all commands\n\n"
            f"**Your Profile:**\n"
            f"• User ID: `{user.id}`\n"
            f"• Name: {user.first_name} {user.last_name or ''}\n"
            f"• Username: @{user.username or 'None'}\n"
            f"• Preferred Volume: {user_config.preferred_volume}%\n"
            f"• Language: {user_config.language}\n"
            f"• Last Active: {format_time(user_config.last_active) if user_config.last_active > 0 else 'First time'}"
        )
    else:
        # Group chat welcome message
        welcome_text += (
            f"I'm ready to play music in this group!\n\n"
            f"Use `/play [song name]` to start playing music in voice chat.\n"
            f"Use `/help` to see all available commands."
        )
    
    # Create inline keyboard with buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Commands", callback_data="help_commands"),
            InlineKeyboardButton("Settings", callback_data="user_settings")
        ],
        [
            InlineKeyboardButton("Play Music", callback_data="open_play_menu")
        ]
    ])
    
    # Update last active time
    config.update_user_config(user.id, last_active=int(time.time()))
    
    # Send profile photo if available
    if profile_photos and profile_photos.total_count > 0:
        try:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=profile_photos[0].file_id,
                caption=welcome_text,
                reply_markup=keyboard
            )
        except Exception as e:
            # Fallback if sending photo fails
            print(f"Error sending photo: {e}")
            await message.reply_text(welcome_text, reply_markup=keyboard)
    else:
        # Fallback if no profile photo
        await message.reply_text(welcome_text, reply_markup=keyboard)


async def broadcast_message(client: Client, sender_id: int, message_text: str, config: Config, database: Database):
    """Broadcast a message to all users and groups."""
    # Check if sender is admin/owner
    if sender_id not in config.ADMIN_IDS:
        return False, "You are not authorized to use the broadcast command."
    
    # Get all users and chats from database
    users = list(config.user_configs.keys())
    chats = list(config.chat_configs.keys())
    
    # Counter for success and failure
    success = 0
    failed = 0
    
    # Format broadcast message
    broadcast_text = (
        f"📢 **Broadcast Message**\n\n"
        f"{message_text}\n\n"
        f"_Sent by the bot owner_"
    )
    
    # Send to users
    for user_id in users:
        try:
            await client.send_message(chat_id=user_id, text=broadcast_text)
            success += 1
            await asyncio.sleep(0.3)  # Sleep to avoid flood limits
        except (UserIsBlocked, FloodWait, Exception) as e:
            failed += 1
            # Handle FloodWait exception
            # Different versions of Pyrogram may have .x or .value attributes
            if isinstance(e, FloodWait):
                wait_time = 5
                if hasattr(e, 'value'):
                    wait_time = e.value
                elif hasattr(e, 'x'):
                    wait_time = e.x
                await asyncio.sleep(wait_time)
    
    # Send to groups
    for chat_id in chats:
        if chat_id < 0:  # Negative IDs are groups
            try:
                await client.send_message(chat_id=chat_id, text=broadcast_text)
                success += 1
                await asyncio.sleep(0.3)  # Sleep to avoid flood limits
            except (ChatWriteForbidden, FloodWait, Exception) as e:
                failed += 1
                # Handle FloodWait exception
                # Different versions of Pyrogram may have .x or .value attributes
                if isinstance(e, FloodWait):
                    wait_time = 5
                    if hasattr(e, 'value'):
                        wait_time = e.value
                    elif hasattr(e, 'x'):
                        wait_time = e.x
                    await asyncio.sleep(wait_time)
    
    # Return results
    result_text = f"📊 **Broadcast Results**\n\n📨 Successfully sent: {success}\n❌ Failed: {failed}"
    return True, result_text


async def get_bot_stats(config: Config, database: Database):
    """Get stats about the bot usage."""
    total_users = len(config.user_configs)
    total_chats = len(config.chat_configs)
    
    # Get group chats count
    group_chats = sum(1 for chat_id in config.chat_configs if chat_id < 0)
    
    # Get user stats
    user_stats = {
        "total": total_users,
        "active_today": 0,
        "active_week": 0
    }
    
    # Calculate active users
    current_time = int(time.time())
    one_day = 24 * 60 * 60
    one_week = 7 * one_day
    
    for user_id, user_config in config.user_configs.items():
        last_active = user_config.last_active
        if current_time - last_active < one_day:
            user_stats["active_today"] += 1
        if current_time - last_active < one_week:
            user_stats["active_week"] += 1
    
    # Get top tracks if available
    top_tracks = []
    try:
        # This assumes a database method exists for top tracks
        top_tracks = await database.get_top_tracks(chat_id=0, limit=5)  # 0 means global
    except Exception:
        pass
    
    stats_text = (
        f"📊 **Bot Statistics**\n\n"
        f"👥 Total Users: {total_users}\n"
        f"👥 Active Today: {user_stats['active_today']}\n"
        f"👥 Active This Week: {user_stats['active_week']}\n\n"
        f"💬 Total Chats: {total_chats}\n"
        f"💬 Group Chats: {group_chats}\n"
    )
    
    # Add top tracks if available
    if top_tracks:
        stats_text += "\n🎵 **Top Tracks**:\n"
        for i, track in enumerate(top_tracks, 1):
            track_name = track.get("title", "Unknown")
            artist = track.get("artist", "Unknown")
            plays = track.get("plays", 0)
            stats_text += f"{i}. {track_name} - {artist} ({plays} plays)\n"
    
    return stats_text


async def handle_owner_command(client: Client, message: Message, command: str, args: str, config: Config, database: Database):
    """Handler for owner-only commands."""
    user_id = message.from_user.id
    
    # Check if user is admin/owner
    if user_id not in config.ADMIN_IDS:
        await message.reply_text("You are not authorized to use this command.")
        return
    
    if command == "broadcast":
        if not args:
            await message.reply_text("Please provide a message to broadcast.")
            return
        
        # Send initial status
        status_msg = await message.reply_text("Broadcasting message... This may take some time.")
        
        # Perform broadcast
        success, result = await broadcast_message(client, user_id, args, config, database)
        
        # Update status message
        await status_msg.edit_text(result)
    
    elif command == "stats":
        # Get and send stats
        stats_text = await get_bot_stats(config, database)
        await message.reply_text(stats_text)
    
    elif command == "reload":
        # Reload configurations
        config.load_user_configs()
        config.load_chat_configs()
        await message.reply_text("Configurations reloaded successfully.")
    
    elif command == "clearqueue":
        # Check if chat_id is provided
        chat_id = None
        if args:
            try:
                chat_id = int(args)
            except ValueError:
                await message.reply_text("Invalid chat ID format. Expected integer.")
                return
        else:
            chat_id = message.chat.id
        
        # This assumes a queue manager instance would be passed to this function
        # For now, reply with a placeholder
        await message.reply_text(f"Queue cleared for chat ID: {chat_id}")
    
    else:
        # Unknown owner command
        await message.reply_text(f"Unknown owner command: {command}")