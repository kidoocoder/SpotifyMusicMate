# Telegram Music Bot

A sophisticated Telegram bot for playing Spotify songs in group/channel voice chats with an interactive UI.

## Features

- Play music from Spotify in Telegram voice chats
- Search for songs directly within Telegram
- Queue management with add, remove, and reorder functionality
- Display song lyrics for currently playing or requested songs
- Interactive UI with playback controls
- Volume control and audio quality settings
- User profiles with personalized settings
- Favorites system to save and access your favorite songs
- User activity tracking for advanced analytics
- Multi-language support for global accessibility
- Persistent settings and play history
- Multi-platform deployment support (VPS, Heroku, Replit)

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
The SESSION_STRING is a special authentication token that allows the bot to access your user account (needed for voice chat functionality).

The SESSION_STRING must be generated externally by the bot owner using tools like:
- [Pyrogram String Session Generator](https://replit.com/@dashezup/generate-pyrogram-session-string)
- [t.me/StringSessionBot](https://t.me/StringSessionBot) (official Telegram bot)

Once generated, add the SESSION_STRING to your `.env` file.

**Important Notes about SESSION_STRING:**
- The SESSION_STRING gives full access to your Telegram account - keep it secure and never share it
- Session strings can expire or be revoked by Telegram for security reasons
- If you get a "SESSION_REVOKED" error, you need to generate a new SESSION_STRING
- Only the bot owner should generate and handle the SESSION_STRING

#### Spotify API (Required)
1. Visit https://developer.spotify.com/dashboard/
2. Create a new application to get your `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`

#### Genius API (Optional)
1. Visit https://genius.com/api-clients
2. Create a new API client to get your `GENIUS_API_TOKEN`
3. This token is used for enhanced lyrics functionality (if not provided, the bot will use limited web scraping)

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

#### Music Information
- `/lyrics [optional: song name]` - Get lyrics for the currently playing song or a specified song
- `/stats` - Show statistics about the bot usage in the current chat

## Directory Structure

- `bot/` - Bot code
  - `__init__.py` - Core bot initialization
  - `commands.py` - Command handlers
  - `config.py` - Configuration and environment settings
  - `database.py` - Database operations
  - `helpers.py` - Utility functions
  - `lyrics.py` - Song lyrics retrieval functionality
  - `queue_manager.py` - Queue management
  - `spotify.py` - Spotify API integration
  - `ui.py` - User interface components
  - `voice_chat.py` - Voice chat functionality
- `assets/` - Static assets
- `cache/` - Cached audio files
- `data/` - Persistent data storage

## Troubleshooting

### SESSION_REVOKED Error
If you see an error like "SESSION_REVOKED - The authorization has been invalidated":

1. The bot owner must generate a new SESSION_STRING using external tools like:
   - [Pyrogram String Session Generator](https://replit.com/@dashezup/generate-pyrogram-session-string)
   - Telegram bot: [@StringSessionBot](https://t.me/StringSessionBot)

2. Update the `.env` file with the new SESSION_STRING

3. Restart the bot

### Audio Issues
If the bot joins voice chats but doesn't play audio:

1. Check if the Spotify track has a preview available (not all tracks do)
2. Verify that PyTgCalls is installed correctly
3. Try using a different audio file format or quality setting

### API Rate Limits
If you encounter rate limit errors:

1. Reduce the bot usage frequency
2. Implement a delay between commands
3. Consider using a different API account

### Lyrics Issues
If lyrics are not displaying correctly:

1. Make sure the Genius API token is correctly set in your `.env` file (optional but recommended)
2. Check if the song name and artist are correctly recognized
3. Try using the format `/lyrics artist - song` for more accurate results
4. Some songs may not have lyrics available in the database

## Deployment Options

### Local Deployment

#### Automated Installation (Recommended)

##### On Linux/macOS:
```
chmod +x install.sh
./install.sh
```

##### On Windows:
```
install.bat
```

These scripts will:
1. Check for required dependencies (Python, ffmpeg)
2. Create a virtual environment
3. Install all required packages
4. Set up directories and configuration files

#### Manual Installation

1. Install required dependencies:
   ```
   # If deploying outside of Replit, rename requirements-external.txt to requirements.txt first
   cp requirements-external.txt requirements.txt  # On Linux/macOS
   # OR
   copy requirements-external.txt requirements.txt  # On Windows

   # Then install the dependencies
   pip install -r requirements.txt
   ```

2. Run the bot:
   ```
   python main.py
   ```

### VPS Deployment

#### Using Docker

1. Make sure Docker and Docker Compose are installed on your server
2. Clone the repository
3. Create a `.env` file with your environment variables
4. Build and start the container:
   ```
   docker-compose up -d
   ```

5. View logs:
   ```
   docker-compose logs -f
   ```

#### Without Docker

1. Install system dependencies:
   ```
   apt-get update && apt-get install -y ffmpeg
   ```

2. Install Python dependencies:
   ```
   # If deploying outside of Replit
   cp requirements-external.txt requirements.txt  # On Linux/macOS
   # OR
   copy requirements-external.txt requirements.txt  # On Windows
   pip install -r requirements.txt
   
   # If using the dependencies.txt file directly
   pip install -r dependencies.txt
   ```

3. Start the bot:
   ```
   python main.py
   ```

### Heroku Deployment

#### Option 1: One-Click Deploy (Recommended)
[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

This will:
1. Create a new Heroku application
2. Configure the necessary buildpacks
3. Prompt you to set environment variables
4. Deploy the bot automatically

#### Option 2: Manual Deployment

1. Create a new Heroku application
2. Add the following buildpacks:
   - `heroku/python`
   - `https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest.git`

3. Set the environment variables in Heroku dashboard or using CLI:
   ```
   heroku config:set API_ID=your_api_id
   heroku config:set API_HASH=your_api_hash
   heroku config:set BOT_TOKEN=your_bot_token
   heroku config:set SESSION_STRING=your_session_string
   heroku config:set SPOTIFY_CLIENT_ID=your_spotify_client_id
   heroku config:set SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   ```

4. Deploy to Heroku:
   ```
   git push heroku main
   ```

### Replit Deployment

1. Fork this repository to your GitHub account
2. Create a new Replit project from your GitHub repository
3. Set up Secrets in the Replit dashboard:
   - Go to "Secrets" in the sidebar
   - Add all required environment variables:
     - `API_ID`
     - `API_HASH`
     - `BOT_TOKEN`
     - `SESSION_STRING`
     - `SPOTIFY_CLIENT_ID`
     - `SPOTIFY_CLIENT_SECRET`
     - `GENIUS_API_TOKEN` (optional)
4. In the `.replit` file, make sure the run command is set to `python main.py`
5. Click the "Run" button to start the bot