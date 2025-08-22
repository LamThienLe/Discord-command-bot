@echo off
echo Command Help Bot - Discord Version
echo ==================================

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Check if .env file exists
if not exist ".env" (
    echo Error: .env file not found!
    echo Please copy discord_env_example.txt to .env and fill in your tokens.
    pause
    exit /b 1
)

REM Run the bot
echo Starting Discord bot...
python -m app.main

pause
