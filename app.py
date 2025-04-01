from flask import Flask, render_template_string, redirect, url_for

app = Flask(__name__)

# HTML template for the index page
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Music Bot</title>
    <link rel="stylesheet" href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css">
    <style>
        .container { 
            max-width: 800px; 
            margin-top: 50px; 
        }
        .bot-info {
            background-color: rgba(33, 37, 41, 0.8);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .features-list li {
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="bot-info">
            <h1 class="text-center mb-4">Telegram Music Bot</h1>
            <p class="lead text-center">A bot for playing Spotify songs in Telegram voice chats</p>
            
            <div class="text-center mb-4">
                <a href="tg://resolve?domain={{ bot_username }}" class="btn btn-primary">Open Bot in Telegram</a>
            </div>
        </div>
        
        <div class="bot-info">
            <h2>Commands</h2>
            <ul class="list-unstyled">
                <li><code>/start</code> - Show start message</li>
                <li><code>/help</code> - Show help message</li>
                <li><code>/play [song name or URL]</code> - Play a song</li>
                <li><code>/search [song name]</code> - Search for a song</li>
                <li><code>/pause</code> - Pause playback</li>
                <li><code>/resume</code> - Resume playback</li>
                <li><code>/skip</code> - Skip to next song</li>
                <li><code>/stop</code> - Stop playback and clear queue</li>
                <li><code>/volume [0-200]</code> - Set volume</li>
                <li><code>/queue</code> - Show current queue</li>
                <li><code>/current</code> - Show current playing song</li>
                <li><code>/ping</code> - Check bot's response time</li>
                <li><code>/stats</code> - Show bot statistics</li>
            </ul>
        </div>
        
        <div class="bot-info">
            <h2>Features</h2>
            <ul class="features-list">
                <li>Play music from Spotify in Telegram voice chats</li>
                <li>Search for songs directly within Telegram</li>
                <li>Queue management with add, remove, and reorder functionality</li>
                <li>Interactive UI with playback controls</li>
                <li>Volume control</li>
                <li>Persistent settings and play history</li>
            </ul>
        </div>
        
        <div class="text-center text-muted mt-4">
            <p>&copy; 2025 Telegram Music Bot</p>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    # Get the bot username from environment variables or use a default
    import os
    bot_username = os.getenv('BOT_USERNAME', 'YourMusicBot')
    
    return render_template_string(INDEX_TEMPLATE, bot_username=bot_username)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)