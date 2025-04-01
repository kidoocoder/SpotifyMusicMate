import asyncio
import os
from pyrogram import Client

async def generate_session_string():
    """Generate a session string for Pyrogram."""
    api_id = int(input("Please enter your API ID: "))
    api_hash = input("Please enter your API Hash: ")
    
    # Create a temporary client to generate session string
    async with Client(
        ":memory:",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True
    ) as app:
        print("\nSession string (copy this):")
        print(await app.export_session_string())

if __name__ == "__main__":
    asyncio.run(generate_session_string())