# Telegram Music Bot

A sophisticated Telegram bot for playing Spotify songs in group/channel voice chats with an interactive UI.

## Features

- Play music from Spotify in Telegram voice chats
- Search for songs directly within Telegram
- Queue management with add, remove, and reorder functionality
- Interactive UI with playback controls
- Volume control and audio quality settings
- User profiles with personalized settings
- Favorites system to save and access your favorite songs
- User activity tracking for advanced analytics
- Multi-language support for global accessibility
- Persistent settings and play history

## Requirements

- Python 3.7+
- Telegram API credentials
- Spotify API credentials
- A Telegram account for the assistant (for joining voice chats)

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your Telegram and Spotify API credentials

### Getting API Credentials

#### Telegram API (Required)
1. Visit https://my.telegram.org/apps
2. Create a new application and get your `API_ID` and `API_HASH`
3. Create a bot with @BotFather on Telegram to get the `BOT_TOKEN`

#### Session String (Required)
Generate a session string for your assistant account:
```
python session_generator.py
```
Follow the prompts to log in with your Telegram account that will be used as the assistant.

#### Spotify API (Required)
1. Visit https://developer.spotify.com/dashboard/
2. Create a new application to get your `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`

## Usage

Start the bot:
```
python main.py
```

### Bot Commands

#### Basic Commands
- `/start`, `/help` - Show help message and list of commands
- `/play [song name or URL]` - Play a song or add it to queue
- `/search [song name]` - Search for a song on Spotify
- `/pause` - Pause the current playback
- `/resume` - Resume the paused playback
- `/skip` - Skip to the next song in the queue
- `/stop` - Stop playback and leave the voice chat
- `/volume [0-200]` - Set playback volume (default: 100)
- `/queue` - Show the current song queue
- `/current` - Show information about the currently playing song
- `/ping` - Check the bot's response time

#### User Commands
- `/profile` - View your user profile with statistics and preferences
- `/settings` - Configure your personal preferences
- `/favorite` - Add the currently playing song to your favorites
- `/favorites` - List your favorite songs

#### Statistics and Information
- `/stats` - Show statistics about the bot usage in the current chat

## Directory Structure

- `bot/` - Bot code
  - `__init__.py` - Core bot initialization
  - `commands.py` - Command handlers
  - `config.py` - Configuration and environment settings
  - `database.py` - Database operations
  - `helpers.py` - Utility functions
  - `queue_manager.py` - Queue management
  - `spotify.py` - Spotify API integration
  - `ui.py` - User interface components
  - `voice_chat.py` - Voice chat functionality
- `assets/` - Static assets
- `cache/` - Cached audio files
- `data/` - Persistent data storage