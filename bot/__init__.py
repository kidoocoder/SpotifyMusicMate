from pyrogram import Client
import asyncio
import logging
import os
from pytgcalls import PyTgCalls
from pytgcalls.types import Update
from pytgcalls.types.stream import MediaStream
from pytgcalls.types.stream.audio_quality import AudioQuality
from pytgcalls.exceptions import NoActiveGroupCall, NotInCallError

from .config import Config
from .commands import register_commands
from .spotify import SpotifyClient
from .voice_chat import VoiceChat
from .voice_overlay import VoiceOverlay
from .queue_manager import QueueManager
from .database import Database
from .lyrics import LyricsClient
from .music_quiz import MusicQuiz
from .image_ui import ImageUI
from .ui import create_ui_components

logger = logging.getLogger(__name__)

async def create_bot():
    """Create and initialize the Telegram bot and assistant."""
    config = Config()
    
    # Initialize the bot and user client
    bot = Client(
        "music_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN
    )
    
    # Initialize assistant for voice chats
    assistant = Client(
        "music_assistant",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        session_string=config.SESSION_STRING
    )
    
    # Initialize PyTgCalls with the assistant
    call_client = PyTgCalls(assistant)
    
    # Initialize database with config
    database = Database(config)
    
    # Initialize Spotify client
    spotify = SpotifyClient(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET
    )
    
    # Initialize lyrics client
    lyrics_client = LyricsClient(api_token=config.GENIUS_API_TOKEN if hasattr(config, "GENIUS_API_TOKEN") else None)
    
    # Initialize queue manager
    queue_manager = QueueManager()
    
    # Initialize image UI generator
    image_ui = ImageUI(config)
    
    # Initialize music quiz
    quiz_manager = MusicQuiz(spotify, database)
    
    # Initialize voice chat manager
    voice_chat = VoiceChat(call_client, queue_manager, spotify, client=bot)
    
    # Initialize voice overlay
    voice_overlay = VoiceOverlay(bot)
    
    # Set voice overlay on voice chat
    voice_chat.voice_overlay = voice_overlay
    
    # Register command handlers
    register_commands(bot, voice_chat, queue_manager, spotify, database, lyrics_client, config)
    
    # Create UI components
    create_ui_components(bot)
    
    # Start the bot and assistant
    await bot.start()
    logger.info("Bot started")
    
    await assistant.start()
    logger.info("Assistant started")
    
    await call_client.start()
    logger.info("Call client started")
    
    # Initialize spotify client
    await spotify.initialize()
    logger.info("Spotify client initialized")
    
    # Initialize lyrics client
    await lyrics_client.initialize()
    logger.info("Lyrics client initialized")
    
    # Start voice overlay
    await voice_overlay.start()
    logger.info("Voice overlay started")
    
    # Attach all instances to the bot for access in callbacks
    bot.voice_chat = voice_chat
    bot.queue_manager = queue_manager
    bot.spotify = spotify
    bot.database = database
    bot.lyrics_client = lyrics_client
    bot.image_ui = image_ui
    bot.quiz_manager = quiz_manager
    bot.voice_overlay = voice_overlay
    
    logger.info("All components attached to bot instance")
    
    # Add stop method for graceful shutdown
    async def stop():
        await voice_overlay.stop()  # Stop voice overlay first
        await bot.stop()
        await assistant.stop()
        await call_client.stop()
        await lyrics_client.close()
    
    bot.stop = stop
    
    # Add idle method to keep bot running
    async def idle():
        try:
            while True:
                await asyncio.sleep(3600)  # Sleep for an hour and then check again
        except asyncio.CancelledError:
            pass
    
    bot.idle = idle
    
    return bot
