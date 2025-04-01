from flask import Flask, render_template
import os

app = Flask(__name__)

@app.route('/')
def index():
    # Get the bot username from environment variables or use a default
    bot_username = os.getenv('BOT_USERNAME', 'YourMusicBot')
    
    return render_template('index.html', bot_username=bot_username)

@app.route('/stats')
def stats():
    """Stats page - will show global stats about the bot usage."""
    # This could be implemented later to show global stats from the database
    return render_template('index.html', bot_username=os.getenv('BOT_USERNAME', 'YourMusicBot'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)