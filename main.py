import asyncio
import logging
import os
import signal
import sys
from dotenv import load_dotenv

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def main():
    """Main function to start the bot."""
    try:
        # Import here to avoid any potential circular imports
        from bot import create_bot
        
        # Create and initialize the bot
        bot = await create_bot()
        logger.info("Bot initialization complete")
        
        # Handle signals for graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutdown signal received")
            asyncio.create_task(bot.stop())
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run the bot indefinitely
        logger.info("Bot is now running")
        await bot.idle()
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        
        # Check for SESSION_REVOKED error and provide helpful guidance
        error_str = str(e).lower()
        if "session_revoked" in error_str or "unauthorized" in error_str or "invalid" in error_str:
            print("\n" + "=" * 60)
            print("SESSION STRING ERROR DETECTED")
            print("=" * 60)
            print("\nYour SESSION_STRING has been revoked or is invalid.")
            print("This can happen if:")
            print("- You've terminated all sessions from your Telegram account settings")
            print("- The session has expired")
            print("- There were too many authentication attempts")
            print("\nTo fix this issue, the bot owner needs to:")
            print("1. Generate a new SESSION_STRING using an external tool")
            print("2. Update the SESSION_STRING in the .env file")
            print("3. Restart the bot")
            print("\nYou can find more information in the README.md file.")
        
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())