# WhatsApp Bot - Discord Version

An AI-powered Discord bot that helps you manage tasks, schedule events, and get help with commands using natural language.

## What This Bot Does

- **Task Management**: Create and organize your tasks with simple commands
- **Calendar Events**: Schedule meetings and events automatically
- **Command Help**: Get explanations for any command or tool
- **Smart Reminders**: Never forget important tasks
- **Easy to Use**: Just type what you want in plain English

## New Features - Task Management

### Creating Tasks

Use `/task` to create tasks with natural language:

**Basic Examples:**
```
/task Buy groceries tomorrow at 5pm
/task Call mom this weekend
/task Review quarterly report by Friday
/task Clean desk #organization
```

**With Priority:**
```
/task Urgent: Fix server issue #work #critical
/task Important presentation prep #work #high
/task Low priority: Organize desk #personal
```

**With Tags (use #):**
```
/task Buy groceries #shopping #personal
/task Review code #work #development #urgent
/task Schedule dentist #health #appointment
```

### How Task Creation Works

The bot automatically:
- **Extracts the task title** from your message
- **Detects priority** from keywords like "urgent", "important", "low"
- **Finds due dates** from phrases like "tomorrow", "next week", "3pm"
- **Creates tags** from words starting with #
- **Sets default priority** to "medium" if not specified

### Managing Your Tasks

**View your tasks:**
```
/tasks                    # Shows all pending tasks
/tasks pending           # Shows pending tasks only
/tasks completed         # Shows completed tasks
/tasks in_progress       # Shows tasks you're working on
```

**Complete a task:**
```
/complete 123            # Marks task #123 as done
```

### Task Properties

Each task has:
- **Title**: What you need to do (auto-generated from your message)
- **Description**: Your full message
- **Due Date**: When it's due (if you mentioned a time)
- **Priority**: Low, Medium, High, or Urgent
- **Status**: Pending, In Progress, Completed, or Cancelled
- **Tags**: For organizing tasks (like #work, #personal)

## All Available Commands

### Task Commands
- `/task <description>` - Create a new task
- `/tasks [status]` - List your tasks (pending/completed/in_progress)
- `/complete <task_id>` - Mark a task as completed

### Calendar Commands
- `/ask_personal <description>` - Schedule a calendar event
- `/set_timezone <timezone>` - Set your timezone (e.g., Asia/Ho_Chi_Minh)

### Help Commands
- `/help <query>` - Get help with commands and tools
- `/stats` - See your usage statistics
- `/system` - System analytics (admin only)

## Step-by-Step Setup Guide

### Step 1: Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Give your bot a name (like "My Task Bot")
4. Go to the "Bot" section
5. Click "Add Bot"
6. Copy the **Bot Token** (you'll need this later)

### Step 2: Get API Keys

1. **OpenAI API Key**: 
   - Go to [platform.openai.com](https://platform.openai.com)
   - Sign up or log in
   - Go to API Keys section
   - Create a new key

2. **FireCrawl API Key**: 
   - Go to [firecrawl.com](https://firecrawl.com)
   - Sign up for an account
   - Get your API key

### Step 3: Set Up Your Project

1. **Create environment file:**
   ```bash
   cp discord_env_example.txt .env
   ```

2. **Edit the .env file** with your tokens:
   ```bash
   DISCORD_BOT_TOKEN=your_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   FIRECRAWL_API_KEY=your_firecrawl_api_key_here
   USE_MCP=true
   DRY_RUN=false
   ```

3. **Install Python dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

### Step 4: Run the Bot

1. **Start the MCP server** (in one terminal):
   ```bash
   python -m app.mcp.server
   ```

2. **Start the bot** (in another terminal):
   ```bash
   USE_MCP=true python -m app.main
   ```

### Step 5: Add Bot to Your Server

1. In Discord Developer Portal, go to "OAuth2" → "URL Generator"
2. Select "bot" scope
3. Select these permissions:
   - Send Messages
   - Use Slash Commands
   - Read Message History
4. Copy the generated URL and open it in your browser
5. Select your Discord server and click "Authorize"

## How to Use - Simple Examples

### Creating Your First Task

1. Type: `/task Buy milk tomorrow`
2. The bot will create a task with:
   - Title: "Buy Milk"
   - Due Date: Tomorrow
   - Priority: Medium
   - Status: Pending

### Scheduling a Meeting

1. Type: `/ask_personal Team meeting tomorrow 3pm for 1 hour`
2. The bot will:
   - Create a calendar event
   - Send you a link to the event
   - Add it to your Google Calendar (if connected)

### Getting Help

1. Type: `/help git commit`
2. The bot will:
   - Search for git commit documentation
   - Give you a clear explanation
   - Show you examples

### Checking Your Tasks

1. Type: `/tasks`
2. The bot will show you all your pending tasks with:
   - Task ID
   - Title
   - Due date
   - Priority
   - Tags

### Completing a Task

1. Type: `/complete 1` (where 1 is the task ID)
2. The bot will mark that task as completed

## Tips for Best Results

### Task Creation Tips
- **Be specific with times**: "3pm" is better than "later"
- **Use tags for organization**: `#work`, `#personal`, `#urgent`
- **Set priorities**: Use words like "urgent", "important", "low"
- **Include context**: "Call mom about dinner plans" is better than just "Call mom"

### Time Examples
- "tomorrow" = tomorrow
- "next week" = next week
- "3pm" = today at 3pm
- "Friday 2pm" = Friday at 2pm
- "in 2 hours" = 2 hours from now

### Priority Keywords
- **Urgent**: "urgent", "asap", "emergency", "critical"
- **High**: "important", "high", "priority"
- **Low**: "low", "whenever", "sometime"
- **Medium**: everything else

## Advanced Features

### Analytics and Monitoring
- **Rate Limiting**: Prevents API overuse
- **Caching**: Speeds up common requests
- **Error Recovery**: Automatic retry with backoff
- **Usage Metrics**: Track command usage and performance

### Natural Language Processing
- **Intent Classification**: Understands what you want to do
- **Smart Routing**: Sends requests to the right specialist
- **Conversation Handling**: Responds naturally to greetings and thanks

### WhatsApp Integration (Coming Soon)
- Send messages via WhatsApp Business API
- Interactive buttons and quick replies
- Webhook handling for incoming messages

## MCP Architecture

The bot uses Model Context Protocol (MCP) for clean specialist separation:

### Specialists
- **PersonalSpecialist**: Handles calendar events and scheduling
- **CommandSpecialist**: Provides help with commands and tools
- **NLPSpecialist**: Routes requests based on intent
- **AnalyticsSpecialist**: Provides usage statistics

### MCP Tools
- `create_event(user_id, summary, start_iso, end_iso)` - Create calendar events
- `search_docs(query)` - Search documentation
- `list_today(user_id)` - List today's calendar events
- `propose_slots(user_id, minutes, count)` - Find free time slots

### Dry Run Mode
Set `DRY_RUN=true` to preview calls without side effects:
```
/ask_personal team sync tomorrow 3pm for 45m
→ DRY_RUN create_event {"user_id": 123, "summary": "Team Sync", "start_iso": "...", "end_iso": "..."}
```

## Troubleshooting

### Bot Not Responding
- Check if the bot is online in your Discord server
- Make sure both the MCP server and bot are running
- Check the console for error messages

### Tasks Show "Untitled"
- Make sure you're using the latest version of the code
- Try being more specific: "Buy groceries" instead of just "groceries"

### Can't Create Calendar Events
- You need to connect your Google account first
- Use `/connect_google` (coming soon)
- For now, use `/task` for reminders

### Commands Not Working
- Make sure you typed the command correctly (with the `/`)
- Check that the bot has the right permissions
- Try restarting the bot

### API Errors
- Verify your OpenAI API key has credits
- Check your FireCrawl API key is valid
- Ensure you have internet connectivity

### Permission Errors
- Make sure the bot has "Send Messages" permission in the channel
- Check that slash commands are enabled for the bot

## File Structure

```
app/
├── main.py                    # Bot entry point
├── cogs/discord_bot.py        # Discord commands
├── agents/specialists.py      # AI specialists (Personal, Command, NLP, Analytics)
├── tools/
│   ├── task_manager.py        # Task management system
│   ├── google_calendar.py     # Google Calendar integration
│   └── firecrawl_client.py    # Documentation scraping
├── services/
│   ├── mcp_client.py          # MCP client with retry logic
│   ├── metrics.py             # Usage analytics
│   ├── cache.py               # Response caching
│   ├── context.py             # Context aggregation
│   ├── llm.py                 # Local LLM helper
│   └── whatsapp_client.py     # WhatsApp integration
├── mcp/server.py              # MCP server
├── utils/timeparse.py         # Time parsing utilities
├── config.py                  # Configuration management
├── user_settings.py           # User preferences
└── google_oauth.py            # Google OAuth helper
```

## What's Next

The bot is designed to grow with your needs. Future features might include:
- **WhatsApp Integration**: Full WhatsApp Business API support
- **Team Collaboration**: Shared tasks and calendars
- **Advanced Automation**: Smart reminders and workflow automation
- **Multi-platform**: Slack, Microsoft Teams integration
- **Voice Commands**: Voice-to-task conversion
- **AI Learning**: Personalized suggestions based on usage

## Development

### Adding New Features
1. Create new specialists in `app/agents/specialists.py`
2. Add MCP tools in `app/mcp/server.py`
3. Update Discord commands in `app/cogs/discord_bot.py`
4. Use the metrics system for monitoring

### Testing
- Use `DRY_RUN=true` for safe testing
- Check logs for detailed debugging
- Use `/stats` and `/system` for monitoring

## Need Help?

If you're having trouble:
1. Check the console for error messages
2. Make sure all API keys are correct
3. Verify the bot has the right permissions
4. Try restarting both the MCP server and bot
5. Use `DRY_RUN=true` to debug issues

## License

This project is open source. Feel free to modify and share!