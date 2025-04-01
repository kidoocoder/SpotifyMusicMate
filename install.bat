@echo off
echo Checking Python installation...

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in PATH. Please install Python 3.7 or higher.
    exit /b 1
)

for /f "tokens=* USEBACKQ" %%F in (`python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"`) do (
    set PYTHON_VERSION=%%F
)

echo Python version: %PYTHON_VERSION%

:: Check if ffmpeg is installed
where ffmpeg >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo FFmpeg is not installed or not in PATH.
    echo Please download FFmpeg from https://ffmpeg.org/download.html and add it to your PATH.
    echo After installing FFmpeg, run this script again.
    exit /b 1
)

echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
:: Try to use requirements-external.txt first, fallback to dependencies.txt
if exist requirements-external.txt (
    copy requirements-external.txt requirements.txt
    pip install -r requirements.txt
) else if exist dependencies.txt (
    pip install -r dependencies.txt
) else (
    echo Error: No requirements file found!
    exit /b 1
)

echo Creating necessary directories...
if not exist cache mkdir cache
if not exist data mkdir data

if not exist .env (
    echo Creating .env file from example...
    copy .env.example .env
    echo Please edit the .env file with your API credentials.
)

echo Installation complete!
echo Run the bot with: venv\Scripts\activate.bat ^&^& python main.py

pause