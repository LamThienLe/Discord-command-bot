# Command Help Bot - Discord Version

An AI-powered Discord bot that helps users learn about commands and tools using OpenAI and FireCrawl.

## Features

- **Discord Integration**: Easy-to-use Discord bot with slash commands
- **AI-Powered Help**: Get explanations for commands and tools using GPT-4o-mini
- **Documentation Scraping**: Automatically fetches documentation using FireCrawl
- **Smart Caching**: Common commands are cached for instant responses
- **Rich Embeds**: Formatted Discord embeds with syntax highlighting

## Supported Commands

### /help [query]
Get help with any command or tool. Examples:
- `/help grep` - Learn about the grep command
- `/help tar` - Learn how to use tar
- `/help docker` - Learn Docker basics
- `/help git commit` - Learn about git commit

## Setup Instructions

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Give your bot a name
4. Go to the "Bot" section
5. Click "Add Bot"
6. Copy the **Bot Token** (you'll need this for the .env file)

### 2. Get API Keys

1. **OpenAI API Key**: Get from [platform.openai.com](https://platform.openai.com)
2. **FireCrawl API Key**: Get from [firecrawl.com](https://firecrawl.com)

### 3. Configure Environment

1. Copy the example environment file:
   ```bash
   cp discord_env_example.txt .env
   ```

2. Edit `.env` and fill in your tokens:
   ```bash
   DISCORD_BOT_TOKEN=your_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   FIRECRAWL_API_KEY=your_firecrawl_api_key_here
   ```

### 4. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Run the Bot

```bash
python -m app.main
```

Or use the convenient run script:
```bash
./run_bot.sh  # On Windows: run_bot.bat
```

### 6. Invite Bot to Your Server

1. In Discord Developer Portal, go to "OAuth2" → "URL Generator"
2. Select "bot" scope
3. Select these permissions:
   - Send Messages
   - Use Slash Commands
   - Read Message History
4. Copy the generated URL and open it in your browser
5. Select your Discord server and click "Authorize"

## Usage

Once the bot is running and invited to your server:

1. Type `/help` followed by a command or tool name
2. The bot will either:
   - Return a cached response (instant)
   - Fetch documentation and generate an AI response (takes a few seconds)

### Examples

```
/help grep
/help how to unzip files
/help docker run
/help git status
```

## How It Works

1. **Cache Check**: First checks if the query matches a known command
2. **Documentation Fetching**: If not cached, uses FireCrawl to fetch relevant docs
3. **AI Generation**: Sends the query and context to OpenAI for a structured response
4. **Discord Response**: Formats the response as a rich Discord embed

## File Structure

```
app/
├── __init__.py
├── main.py              # Bot entry point
├── discord_bot.py       # Discord bot logic
├── config.py           # Configuration management
├── cache.py            # Command cache
├── firecrawl.py        # FireCrawl API client
├── agent.py            # OpenAI integration
└── whatsapp.py         # Legacy WhatsApp code (can be removed)

requirements.txt         # Python dependencies
discord_env_example.txt  # Environment variables template
```

## Customization

### Adding More Cached Commands

Edit `app/cache.py` to add more pre-defined command explanations:

```python
COMMON_ANSWERS = {
    "new_command": (
        "Explanation: Brief description of what the command does.\n\n"
        "Syntax:\n```\nnew_command [OPTIONS] ARGUMENTS\n```\n\n"
        "Example:\n```\nnew_command --help\n```"
    ),
    # Add more commands here
}
```

### Changing the AI Model

Edit `app/agent.py` to use a different OpenAI model:

```python
# Change this line in generate_structured_answer()
payload = {
    "model": "gpt-4",  # or "gpt-3.5-turbo"
    # ... rest of payload
}
```

## Troubleshooting

### Bot Not Responding
- Check if the bot is online in your Discord server
- Verify the bot token in `.env` is correct
- Check the console for error messages

### API Errors
- Verify your OpenAI API key has credits
- Check your FireCrawl API key is valid
- Ensure you have internet connectivity

### Permission Errors
- Make sure the bot has "Send Messages" permission in the channel
- Check that slash commands are enabled for the bot

## License

This project is open source. Feel free to modify and distribute.
