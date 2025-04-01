# Telegram Music Bot

A Telegram bot for playing Spotify songs in group/channel voice chats with an interactive UI.

## Features

- Play music from Spotify in Telegram voice chats
- Search for songs directly within Telegram
- Queue management with add, remove, and reorder functionality
- Interactive UI with playback controls
- Volume control
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

- `/start`, `/help` - Show help message
- `/play [song name or URL]` - Play a song
- `/search [song name]` - Search for a song
- `/pause` - Pause playback
- `/resume` - Resume playback
- `/skip` - Skip to the next song
- `/stop` - Stop playback and clear queue
- `/volume [0-200]` - Set volume
- `/queue` - Show current queue
- `/current` - Show current playing song
- `/ping` - Check bot's response time
- `/stats` - Show bot statistics

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