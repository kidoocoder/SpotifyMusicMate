import asyncio
import logging
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get API credentials from environment
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize the bot
bot = Client(
    "test_music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Command handlers
@bot.on_message(filters.command("start"))
async def cmd_start(client, message: Message):
    """Handler for /start command."""
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Help", callback_data="help"),
                InlineKeyboardButton("Commands", callback_data="commands")
            ]
        ]
    )
    
    await message.reply(
        "👋 **Hello! I'm your Music Bot.**\n\n"
        "I can play music in Telegram voice chats.\n"
        "Use /help to see available commands.",
        reply_markup=keyboard
    )

@bot.on_message(filters.command("help"))
async def cmd_help(client, message: Message):
    """Handler for /help command."""
    await message.reply(
        "📖 **Available Commands:**\n\n"
        "/play [song name or URL] - Play a song\n"
        "/search [song name] - Search for a song\n"
        "/pause - Pause playback\n"
        "/resume - Resume playback\n"
        "/skip - Skip to next song\n"
        "/queue - Show current queue\n"
        "/current - Show current playing song\n"
        "/volume [0-200] - Set volume\n"
        "/ping - Check bot's response time\n"
        "/stats - Show bot statistics"
    )

@bot.on_message(filters.command("play"))
async def cmd_play(client, message: Message):
    """Handler for /play command."""
    # Extract query from message
    if len(message.command) < 2:
        await message.reply("Please provide a song name or URL. Example: `/play Despacito`")
        return
    
    query = " ".join(message.command[1:])
    
    # Simulate searching and queueing
    await message.reply(f"🔍 **Searching for:** `{query}`\n\n"
                        f"⏳ This is a test version without actual playback capability.\n"
                        f"In the full version, the song would be added to the queue.")

@bot.on_message(filters.command("search"))
async def cmd_search(client, message: Message):
    """Handler for /search command."""
    # Extract query from message
    if len(message.command) < 2:
        await message.reply("Please provide a song name to search. Example: `/search Despacito`")
        return
    
    query = " ".join(message.command[1:])
    
    # Create fake search results
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"1. {query} - Artist 1", callback_data="search_result_1")],
            [InlineKeyboardButton(f"2. {query} Remix - Artist 2", callback_data="search_result_2")],
            [InlineKeyboardButton(f"3. {query} Cover - Artist 3", callback_data="search_result_3")],
            [InlineKeyboardButton("Cancel", callback_data="cancel_search")]
        ]
    )
    
    await message.reply(f"🔍 **Search Results for** `{query}`:", reply_markup=keyboard)

@bot.on_message(filters.command("ping"))
async def cmd_ping(client, message: Message):
    """Handler for /ping command."""
    start_time = asyncio.get_event_loop().time()
    ping_message = await message.reply("Pinging...")
    end_time = asyncio.get_event_loop().time()
    
    ping_time = round((end_time - start_time) * 1000, 2)
    await ping_message.edit(f"🏓 **Pong!** `{ping_time}ms`")

@bot.on_callback_query()
async def handle_callback(client, callback_query):
    """Handle callback queries."""
    data = callback_query.data
    
    if data == "help":
        await callback_query.message.edit_text(
            "📖 **Available Commands:**\n\n"
            "/play [song name or URL] - Play a song\n"
            "/search [song name] - Search for a song\n"
            "/pause - Pause playback\n"
            "/resume - Resume playback\n"
            "/skip - Skip to next song\n"
            "/queue - Show current queue\n"
            "/current - Show current playing song\n"
            "/volume [0-200] - Set volume\n"
            "/ping - Check bot's response time\n"
            "/stats - Show bot statistics"
        )
    elif data == "commands":
        await callback_query.message.edit_text(
            "🎮 **Basic Commands:**\n"
            "/play - Play a song\n"
            "/pause - Pause playback\n"
            "/resume - Resume playback\n"
            "/skip - Skip to next song\n"
            "/stop - Stop playback\n\n"
            
            "📋 **Queue Commands:**\n"
            "/queue - Show the song queue\n"
            "/current - Show current song\n\n"
            
            "⚙️ **Other Commands:**\n"
            "/volume - Adjust volume\n"
            "/ping - Check response time\n"
            "/stats - Show bot stats"
        )
    elif data.startswith("search_result_"):
        song_index = data.split("_")[-1]
        await callback_query.message.edit_text(
            f"✅ Selected song #{song_index}\n\n"
            f"⏳ This is a test version without actual playback capability.\n"
            f"In the full version, the song would be added to the queue."
        )
    elif data == "cancel_search":
        await callback_query.message.edit_text("❌ Search cancelled.")
    
    # Answer the callback query to stop the loading indicator
    await callback_query.answer()

# Main function
async def main():
    """Start the bot."""
    try:
        logger.info("Starting bot...")
        await bot.start()
        
        # Keep the bot running
        logger.info("Bot is running. Press Ctrl+C to stop.")
        
        # Create our own idle function
        while True:
            await asyncio.sleep(60)
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error occurred: {e}")
    finally:
        if bot and bot.is_connected:
            await bot.stop()
            logger.info("Bot stopped.")

if __name__ == "__main__":
    # Run the event loop
    asyncio.run(main())