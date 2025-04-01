#!/usr/bin/env python3
"""
Music Voice Bot for Telegram
----------------------------
A sophisticated Telegram music bot offering advanced interactive music playback 
in group and channel voice chats, with rich user engagement features and 
cross-platform deployment support.

Features:
- Spotify integration for high-quality music
- Interactive voice chat controls
- Real-time participant tracking and reactions
- Personalized user settings and preferences
- Music quiz games and lyrics display
- Cross-platform deployment support
"""

import asyncio
import logging
import os
import platform
import signal
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
import colorama
from colorama import Fore, Style

# Initialize colorama for cross-platform colored terminal output
colorama.init(autoreset=True)

# ASCII Art Banner
BANNER = f"""
{Fore.CYAN}╔═══════════════════════════════════════════════════════════╗
{Fore.CYAN}║{Fore.MAGENTA} ███╗   ███╗██╗   ██╗███████╗██╗ ██████╗{Fore.CYAN}    ██████╗  ██████╗ ████████╗{Fore.CYAN} ║
{Fore.CYAN}║{Fore.MAGENTA} ████╗ ████║██║   ██║██╔════╝██║██╔════╝{Fore.CYAN}    ██╔══██╗██╔═══██╗╚══██╔══╝{Fore.CYAN} ║
{Fore.CYAN}║{Fore.MAGENTA} ██╔████╔██║██║   ██║███████╗██║██║     {Fore.CYAN}    ██████╔╝██║   ██║   ██║   {Fore.CYAN} ║
{Fore.CYAN}║{Fore.MAGENTA} ██║╚██╔╝██║██║   ██║╚════██║██║██║     {Fore.CYAN}    ██╔══██╗██║   ██║   ██║   {Fore.CYAN} ║
{Fore.CYAN}║{Fore.MAGENTA} ██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗{Fore.CYAN}    ██████╔╝╚██████╔╝   ██║   {Fore.CYAN} ║
{Fore.CYAN}║{Fore.MAGENTA} ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝{Fore.CYAN}    ╚═════╝  ╚═════╝    ╚═╝   {Fore.CYAN} ║
{Fore.CYAN}╚═══════════════════════════════════════════════════════════╝
{Fore.GREEN}              Sophisticated Telegram Music Voice Bot
{Fore.YELLOW}                 Version 1.0.0 - © 2025
"""

