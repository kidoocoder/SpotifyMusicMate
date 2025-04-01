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
            print("\nTo fix this issue, you need to generate a new SESSION_STRING:")
            print("1. Run: python session_generator.py")
            print("2. Follow the prompts to log in with your Telegram account")
            print("3. Save the new SESSION_STRING to your .env file")
            print("4. Restart the bot")
            print("\nRun the session generator now? (y/n)")
            
            user_input = input().strip().lower()
            if user_input == "y":
                try:
                    from session_generator import generate_session_string
                    asyncio.run(generate_session_string())
                except Exception as session_error:
                    print(f"Error running session generator: {session_error}")
        
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())