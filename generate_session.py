import asyncio
import logging
import os
from pyrogram import Client
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def generate_session():
    """Generate a new session string using credentials from .env file"""
    # Get API credentials from environment
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    
    if not api_id or not api_hash:
        logger.error("API_ID or API_HASH not found in .env file")
        return
    
    try:
        api_id = int(api_id)
    except ValueError:
        logger.error("API_ID must be an integer")
        return
    
    logger.info("Creating Telegram client with your API credentials")
    logger.info("You will need to log in with your phone number")
    
    # Create a new client
    async with Client(
        "temp_session",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True
    ) as app:
        # Export the session string
        session_string = await app.export_session_string()
        
        logger.info("="*50)
        logger.info("SESSION STRING GENERATED SUCCESSFULLY")
        logger.info("="*50)
        logger.info("\nYour new SESSION_STRING is:\n")
        logger.info(session_string)
        logger.info("\nUpdating .env file with new SESSION_STRING...")
        
        # Update the .env file
        env_path = ".env"
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                content = f.read()
            
            # Replace the old SESSION_STRING with the new one
            if "SESSION_STRING=" in content:
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if line.startswith("SESSION_STRING="):
                        lines[i] = f"SESSION_STRING={session_string}"
                        break
                content = "\n".join(lines)
            else:
                content += f"\nSESSION_STRING={session_string}"
            
            # Write the updated content
            with open(env_path, "w") as f:
                f.write(content)
            
            logger.info("SESSION_STRING has been updated in .env file")
            logger.info("Restart the bot to use the new session string")
        else:
            logger.error(".env file not found")
            logger.info("Your SESSION_STRING is: %s", session_string)
            logger.info("Add this to your .env file manually")

if __name__ == "__main__":
    asyncio.run(generate_session())