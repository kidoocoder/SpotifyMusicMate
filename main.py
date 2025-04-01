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

async def main():
    """Main function to start the bot."""
    try:
        from bot import create_bot
        
        # Initialize and start the bot
        bot = await create_bot()
        
        # Handle graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal, closing bot...")
            asyncio.create_task(bot.stop())
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep the bot running
        await bot.idle()
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Check if required environment variables are set
    required_env_vars = [
        "BOT_TOKEN", 
        "API_ID", 
        "API_HASH", 
        "SPOTIFY_CLIENT_ID", 
        "SPOTIFY_CLIENT_SECRET"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set them in .env file or environment")
        sys.exit(1)
    
    # Run the main function
    asyncio.run(main())
