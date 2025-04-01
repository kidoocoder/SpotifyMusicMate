#!/bin/bash

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.7 or higher."
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
required_version="3.7"
if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Python version must be 3.7 or higher. Current version: $python_version"
    exit 1
fi

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "ffmpeg is not installed. Installing ffmpeg..."
    if [ "$(uname)" == "Darwin" ]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install ffmpeg
        else
            echo "Homebrew is not installed. Please install Homebrew and then ffmpeg."
            exit 1
        fi
    elif [ "$(uname)" == "Linux" ]; then
        # Linux
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y ffmpeg
        elif command -v yum &> /dev/null; then
            sudo yum install -y ffmpeg
        else
            echo "Unsupported package manager. Please install ffmpeg manually."
            exit 1
        fi
    else
        echo "Unsupported operating system. Please install ffmpeg manually."
        exit 1
    fi
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
# Try to use requirements-external.txt first, fallback to dependencies.txt
if [ -f "requirements-external.txt" ]; then
    cp requirements-external.txt requirements.txt
    pip install -r requirements.txt
elif [ -f "dependencies.txt" ]; then
    pip install -r dependencies.txt
else
    echo "Error: No requirements file found!"
    exit 1
fi

# Create directories
echo "Creating necessary directories..."
mkdir -p cache data

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "Please edit the .env file with your API credentials."
fi

echo "Installation complete!"
echo "Run the bot with: source venv/bin/activate && python main.py"