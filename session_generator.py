import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

HEADER = """
╔════════════════════════════════════════╗
║      TELEGRAM BOT SESSION GENERATOR     ║
║        Generate SESSION_STRING          ║
╚════════════════════════════════════════╝
"""

INSTRUCTIONS = """
This tool will help you generate a SESSION_STRING for your assistant account.
The assistant account will be used to join voice chats and play music.

You will need:
1. Your Telegram account (phone number)
2. API_ID and API_HASH from https://my.telegram.org/apps

The SESSION_STRING allows the bot to act on behalf of your user account
without storing your actual password or credentials.

IMPORTANT: This SESSION_STRING gives full access to your Telegram account.
           NEVER share it with anyone or post it publicly.
"""

async def generate_session_string():
    """Generate a session string for Pyrogram."""
    print(HEADER)
    print(INSTRUCTIONS)
    
    try:
        from pyrogram import Client
    except ImportError:
        print("\n❌ Error: Pyrogram is not installed.")
        print("Please run: pip install pyrogram tgcrypto")
        return
    
    api_id = input("\nEnter your API ID: ") or os.getenv("API_ID")
    api_hash = input("Enter your API HASH: ") or os.getenv("API_HASH")
    
    if not api_id or not api_hash:
        print("\n❌ Error: API ID and API HASH are required!")
        return
    
    try:
        api_id = int(api_id)
    except ValueError:
        print("\n❌ Error: API ID must be an integer!")
        return
    
    print("\n📱 You will now receive a code on your Telegram account.")
    print("Please enter the code when prompted.\n")
    
    try:
        async with Client(
            ":memory:",
            api_id=api_id,
            api_hash=api_hash,
            in_memory=True
        ) as app:
            session_string = await app.export_session_string()
            print("\n✅ Session generated successfully!")
            print("\nYour SESSION_STRING is:")
            print("=" * 50)
            print(session_string)
            print("=" * 50)
            print("\n⚠️  KEEP THIS STRING SAFE AND NEVER SHARE IT WITH ANYONE! ⚠️")
            print("This string gives full access to your Telegram account.")
            
            # Optionally save to .env file
            save_option = input("\nDo you want to save this to your .env file? (y/n): ").lower()
            if save_option == "y":
                env_file = ".env"
                
                # Create .env file if it doesn't exist
                if not os.path.exists(env_file):
                    with open(env_file, "w") as f:
                        f.write(f"API_ID={api_id}\n")
                        f.write(f"API_HASH={api_hash}\n")
                        f.write(f"SESSION_STRING={session_string}\n")
                    print(f"✅ Created new {env_file} file with your credentials")
                else:
                    # Read existing .env file
                    with open(env_file, "r") as f:
                        env_content = f.read()
                    
                    # Update or add SESSION_STRING
                    if "SESSION_STRING=" in env_content:
                        env_content = env_content.replace(
                            f"SESSION_STRING={os.getenv('SESSION_STRING', '')}",
                            f"SESSION_STRING={session_string}"
                        )
                    else:
                        env_content += f"\nSESSION_STRING={session_string}"
                    
                    # Make sure API_ID and API_HASH are also saved
                    if "API_ID=" not in env_content:
                        env_content += f"\nAPI_ID={api_id}"
                    if "API_HASH=" not in env_content:
                        env_content += f"\nAPI_HASH={api_hash}"
                    
                    # Write updated content
                    with open(env_file, "w") as f:
                        f.write(env_content)
                    
                    print(f"✅ Updated {env_file} with your new SESSION_STRING")
                
                print("\n🔄 Please restart the bot for changes to take effect.")
            else:
                print("\nPlease add this SESSION_STRING to your .env file manually.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Failed to generate session string. Please try again.")

if __name__ == "__main__":
    try:
        asyncio.run(generate_session_string())
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)