# Configure basic logging with enhanced format and color
logging.basicConfig(
    level=logging.INFO,
    format=f"{Fore.BLUE}%(asctime)s {Fore.YELLOW}[%(levelname)s] {Fore.GREEN}%(name)s: {Style.RESET_ALL}%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def check_first_run():
    """Check if this is the first time running the bot and display helpful information."""
    first_run_file = "data/first_run_completed"
    os.makedirs("data", exist_ok=True)
    
    if not os.path.exists(first_run_file):
        print(f"\n{Fore.CYAN}╔{'═' * 60}")
        print(f"{Fore.CYAN}║ {Fore.YELLOW}WELCOME TO THE TELEGRAM MUSIC BOT!")
        print(f"{Fore.CYAN}╚{'═' * 60}")
        
        print(f"\n{Fore.CYAN}📖 {Fore.WHITE}This appears to be your first time running the bot. Here's a quick guide:")
        
        print(f"\n{Fore.YELLOW}🔑 REQUIRED CREDENTIALS:")
        print(f"{Fore.WHITE} • API_ID, API_HASH: Get from https://my.telegram.org/apps")
        print(f"{Fore.WHITE} • BOT_TOKEN: Get from @BotFather on Telegram")
        print(f"{Fore.WHITE} • SESSION_STRING: Generate using @StringFatherBot")
        
        print(f"\n{Fore.YELLOW}🎵 SPOTIFY INTEGRATION:")
        print(f"{Fore.WHITE} • Get SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET from https://developer.spotify.com/dashboard")
        print(f"{Fore.WHITE} • Set these in your .env file for full music search and playback features")
        
        print(f"\n{Fore.YELLOW}📝 BASIC COMMANDS:")
        print(f"{Fore.WHITE} • /start - Begin interaction with the bot")
        print(f"{Fore.WHITE} • /play <song name> - Play a song in the voice chat")
        print(f"{Fore.WHITE} • /help - Show all available commands")
        
        print(f"\n{Fore.YELLOW}🔄 UPDATES:")
        print(f"{Fore.WHITE} • For updates and more information, check the GitHub repository")
        print(f"{Fore.WHITE} • Remember to keep your SESSION_STRING secure and updated\n")
        
        # Create the file to mark first run as completed
        with open(first_run_file, "w") as f:
            f.write(str(datetime.now()))

def check_environment():
    """Verify required environment variables and system compatibility."""
    required_vars = ["API_ID", "API_HASH", "BOT_TOKEN", "SESSION_STRING"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    # Check for first run
    check_first_run()
    
    if missing_vars:
        logger.error(f"{Fore.RED}Missing required environment variables: {', '.join(missing_vars)}")
        print(f"\n{Fore.RED}ERROR: {Fore.YELLOW}Please set the following environment variables in your .env file:")
        for var in missing_vars:
            print(f"{Fore.YELLOW}  - {var}")
        return False
    
    # Check for Spotify credentials (optional but recommended)
    if not (os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET")):
        logger.warning(f"{Fore.YELLOW}Spotify credentials not found. Music search and playback features may be limited.")
    
    return True

async def main():
    """Main function to start the bot."""
    # Display banner and system info
    print(BANNER)
    print(f"{Fore.CYAN}System Information:")
    print(f"{Fore.CYAN}╔{'═' * 50}")
    print(f"{Fore.CYAN}║ {Fore.GREEN}Platform:      {Style.RESET_ALL}{platform.system()} {platform.release()}")
    print(f"{Fore.CYAN}║ {Fore.GREEN}Python:        {Style.RESET_ALL}{platform.python_version()}")
    print(f"{Fore.CYAN}║ {Fore.GREEN}Time:          {Style.RESET_ALL}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Fore.CYAN}║ {Fore.GREEN}Directory:     {Style.RESET_ALL}{os.getcwd()}")
    print(f"{Fore.CYAN}╚{'═' * 50}\n")
    
    # Check environment before proceeding
    if not check_environment():
        sys.exit(1)
    
    # Start bot initialization with progress indication
    print(f"{Fore.YELLOW}Starting bot initialization...")
    for i in range(5):
        print(f"{Fore.YELLOW}Loading {'.' * (i+1)}", end='\r')
        time.sleep(0.2)
    print(f"{Fore.GREEN}Loading complete!{' ' * 20}")
    
    try:
        # Import here to avoid any potential circular imports
        from bot import create_bot
        
        # Create and initialize the bot
        print(f"{Fore.YELLOW}Creating bot instance...")
        bot = await create_bot()
        logger.info(f"{Fore.GREEN}Bot initialization complete!")
        print(f"{Fore.GREEN}Bot successfully initialized and ready to serve!{Style.RESET_ALL}")
        
        # Handle signals for graceful shutdown
        def signal_handler(sig, frame):
            print(f"\n{Fore.YELLOW}Shutdown signal received. Cleaning up...{Style.RESET_ALL}")
            logger.info("Shutdown signal received")
            asyncio.create_task(bot.stop())
            print(f"{Fore.GREEN}Shutdown complete. Goodbye!{Style.RESET_ALL}")
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run the bot indefinitely
        print(f"{Fore.GREEN}Bot is now running. Press Ctrl+C to stop.{Style.RESET_ALL}")
        logger.info("Bot is now running")
        await bot.idle()
        
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        
        # Extract error information
        error_str = str(e).lower()
        error_type = type(e).__name__
        
        # Draw error box header
        print(f"\n{Fore.RED}╔{'═' * 60}")
        print(f"{Fore.RED}║ {Fore.YELLOW}ERROR DETECTED: {Fore.RED}{error_type}")
        print(f"{Fore.RED}╚{'═' * 60}")
        
        # Check for known error types and provide specific guidance
        if "session_revoked" in error_str or "unauthorized" in error_str or "invalid" in error_str or "session" in error_str:
            # SESSION_STRING errors
            print(f"\n{Fore.YELLOW}📢 Your SESSION_STRING has been revoked or is invalid.")
            print(f"{Fore.YELLOW}🔍 This can happen if:")
            print(f"{Fore.YELLOW}  • You've terminated all sessions from your Telegram account settings")
            print(f"{Fore.YELLOW}  • The session has expired")
            print(f"{Fore.YELLOW}  • There were too many authentication attempts")
            print(f"\n{Fore.GREEN}✅ To fix this issue, the bot owner needs to:")
            print(f"{Fore.GREEN}  1️⃣ Generate a new SESSION_STRING using an external tool like @StringFatherBot")
            print(f"{Fore.GREEN}  2️⃣ Update the SESSION_STRING in the .env file")
            print(f"{Fore.GREEN}  3️⃣ Restart the bot")
        
        elif "api_id_invalid" in error_str or "api_hash_invalid" in error_str or "api" in error_str:
            # API credentials errors
            print(f"\n{Fore.YELLOW}📢 Your API_ID or API_HASH appears to be invalid.")
            print(f"{Fore.YELLOW}🔍 These credentials are required to authenticate with Telegram's API.")
            print(f"\n{Fore.GREEN}✅ To fix this issue:")
            print(f"{Fore.GREEN}  1️⃣ Visit {Fore.CYAN}https://my.telegram.org/apps{Fore.GREEN} to get your API credentials")
            print(f"{Fore.GREEN}  2️⃣ Update API_ID and API_HASH in your .env file")
            print(f"{Fore.GREEN}  3️⃣ Restart the bot")
        
        elif "bot_token_invalid" in error_str or "token" in error_str:
            # Bot token errors
            print(f"\n{Fore.YELLOW}📢 Your BOT_TOKEN appears to be invalid.")
            print(f"{Fore.YELLOW}🔍 This token is required for your bot to connect to Telegram.")
            print(f"\n{Fore.GREEN}✅ To fix this issue:")
            print(f"{Fore.GREEN}  1️⃣ Talk to @BotFather on Telegram to create or retrieve your bot token")
            print(f"{Fore.GREEN}  2️⃣ Update BOT_TOKEN in your .env file")
            print(f"{Fore.GREEN}  3️⃣ Restart the bot")
        
        elif "floodwait" in error_str or "flood" in error_str:
            # Rate limiting errors
            print(f"\n{Fore.YELLOW}📢 Telegram is rate-limiting your bot (FloodWait error).")
            print(f"{Fore.YELLOW}🔍 This happens when too many requests are made in a short period.")
            print(f"\n{Fore.GREEN}✅ To fix this issue:")
            print(f"{Fore.GREEN}  1️⃣ Wait for the specified time before restarting")
            print(f"{Fore.GREEN}  2️⃣ Consider implementing more aggressive rate limiting in your code")
        
        elif "spotify" in error_str:
            # Spotify API errors
            print(f"\n{Fore.YELLOW}📢 There was an issue with the Spotify API integration.")
            print(f"{Fore.YELLOW}🔍 This could be due to missing or invalid Spotify credentials.")
            print(f"\n{Fore.GREEN}✅ To fix this issue:")
            print(f"{Fore.GREEN}  1️⃣ Check that SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are correctly set")
            print(f"{Fore.GREEN}  2️⃣ Verify that your Spotify Developer account is active")
            print(f"{Fore.GREEN}  3️⃣ Restart the bot")
        
        elif "import" in error_str or "module" in error_str or "no module" in error_str:
            # Missing module errors
            print(f"\n{Fore.YELLOW}📢 There was an issue importing required modules.")
            print(f"{Fore.YELLOW}🔍 This could be due to missing dependencies or installation issues.")
            print(f"\n{Fore.GREEN}✅ To fix this issue:")
            print(f"{Fore.GREEN}  1️⃣ Make sure all dependencies are installed: {Fore.CYAN}pip install -r requirements.txt")
            print(f"{Fore.GREEN}  2️⃣ Check for any specific module installation errors")
            print(f"{Fore.GREEN}  3️⃣ Restart the bot")
            
        else:
            # Generic error handling for unexpected issues
            print(f"\n{Fore.YELLOW}📢 An unexpected error occurred:")
            print(f"{Fore.RED}{str(e)}")
            print(f"\n{Fore.YELLOW}🔍 Error details: Check the logs for more information.")
        
        # Common help footer for all errors
        print(f"\n{Fore.CYAN}📚 More information and troubleshooting tips can be found in the README.md file.")
        print(f"{Fore.CYAN}🌟 If the issue persists, please report it on GitHub with the error details.")
        
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Bot stopped by user.{Style.RESET_ALL}")
        sys.exit(0)