#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import signal
import sys
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import test bot
from test_bot import bot

async def main():
    """Main function to start the test bot."""
    try:
        logger.info("Starting test bot...")
        
        # Start the bot
        await bot.start()
        
        # Handle graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal, closing bot...")
            asyncio.create_task(bot.stop())
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep the bot running
        logger.info("Bot is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(60)
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
    finally:
        if bot.is_connected:
            await bot.stop()
            logger.info("Bot stopped.")

if __name__ == "__main__":
    # Check if required environment variables are set
    required_env_vars = [
        "BOT_TOKEN", 
        "API_ID", 
        "API_HASH"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set them in .env file or environment")
        sys.exit(1)
    
    # Run the main function
    asyncio.run(main())