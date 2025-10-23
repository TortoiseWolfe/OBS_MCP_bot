# Quickstart: Twitch Chat Bot Development

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Twitch account with OAuth token
- Anthropic Claude API key

## Environment Setup

```bash
# Add to .env file
TWITCH_OAUTH_TOKEN=oauth:your_token_here
TWITCH_CHANNEL=your_channel_name
TWITCH_BOT_NICK=your_bot_username
CLAUDE_API_KEY=sk-ant-your-key-here
```

## Install Dependencies

```bash
pip install twitchio==2.10.0 anthropic==0.40.0 anthropic[aiohttp]
```

## Run Locally

```bash
# Start OBS orchestrator (dependency)
docker-compose up obs-orchestrator

# Run chat bot
python3 -m src.services.twitch_chat_bot
```

## Test Commands

In Twitch chat:
- `!help` - Show available commands
- `!uptime` - Show stream uptime
- `!commands` - List all commands
- `!ask what is recursion?` - Ask AI a question

## Development Workflow

1. **Feature branch**: `002-twitch-chat-bot`
2. **Run tests**: `pytest tests/integration/test_twitch_chat_bot.py`
3. **Check style**: `ruff check src/services/twitch_chat_bot.py`
4. **Commit**: Follow existing commit message style

## Key Files

- `src/services/twitch_chat_bot.py` - Main bot service
- `src/services/claude_queue.py` - AI question queue
- `src/services/moderation.py` - Rate limiting & spam detection
- `src/config/settings.py` - Configuration (extend TwitchSettings)
- `tests/integration/test_twitch_chat_bot.py` - Integration tests
