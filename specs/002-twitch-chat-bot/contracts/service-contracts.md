# Service Contracts: Twitch Chat Bot

**Internal Service APIs**

## TwitchChatBotService

### `start() -> None`
Start the Twitch IRC bot service

**Triggers**: Main application startup
**Side Effects**: Connects to Twitch IRC, starts background tasks

### `stop() -> None`
Stop the bot service gracefully

**Side Effects**: Disconnects from IRC, cancels background tasks

### `send_notification(message: str) -> None`
Send notification to Twitch chat

**Used By**: OBS orchestrator (e.g., stream starting notification)

## ClaudeQuestionQueue

### `submit_question(username: str, question: str) -> UUID`
Submit AI question to processing queue

**Returns**: Request ID for tracking
**Errors**: `QueueFullError` if 100 requests queued

### `get_queue_status() -> QueueMetrics`
Get current queue metrics

**Returns**: Queue depth, average wait time, throughput

## ModerationService

### `check_rate_limit(username: str, command: str) -> RateLimitResult`
Check if user can execute command

**Returns**: `{allowed: bool, retry_after_seconds: float}`

### `check_spam(username: str, message: str) -> bool`
Check if message is spam

**Returns**: True if spam detected

### `add_timeout(username: str, duration: int, reason: str) -> None`
Add user to temporary ignore list

## StreamStatusCache

### `get_uptime() -> str`
Get formatted stream uptime

**Cache**: 10 seconds
**Fallback**: "Stream status unavailable" if Health API down
