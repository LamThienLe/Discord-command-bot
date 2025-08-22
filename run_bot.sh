#!/bin/bash

# Command Help Bot - Run Script

echo "Command Help Bot - Discord Version"
echo "=================================="

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found!"
    echo "Please copy discord_env_example.txt to .env and fill in your tokens."
    exit 1
fi

# Run the bot
echo "Starting Discord bot..."
python -m app.main
