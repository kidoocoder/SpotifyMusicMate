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

def check_environment():
    """Verify required environment variables and system compatibility."""
    required_vars = ["API_ID", "API_HASH", "BOT_TOKEN", "SESSION_STRING"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
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
        
        # Check for SESSION_REVOKED error and provide helpful guidance
        error_str = str(e).lower()
        if "session_revoked" in error_str or "unauthorized" in error_str or "invalid" in error_str:
            print(f"\n{Fore.RED}" + "=" * 60)
            print(f"{Fore.RED}SESSION STRING ERROR DETECTED")
            print(f"{Fore.RED}" + "=" * 60)
            print(f"\n{Fore.YELLOW}Your SESSION_STRING has been revoked or is invalid.")
            print(f"{Fore.YELLOW}This can happen if:")
            print(f"{Fore.YELLOW}- You've terminated all sessions from your Telegram account settings")
            print(f"{Fore.YELLOW}- The session has expired")
            print(f"{Fore.YELLOW}- There were too many authentication attempts")
            print(f"\n{Fore.GREEN}To fix this issue, the bot owner needs to:")
            print(f"{Fore.GREEN}1. Generate a new SESSION_STRING using an external tool")
            print(f"{Fore.GREEN}2. Update the SESSION_STRING in the .env file")
            print(f"{Fore.GREEN}3. Restart the bot")
            print(f"\n{Fore.CYAN}You can find more information in the README.md file.")
        else:
            print(f"\n{Fore.RED}ERROR: An unexpected error occurred:")
            print(f"{Fore.YELLOW}{str(e)}")
            print(f"\n{Fore.GREEN}Please check the logs for more details.")
        
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Bot stopped by user.{Style.RESET_ALL}")
        sys.exit(0)