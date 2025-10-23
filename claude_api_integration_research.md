# Claude API Integration Research - Best Practices for Python Asyncio

**Research Date:** 2025-10-22
**Target Application:** OBS_bot - Python 3.11+ asyncio streaming management
**Requirements:** 50-100 concurrent requests, <10s response time (90%), 450-char limit, rate limiting

---

## Executive Summary

This research evaluates integration strategies for Anthropic's Claude API in a Python asyncio application with specific focus on handling 50-100 concurrent question requests while maintaining sub-10-second response times. The official `anthropic` Python SDK provides native async support, built-in retry logic, and is the recommended approach over custom HTTP clients.

**Key Findings:**
- Official SDK includes async client (`AsyncAnthropic`) with built-in rate limiting and retry logic
- Token bucket algorithm used for API rate limits (50 RPM, 30K ITPM, 8K OTPM for Tier 1)
- Recommended pattern: `asyncio.Queue` + `asyncio.Semaphore` for request management
- Response times achievable with proper concurrency limiting and queue management
- Character limit requires token estimation (450 chars ≈ 113 tokens)

---

## 1. Official Claude Python SDK vs Custom HTTP Client

### Recommendation: Use Official SDK

**Package:** `anthropic` (latest version via PyPI)
**Repository:** https://github.com/anthropics/anthropic-sdk-python
**Python Requirements:** 3.8+ (3.11+ recommended for async performance)

### Why Official SDK?

1. **Native Async Support** - Full `async`/`await` integration with `AsyncAnthropic` client
2. **Built-in Retry Logic** - Automatic retries for 408, 409, 429, 5xx errors (2 retries by default)
3. **Timeout Management** - Default 10-minute timeout, configurable per-request
4. **Type Safety** - Complete type definitions for all request/response models
5. **Streaming Support** - Native async streaming for real-time responses
6. **Maintained** - Official Anthropic support with regular updates

### Installation

```bash
# Basic installation
pip install anthropic

# With aiohttp backend (recommended for better concurrency)
pip install anthropic[aiohttp]
```

Add to `/home/turtle_wolfe/repos/OBS_bot/requirements.txt`:
```
anthropic==0.40.0  # Claude API client with async support
```

### Basic Async Client Setup

```python
import asyncio
from anthropic import AsyncAnthropic

# Initialize client (reads ANTHROPIC_API_KEY from environment)
client = AsyncAnthropic(
    timeout=10.0,  # 10 seconds to meet <10s requirement
    max_retries=2,  # Built-in retry logic
)

async def ask_claude(question: str) -> str:
    """Send question to Claude and get response."""
    message = await client.messages.create(
        model="claude-sonnet-4-5-20250929",  # Latest Sonnet model
        max_tokens=150,  # Approximately 200 chars (buffer for 450 char limit)
        messages=[{"role": "user", "content": question}],
    )
    return message.content[0].text
```

### Custom HTTP Client (Not Recommended)

While possible to build with `httpx` or `aiohttp`, you would need to manually implement:
- Token bucket rate limiting
- Exponential backoff retry logic
- Request/response schema validation
- Error code handling (429, 529, 5xx)
- Timeout management
- Connection pooling

**Verdict:** Not worth the maintenance burden. Use official SDK.

---

## 2. Async Request Patterns and Best Practices

### Recommended Architecture: Producer-Consumer Pattern

```python
import asyncio
from anthropic import AsyncAnthropic
from typing import NamedTuple
from datetime import datetime, timedelta

class QuestionRequest(NamedTuple):
    """Question request with metadata."""
    user_id: str
    question: str
    timestamp: datetime

class ClaudeService:
    """Claude API service with async queue management."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(
            api_key=api_key,
            timeout=10.0,  # Meet <10s requirement
            max_retries=2,
        )

        # Queue management (FIFO)
        self.queue: asyncio.Queue[QuestionRequest] = asyncio.Queue(maxsize=100)

        # Concurrency control (limit concurrent API calls)
        self.semaphore = asyncio.Semaphore(10)  # 10 concurrent requests max

        # Per-user rate limiting (1 per 60 seconds)
        self.user_last_request: dict[str, datetime] = {}
        self.user_rate_limit_sec = 60

    async def enqueue_question(self, user_id: str, question: str) -> bool:
        """
        Add question to queue with user rate limiting.

        Returns:
            True if queued, False if rate limited or queue full
        """
        # Check per-user rate limit
        now = datetime.now()
        if user_id in self.user_last_request:
            last_request = self.user_last_request[user_id]
            if now - last_request < timedelta(seconds=self.user_rate_limit_sec):
                return False  # Rate limited

        # Try to add to queue (non-blocking)
        try:
            self.queue.put_nowait(QuestionRequest(user_id, question, now))
            self.user_last_request[user_id] = now
            return True
        except asyncio.QueueFull:
            return False

    async def worker(self, worker_id: int):
        """
        Consumer worker that processes questions from queue.

        Uses semaphore to limit concurrent API calls.
        """
        while True:
            # Get next question from queue (FIFO)
            request = await self.queue.get()

            try:
                # Acquire semaphore slot (limit concurrent API calls)
                async with self.semaphore:
                    response = await self._ask_claude(request.question)
                    await self._send_response(request.user_id, response)

            except Exception as e:
                # Log error and continue processing
                await self._handle_error(request.user_id, e)
            finally:
                # Mark task as done
                self.queue.task_done()

    async def _ask_claude(self, question: str) -> str:
        """Call Claude API with timeout and retry logic."""
        message = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=150,  # ~200 chars (450 char target with buffer)
            messages=[{"role": "user", "content": question}],
            temperature=0.7,
        )

        # Extract text and truncate to 450 chars
        text = message.content[0].text
        if len(text) > 450:
            text = text[:447] + "..."

        return text

    async def _send_response(self, user_id: str, response: str):
        """Send response back to user (integrate with Twitch IRC)."""
        # TODO: Implement Twitch IRC message sending
        pass

    async def _handle_error(self, user_id: str, error: Exception):
        """Handle API errors gracefully."""
        # Log error
        import logging
        logging.error(f"Claude API error for user {user_id}: {error}")

        # Send fallback message to user
        await self._send_response(user_id, "Sorry, I'm having trouble responding right now.")

    async def start(self, num_workers: int = 10):
        """Start worker pool to process questions."""
        workers = [
            asyncio.create_task(self.worker(i))
            for i in range(num_workers)
        ]
        await asyncio.gather(*workers)
```

### Integration with Existing OBS_bot

```python
# src/services/claude_service.py
import asyncio
from anthropic import AsyncAnthropic
from src.config.settings import get_settings

class ClaudeQuestionService:
    """
    Claude API integration for Twitch chat questions.

    Runs independently of OBS control loop to prevent blocking.
    """

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(
            api_key=settings.claude.api_key,  # Add to settings.py
            timeout=settings.claude.timeout_sec,
            max_retries=settings.claude.max_retries,
        )

        self.queue = asyncio.Queue(maxsize=settings.claude.max_queue_size)
        self.semaphore = asyncio.Semaphore(settings.claude.max_concurrent_requests)
        self.user_rate_limiter = {}

    async def run(self):
        """Main service loop (runs as background task)."""
        # Start worker pool
        workers = [
            asyncio.create_task(self.worker(i))
            for i in range(10)  # 10 concurrent workers
        ]

        # Keep running until shutdown
        await asyncio.gather(*workers)
```

### Best Practices Summary

1. **Separate from Main Event Loop** - Run Claude service as independent background task
2. **Queue-Based Architecture** - Decouple request ingestion from processing
3. **Semaphore for API Limits** - Control concurrent API calls (not just queue size)
4. **Per-User Rate Limiting** - Track last request time per user (1/60s requirement)
5. **Graceful Degradation** - Continue processing queue even if individual requests fail
6. **Timeout Enforcement** - Set aggressive timeouts (10s) to meet SLA

---

## 3. Rate Limiting Strategies

### API-Side Rate Limits (Anthropic Tier 1)

| Metric | Limit | Notes |
|--------|-------|-------|
| **Requests Per Minute (RPM)** | 50 | All models |
| **Input Tokens Per Minute (ITPM)** | 30,000 | Sonnet 4.x |
| **Output Tokens Per Minute (OTPM)** | 8,000 | Sonnet 4.x |

**Algorithm:** Token bucket (continuous replenishment, not fixed intervals)
**Error Response:** HTTP 429 with `retry-after` header (seconds to wait)

### Client-Side Rate Limiting Strategy

#### 1. Per-User Rate Limiting (Application Requirement)

```python
from datetime import datetime, timedelta
from collections import defaultdict

class UserRateLimiter:
    """Enforce 1 question per user per 60 seconds."""

    def __init__(self, window_sec: int = 60):
        self.window_sec = window_sec
        self.last_request: dict[str, datetime] = {}

    def is_allowed(self, user_id: str) -> bool:
        """Check if user can make request."""
        now = datetime.now()

        if user_id not in self.last_request:
            self.last_request[user_id] = now
            return True

        last_request = self.last_request[user_id]
        if now - last_request >= timedelta(seconds=self.window_sec):
            self.last_request[user_id] = now
            return True

        return False

    def time_until_allowed(self, user_id: str) -> float:
        """Get seconds until user can make next request."""
        if user_id not in self.last_request:
            return 0.0

        elapsed = (datetime.now() - self.last_request[user_id]).total_seconds()
        remaining = max(0, self.window_sec - elapsed)
        return remaining
```

#### 2. API Rate Limiting (Respect Anthropic Limits)

```python
import asyncio
import time
from collections import deque

class APIRateLimiter:
    """
    Token bucket rate limiter for API calls.

    Implements sliding window to respect:
    - 50 RPM (requests per minute)
    - 30,000 ITPM (input tokens per minute)
    - 8,000 OTPM (output tokens per minute)
    """

    def __init__(
        self,
        max_requests_per_min: int = 50,
        max_input_tokens_per_min: int = 30000,
        max_output_tokens_per_min: int = 8000,
    ):
        self.max_rpm = max_requests_per_min
        self.max_itpm = max_input_tokens_per_min
        self.max_otpm = max_output_tokens_per_min

        # Sliding window tracking
        self.request_times: deque[float] = deque()
        self.input_tokens: deque[tuple[float, int]] = deque()
        self.output_tokens: deque[tuple[float, int]] = deque()

        self.lock = asyncio.Lock()

    async def acquire(self, estimated_input_tokens: int, estimated_output_tokens: int):
        """
        Wait until rate limits allow request.

        Args:
            estimated_input_tokens: Estimated input tokens for request
            estimated_output_tokens: Estimated output tokens (max_tokens parameter)
        """
        async with self.lock:
            while True:
                now = time.time()
                cutoff = now - 60  # 1 minute window

                # Clean old entries
                self._clean_old_entries(cutoff)

                # Check if request would exceed limits
                current_requests = len(self.request_times)
                current_input = sum(tokens for _, tokens in self.input_tokens)
                current_output = sum(tokens for _, tokens in self.output_tokens)

                if (
                    current_requests < self.max_rpm
                    and current_input + estimated_input_tokens <= self.max_itpm
                    and current_output + estimated_output_tokens <= self.max_otpm
                ):
                    # Record request
                    self.request_times.append(now)
                    self.input_tokens.append((now, estimated_input_tokens))
                    self.output_tokens.append((now, estimated_output_tokens))
                    return

                # Wait before retrying
                await asyncio.sleep(1)

    def _clean_old_entries(self, cutoff: float):
        """Remove entries older than 1 minute."""
        while self.request_times and self.request_times[0] < cutoff:
            self.request_times.popleft()

        while self.input_tokens and self.input_tokens[0][0] < cutoff:
            self.input_tokens.popleft()

        while self.output_tokens and self.output_tokens[0][0] < cutoff:
            self.output_tokens.popleft()
```

#### 3. Combined Approach with Semaphore

**Recommended:** Use `asyncio.Semaphore` for concurrency control + custom rate limiter for API limits.

```python
class ClaudeAPIClient:
    """Claude API client with comprehensive rate limiting."""

    def __init__(self):
        self.client = AsyncAnthropic(timeout=10.0, max_retries=2)

        # Concurrency control (limit simultaneous requests)
        self.semaphore = asyncio.Semaphore(10)  # 10 concurrent requests

        # API rate limiting
        self.api_rate_limiter = APIRateLimiter(
            max_requests_per_min=45,  # Buffer below 50 RPM limit
            max_input_tokens_per_min=28000,  # Buffer below 30K limit
            max_output_tokens_per_min=7500,  # Buffer below 8K limit
        )

        # Per-user rate limiting
        self.user_rate_limiter = UserRateLimiter(window_sec=60)

    async def ask_question(self, user_id: str, question: str) -> str | None:
        """
        Ask Claude a question with full rate limiting.

        Returns:
            Response string or None if rate limited
        """
        # Check per-user rate limit
        if not self.user_rate_limiter.is_allowed(user_id):
            return None  # User rate limited

        # Estimate tokens (rough: 1 token ≈ 4 chars)
        input_tokens = len(question) // 4
        output_tokens = 150  # max_tokens setting

        # Wait for API rate limit availability
        await self.api_rate_limiter.acquire(input_tokens, output_tokens)

        # Acquire semaphore slot for concurrent request
        async with self.semaphore:
            response = await self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=output_tokens,
                messages=[{"role": "user", "content": question}],
            )

            return response.content[0].text
```

### Rate Limiting Summary

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| **Per-User** | Timestamp tracking | 1 question/60s per user |
| **Concurrency** | `asyncio.Semaphore(10)` | Limit simultaneous API calls |
| **API Requests** | Token bucket (sliding window) | Respect 50 RPM limit |
| **API Tokens** | Token bucket (sliding window) | Respect 30K ITPM, 8K OTPM limits |
| **Built-in SDK** | Automatic retry on 429 | Handle transient rate limit errors |

---

## 4. Error Handling and Retry Logic

### SDK Built-in Retry Logic

The official SDK **automatically retries** these errors up to 2 times (configurable):

- **408** - Request Timeout
- **409** - Conflict
- **429** - Rate Limit (with exponential backoff)
- **5xx** - Internal Server Errors
- **Connection errors** - Network issues

```python
# Configure retries
client = AsyncAnthropic(
    max_retries=3,  # Increase to 3 retries (default: 2)
    timeout=10.0,
)
```

### Custom Error Handling

```python
from anthropic import (
    APIError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
    APIConnectionError,
)
import asyncio
from typing import Optional

async def ask_claude_with_error_handling(
    client: AsyncAnthropic,
    question: str,
    max_attempts: int = 3,
) -> Optional[str]:
    """
    Ask Claude with comprehensive error handling.

    Returns:
        Response text or None if all retries failed
    """
    for attempt in range(max_attempts):
        try:
            response = await client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=150,
                messages=[{"role": "user", "content": question}],
            )
            return response.content[0].text

        except RateLimitError as e:
            # SDK already retried, but we hit hard limit
            # Extract retry-after header if available
            retry_after = getattr(e, 'retry_after', 5)

            import logging
            logging.warning(f"Rate limited, waiting {retry_after}s (attempt {attempt + 1})")

            if attempt < max_attempts - 1:
                await asyncio.sleep(retry_after)
                continue
            else:
                logging.error("Rate limit exceeded after all retries")
                return None

        except APITimeoutError:
            # Request took >10 seconds
            import logging
            logging.warning(f"Request timeout (attempt {attempt + 1})")

            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                logging.error("Request timeout after all retries")
                return None

        except InternalServerError as e:
            # 500/502/503 errors (Claude service issues)
            import logging
            logging.warning(f"Claude service error: {e} (attempt {attempt + 1})")

            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                logging.error("Service error after all retries")
                return None

        except APIConnectionError:
            # Network connectivity issues
            import logging
            logging.warning(f"Network error (attempt {attempt + 1})")

            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                logging.error("Network error after all retries")
                return None

        except APIError as e:
            # Generic API error (catch-all)
            import logging
            logging.error(f"Unexpected API error: {e}")
            return None

    return None  # All retries exhausted
```

### Graceful Degradation Strategy

```python
class ClaudeServiceWithFallback:
    """Claude service with fallback responses."""

    ERROR_MESSAGES = {
        "rate_limit": "I'm receiving too many questions right now. Please try again in a moment.",
        "timeout": "Sorry, that question took too long to process. Try a simpler question?",
        "service_error": "I'm having trouble connecting to my brain right now. Try again soon!",
        "generic": "Sorry, I couldn't process that question right now.",
    }

    async def ask_with_fallback(self, user_id: str, question: str) -> str:
        """
        Ask Claude with automatic fallback to error message.

        Always returns a response (never None).
        """
        try:
            response = await self.ask_claude(question)
            if response:
                return response
            else:
                return self.ERROR_MESSAGES["generic"]

        except RateLimitError:
            return self.ERROR_MESSAGES["rate_limit"]

        except APITimeoutError:
            return self.ERROR_MESSAGES["timeout"]

        except InternalServerError:
            return self.ERROR_MESSAGES["service_error"]

        except Exception:
            import logging
            logging.exception("Unexpected error in Claude service")
            return self.ERROR_MESSAGES["generic"]
```

### Error Monitoring

```python
from dataclasses import dataclass
from datetime import datetime
from collections import Counter

@dataclass
class ErrorMetrics:
    """Track error rates for monitoring."""
    total_requests: int = 0
    successful_requests: int = 0
    rate_limit_errors: int = 0
    timeout_errors: int = 0
    service_errors: int = 0
    network_errors: int = 0
    last_reset: datetime = None

    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100

    def error_breakdown(self) -> dict[str, int]:
        """Get error count breakdown."""
        return {
            "rate_limit": self.rate_limit_errors,
            "timeout": self.timeout_errors,
            "service": self.service_errors,
            "network": self.network_errors,
        }

# Integrate with health monitoring
class ClaudeServiceMonitored:
    """Claude service with error tracking."""

    def __init__(self):
        self.metrics = ErrorMetrics(last_reset=datetime.now())

    async def ask_with_metrics(self, question: str) -> Optional[str]:
        """Ask Claude and track success/failure metrics."""
        self.metrics.total_requests += 1

        try:
            response = await self.ask_claude(question)
            self.metrics.successful_requests += 1
            return response

        except RateLimitError:
            self.metrics.rate_limit_errors += 1
            raise

        except APITimeoutError:
            self.metrics.timeout_errors += 1
            raise

        except InternalServerError:
            self.metrics.service_errors += 1
            raise

        except APIConnectionError:
            self.metrics.network_errors += 1
            raise
```

### Error Handling Best Practices

1. **Let SDK Handle Initial Retries** - Don't disable built-in retry logic
2. **Custom Retry for Business Logic** - Add application-level retries for critical requests
3. **Exponential Backoff** - Use `2 ** attempt` for retry delays
4. **Respect `retry-after` Header** - On 429 errors, wait specified duration
5. **Circuit Breaker Pattern** - Stop requests if error rate exceeds threshold
6. **Fallback Responses** - Always return something to user (never fail silently)
7. **Comprehensive Logging** - Log all errors with context for debugging
8. **Metrics Collection** - Track error rates for monitoring/alerting

---

## 5. Queue Implementation Recommendations

### asyncio.Queue Overview

**FIFO Guarantee:** `asyncio.Queue` maintains strict first-in-first-out ordering
**Async-Native:** Non-blocking `put()` and `get()` operations with `await`
**Backpressure:** `maxsize` parameter blocks producers when queue is full
**Task Tracking:** `task_done()` and `join()` for coordinated shutdown

### Recommended Queue Architecture

```python
import asyncio
from typing import NamedTuple, Optional
from datetime import datetime
from anthropic import AsyncAnthropic

class QuestionRequest(NamedTuple):
    """Question request with metadata."""
    user_id: str
    username: str  # For response targeting
    question: str
    timestamp: datetime
    channel: str  # Twitch channel (for multi-channel support)

class QuestionResponse(NamedTuple):
    """Response with routing information."""
    user_id: str
    username: str
    response: str
    channel: str
    processing_time_ms: float

class ClaudeQuestionQueue:
    """
    Production-ready queue manager for Claude API questions.

    Features:
    - FIFO processing
    - Max queue size (100)
    - Concurrent workers (10)
    - Per-user rate limiting
    - Graceful shutdown
    - Metrics collection
    """

    def __init__(
        self,
        api_key: str,
        max_queue_size: int = 100,
        num_workers: int = 10,
        max_concurrent_api_calls: int = 10,
    ):
        # Claude API client
        self.client = AsyncAnthropic(
            api_key=api_key,
            timeout=10.0,
            max_retries=2,
        )

        # Request queue (FIFO)
        self.request_queue: asyncio.Queue[QuestionRequest] = asyncio.Queue(
            maxsize=max_queue_size
        )

        # Response queue (for sending back to Twitch)
        self.response_queue: asyncio.Queue[QuestionResponse] = asyncio.Queue()

        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent_api_calls)

        # Rate limiting
        self.user_last_request: dict[str, datetime] = {}
        self.rate_limit_sec = 60

        # Worker management
        self.num_workers = num_workers
        self.workers: list[asyncio.Task] = []
        self.running = False

        # Metrics
        self.total_processed = 0
        self.total_errors = 0
        self.queue_full_rejections = 0
        self.rate_limit_rejections = 0

    async def enqueue(self, request: QuestionRequest) -> tuple[bool, str]:
        """
        Enqueue question request with validation.

        Returns:
            (success, message) tuple
        """
        # Check per-user rate limit
        now = datetime.now()
        if request.user_id in self.user_last_request:
            last_request = self.user_last_request[request.user_id]
            elapsed = (now - last_request).total_seconds()
            if elapsed < self.rate_limit_sec:
                self.rate_limit_rejections += 1
                remaining = int(self.rate_limit_sec - elapsed)
                return False, f"Rate limited. Try again in {remaining}s."

        # Try to add to queue (non-blocking)
        try:
            self.request_queue.put_nowait(request)
            self.user_last_request[request.user_id] = now
            return True, f"Question queued (position: {self.request_queue.qsize()})"

        except asyncio.QueueFull:
            self.queue_full_rejections += 1
            return False, "Question queue is full. Try again later."

    async def worker(self, worker_id: int):
        """
        Consumer worker that processes questions.

        Runs until shutdown signal received.
        """
        import logging
        logger = logging.getLogger(f"claude_worker_{worker_id}")

        while self.running:
            try:
                # Get next request (blocks until available)
                request = await asyncio.wait_for(
                    self.request_queue.get(),
                    timeout=1.0,  # Check running flag every 1s
                )

                # Process request
                start_time = asyncio.get_event_loop().time()

                try:
                    # Limit concurrent API calls
                    async with self.semaphore:
                        response_text = await self._call_claude(request.question)

                    processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

                    # Enqueue response
                    response = QuestionResponse(
                        user_id=request.user_id,
                        username=request.username,
                        response=response_text,
                        channel=request.channel,
                        processing_time_ms=processing_time,
                    )
                    await self.response_queue.put(response)

                    self.total_processed += 1
                    logger.info(f"Processed question for {request.username} in {processing_time:.0f}ms")

                except Exception as e:
                    self.total_errors += 1
                    logger.error(f"Error processing question: {e}")

                    # Send fallback response
                    fallback = QuestionResponse(
                        user_id=request.user_id,
                        username=request.username,
                        response="Sorry, I couldn't process your question right now.",
                        channel=request.channel,
                        processing_time_ms=0,
                    )
                    await self.response_queue.put(fallback)

                finally:
                    self.request_queue.task_done()

            except asyncio.TimeoutError:
                # No requests in queue, continue loop
                continue

            except Exception as e:
                logger.exception(f"Worker {worker_id} error: {e}")

    async def _call_claude(self, question: str) -> str:
        """Call Claude API and format response."""
        message = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=150,  # ~200 chars (target: 450 chars max)
            messages=[{"role": "user", "content": question}],
            temperature=0.7,
        )

        # Extract and truncate response
        text = message.content[0].text
        if len(text) > 450:
            text = text[:447] + "..."

        return text

    async def start(self):
        """Start worker pool."""
        if self.running:
            return

        self.running = True
        self.workers = [
            asyncio.create_task(self.worker(i))
            for i in range(self.num_workers)
        ]

        import logging
        logging.info(f"Started {self.num_workers} Claude workers")

    async def stop(self, timeout_sec: float = 30.0):
        """
        Gracefully shutdown workers.

        Args:
            timeout_sec: Max time to wait for queue to drain
        """
        import logging
        logging.info("Stopping Claude service...")

        # Stop accepting new requests
        self.running = False

        # Wait for queue to drain (with timeout)
        try:
            await asyncio.wait_for(
                self.request_queue.join(),
                timeout=timeout_sec,
            )
            logging.info("All queued questions processed")
        except asyncio.TimeoutError:
            remaining = self.request_queue.qsize()
            logging.warning(f"Shutdown timeout: {remaining} questions not processed")

        # Cancel workers
        for worker in self.workers:
            worker.cancel()

        await asyncio.gather(*self.workers, return_exceptions=True)
        logging.info("Claude service stopped")

    def get_metrics(self) -> dict:
        """Get queue and processing metrics."""
        return {
            "queue_size": self.request_queue.qsize(),
            "response_queue_size": self.response_queue.qsize(),
            "total_processed": self.total_processed,
            "total_errors": self.total_errors,
            "queue_full_rejections": self.queue_full_rejections,
            "rate_limit_rejections": self.rate_limit_rejections,
            "success_rate": (
                (self.total_processed / (self.total_processed + self.total_errors) * 100)
                if self.total_processed + self.total_errors > 0
                else 100.0
            ),
        }
```

### Integration with Main Application

```python
# src/main.py
import asyncio
from src.services.claude_service import ClaudeQuestionQueue

async def main():
    """Main application entry point."""
    # Initialize services
    claude_service = ClaudeQuestionQueue(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_queue_size=100,
        num_workers=10,
    )

    # Start background services
    await claude_service.start()

    # Start other services (OBS, Twitch IRC, etc.)
    # ...

    try:
        # Run forever
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        # Graceful shutdown
        await claude_service.stop(timeout_sec=30)

if __name__ == "__main__":
    asyncio.run(main())
```

### Queue Monitoring Endpoint

```python
# src/api/health.py (extend existing health API)
from fastapi import APIRouter

router = APIRouter()

@router.get("/health/claude")
async def claude_health(claude_service: ClaudeQuestionQueue):
    """Get Claude service health metrics."""
    metrics = claude_service.get_metrics()

    # Determine health status
    queue_utilization = metrics["queue_size"] / 100.0  # Assuming max_queue_size=100
    error_rate = 100.0 - metrics["success_rate"]

    if queue_utilization > 0.9 or error_rate > 10.0:
        status = "degraded"
    elif queue_utilization > 0.95 or error_rate > 25.0:
        status = "unhealthy"
    else:
        status = "healthy"

    return {
        "status": status,
        "metrics": metrics,
        "thresholds": {
            "max_queue_size": 100,
            "max_error_rate_pct": 10.0,
            "max_queue_utilization_pct": 90.0,
        },
    }
```

### Queue Implementation Best Practices

1. **Use `asyncio.Queue` over threading queues** - Designed for async/await
2. **Set `maxsize` parameter** - Prevents unbounded memory growth
3. **Non-blocking enqueue** - Use `put_nowait()` and handle `QueueFull`
4. **Worker pool pattern** - Multiple consumers for concurrent processing
5. **Graceful shutdown** - Use `queue.join()` to wait for completion
6. **Separate response queue** - Decouple API processing from response delivery
7. **Metrics collection** - Track queue size, throughput, error rates
8. **Health checks** - Expose queue metrics via health API

---

## 6. Configuration Integration

### Add Claude Settings to OBS_bot

```python
# src/config/settings.py (additions)

class ClaudeSettings(BaseModel):
    """Claude API configuration."""

    api_key: str = Field(default="", exclude=True)  # Load from env
    model: str = "claude-sonnet-4-5-20250929"
    timeout_sec: int = 10
    max_retries: int = 2
    max_tokens: int = 150
    temperature: float = 0.7

    # Queue settings
    max_queue_size: int = 100
    num_workers: int = 10
    max_concurrent_api_calls: int = 10

    # Rate limiting
    user_rate_limit_sec: int = 60  # 1 question per user per minute

    # Response formatting
    max_response_chars: int = 450
    truncate_suffix: str = "..."

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key is configured."""
        if not v:
            import logging
            logging.warning("ANTHROPIC_API_KEY not configured - Claude service disabled")
        return v

class Settings(BaseSettings):
    """Main application settings."""

    # ... existing settings ...
    claude: ClaudeSettings = Field(default_factory=ClaudeSettings)

    @classmethod
    def load_from_yaml(cls, config_path: Path = Path("config/settings.yaml")) -> "Settings":
        """Load settings from YAML file + environment variables."""
        # ... existing code ...

        # Load Claude API key from environment
        import os
        settings.claude.api_key = os.getenv("ANTHROPIC_API_KEY", "")

        return settings
```

### Environment Variables

Add to `.env` file:
```bash
# Claude API Configuration
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx...
```

### YAML Configuration

Add to `config/settings.yaml`:
```yaml
claude:
  model: "claude-sonnet-4-5-20250929"
  timeout_sec: 10
  max_retries: 2
  max_tokens: 150
  temperature: 0.7
  max_queue_size: 100
  num_workers: 10
  max_concurrent_api_calls: 10
  user_rate_limit_sec: 60
  max_response_chars: 450
  truncate_suffix: "..."
```

---

## 7. Performance Considerations

### Response Time Target: <10 seconds (90% of requests)

**Current Tier 1 Limits:**
- 50 RPM = ~0.83 requests/second theoretical max
- With 10 concurrent workers = 10 requests in-flight simultaneously
- Average Claude API latency: ~2-5 seconds per request

**Calculation:**
- 10 workers × 5s avg latency = 2 requests/second throughput
- Queue of 100 requests = 50 seconds to drain when full
- Individual request: queue wait + API call (<5s queue + ~3s API = <8s typical)

**Conclusion:** Configuration supports requirements if:
1. Queue doesn't stay at capacity (design: reject new requests when full)
2. Workers set to 10 concurrent (matches API rate limits)
3. API timeout set to 10s (enforces hard limit)

### Token Estimation for 450 Character Limit

**Conversion:** ~1 token = 4 characters (English text)
**450 characters = ~113 tokens**

**Recommended `max_tokens` setting:**
- Set to 150 tokens (~200 chars) for safety buffer
- Truncate response to 450 chars in code
- Prevents over-generation waste

### Optimization Strategies

1. **Prompt Caching** - Cache system prompts to reduce input tokens
2. **Response Streaming** - Start sending response before completion (advanced)
3. **Model Selection** - Use Claude Haiku for faster responses (lower quality)
4. **Concurrent API Calls** - 10 workers = 10× throughput vs sequential
5. **Queue Size Tuning** - Reduce to 50 if <10s target not met with 100

---

## 8. Testing Recommendations

### Unit Tests

```python
# tests/unit/test_claude_service.py
import pytest
from datetime import datetime
from src.services.claude_service import ClaudeQuestionQueue, QuestionRequest

@pytest.mark.asyncio
async def test_user_rate_limiting():
    """Test per-user rate limiting (1 per 60s)."""
    queue = ClaudeQuestionQueue(api_key="test")

    request1 = QuestionRequest("user1", "alice", "Question 1", datetime.now(), "channel1")
    request2 = QuestionRequest("user1", "alice", "Question 2", datetime.now(), "channel1")

    success1, msg1 = await queue.enqueue(request1)
    assert success1, "First request should succeed"

    success2, msg2 = await queue.enqueue(request2)
    assert not success2, "Second request should be rate limited"
    assert "Rate limited" in msg2

@pytest.mark.asyncio
async def test_queue_full_rejection():
    """Test queue rejects when at capacity."""
    queue = ClaudeQuestionQueue(api_key="test", max_queue_size=2)

    # Fill queue
    for i in range(2):
        request = QuestionRequest(f"user{i}", f"user{i}", "Question", datetime.now(), "channel1")
        success, _ = await queue.enqueue(request)
        assert success

    # Next request should fail
    request = QuestionRequest("user3", "user3", "Question", datetime.now(), "channel1")
    success, msg = await queue.enqueue(request)
    assert not success
    assert "queue is full" in msg
```

### Integration Tests

```python
# tests/integration/test_claude_api.py
import pytest
import os
from anthropic import AsyncAnthropic

@pytest.mark.integration
@pytest.mark.asyncio
async def test_claude_api_connection():
    """Test real Claude API connection (requires API key)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not configured")

    client = AsyncAnthropic(api_key=api_key, timeout=10.0)

    response = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=150,
        messages=[{"role": "user", "content": "Say 'test successful' in one word"}],
    )

    assert response.content[0].text
    assert len(response.content[0].text) > 0
```

### Load Tests

```python
# tests/load/test_claude_concurrency.py
import asyncio
import pytest
from datetime import datetime
from src.services.claude_service import ClaudeQuestionQueue, QuestionRequest

@pytest.mark.load
@pytest.mark.asyncio
async def test_100_concurrent_requests():
    """Test handling 100 concurrent question requests."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not configured")

    queue = ClaudeQuestionQueue(
        api_key=api_key,
        max_queue_size=100,
        num_workers=10,
    )

    await queue.start()

    # Enqueue 100 requests
    requests = [
        QuestionRequest(f"user{i}", f"user{i}", f"Question {i}", datetime.now(), "channel1")
        for i in range(100)
    ]

    enqueue_start = asyncio.get_event_loop().time()

    for request in requests:
        success, _ = await queue.enqueue(request)
        assert success or queue.request_queue.qsize() == 100  # Queue full OK

    # Wait for processing
    await asyncio.wait_for(queue.request_queue.join(), timeout=120.0)

    total_time = asyncio.get_event_loop().time() - enqueue_start

    # Verify metrics
    metrics = queue.get_metrics()
    assert metrics["total_processed"] > 0
    assert metrics["success_rate"] > 90.0  # At least 90% success rate

    print(f"Processed {metrics['total_processed']} requests in {total_time:.2f}s")
    print(f"Success rate: {metrics['success_rate']:.1f}%")

    await queue.stop()
```

---

## 9. Security Considerations

### API Key Management

1. **Never commit API keys** - Use environment variables only
2. **Use `.env` file** - Add to `.gitignore`
3. **Rotate keys regularly** - Anthropic Console settings
4. **Limit key scope** - Use separate keys for dev/staging/prod
5. **Monitor usage** - Set up billing alerts in Anthropic Console

### Example `.env` file:
```bash
# .env (add to .gitignore)
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx...
```

### Docker Secrets

For production deployment:

```yaml
# docker-compose.yml
services:
  obs_bot:
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    env_file:
      - .env.production
```

### Input Validation

```python
def validate_question(question: str) -> tuple[bool, str]:
    """Validate user question before sending to API."""
    # Length check
    if len(question) < 5:
        return False, "Question too short (min 5 characters)"

    if len(question) > 500:
        return False, "Question too long (max 500 characters)"

    # Content filtering (basic)
    prohibited_terms = ["jailbreak", "ignore instructions", "system prompt"]
    if any(term in question.lower() for term in prohibited_terms):
        return False, "Question contains prohibited content"

    return True, "OK"
```

---

## 10. Cost Analysis

### Claude API Pricing (as of 2025-01-01)

**Claude Sonnet 4.5:**
- Input: $3.00 / million tokens
- Output: $15.00 / million tokens
- Cached input: $0.30 / million tokens (10% of base price)

### Cost Calculation for OBS_bot Use Case

**Assumptions:**
- Average question: 50 tokens input (200 chars)
- Average response: 150 tokens output (450 chars max)
- Volume: 1000 questions/day

**Daily Cost:**
- Input: 1000 × 50 tokens = 50K tokens = $0.15/day
- Output: 1000 × 150 tokens = 150K tokens = $2.25/day
- **Total: ~$2.40/day = $72/month**

**Optimization with Prompt Caching:**
If using system prompt (e.g., "You are a helpful Twitch chat assistant"):
- System prompt: 50 tokens (cached after first use)
- Cached cost: $0.30 / million tokens = 99% savings on repeated input

**With caching:**
- First request: 50 tokens @ $3.00 = $0.00015
- Subsequent 999: 50 tokens @ $0.30 = $0.000015 each
- **Savings: ~$0.13/day = $4/month**

### Rate Limit Budget

**Tier 1 Limits (Free/Entry):**
- 50 RPM = 3000 requests/hour = 72,000 requests/day (theoretical max)
- 30K ITPM = 1.8M input tokens/hour = enough for 36K questions/hour
- 8K OTPM = 480K output tokens/hour = enough for 3.2K responses/hour

**Conclusion:** Tier 1 limits sufficient for expected volume (<1000 questions/day)

---

## 11. Example Implementation Checklist

### Phase 1: Basic Integration

- [ ] Add `anthropic` to `requirements.txt`
- [ ] Add `ClaudeSettings` to `src/config/settings.py`
- [ ] Create `src/services/claude_service.py` with basic client
- [ ] Add `ANTHROPIC_API_KEY` to `.env` (and `.env.example`)
- [ ] Write unit tests for configuration loading
- [ ] Test basic API call with hardcoded question

### Phase 2: Queue System

- [ ] Implement `ClaudeQuestionQueue` with `asyncio.Queue`
- [ ] Add per-user rate limiting (`UserRateLimiter`)
- [ ] Add API rate limiting (`APIRateLimiter`)
- [ ] Implement worker pool (10 workers)
- [ ] Add graceful shutdown logic
- [ ] Write unit tests for queue management

### Phase 3: Twitch Integration

- [ ] Create Twitch IRC message parser for questions
- [ ] Integrate queue enqueue with Twitch message handler
- [ ] Implement response sender (Twitch IRC)
- [ ] Add command prefix (e.g., "!ask <question>")
- [ ] Test end-to-end flow (Twitch → Claude → Twitch)

### Phase 4: Error Handling

- [ ] Add comprehensive exception handling
- [ ] Implement fallback responses
- [ ] Add error metrics collection
- [ ] Set up logging for all error types
- [ ] Write integration tests for error scenarios

### Phase 5: Monitoring

- [ ] Add `/health/claude` endpoint to health API
- [ ] Expose queue metrics (size, throughput, errors)
- [ ] Add Discord alerts for high error rates
- [ ] Create Grafana dashboard (if using monitoring)
- [ ] Load test with 100 concurrent requests

### Phase 6: Optimization

- [ ] Implement prompt caching for repeated system prompts
- [ ] Tune worker count based on real-world usage
- [ ] Add response time percentile tracking (p50, p90, p99)
- [ ] Optimize token usage (reduce input/output where possible)
- [ ] Consider Claude Haiku for faster responses (if needed)

---

## 12. Summary and Recommendations

### Use Official SDK

**Package:** `anthropic` with `AsyncAnthropic` client
**Reason:** Built-in retry logic, timeout management, type safety, and maintenance

### Queue Architecture

**Pattern:** `asyncio.Queue` with worker pool
**Configuration:**
- Max queue size: 100
- Workers: 10 concurrent
- Semaphore: 10 concurrent API calls
- Per-user limit: 1 question/60s

### Rate Limiting

**Three-layer approach:**
1. Per-user rate limiting (application requirement)
2. Concurrency limiting with `asyncio.Semaphore`
3. API rate limiting with token bucket algorithm

### Error Handling

**Strategy:**
- Let SDK handle initial retries (built-in)
- Add application-level retry for critical requests
- Always return fallback response to user
- Log all errors with context
- Track error metrics for monitoring

### Performance

**Target:** <10s response time (90% of requests)
**Achievability:** Yes, with:
- 10 concurrent workers
- 10s API timeout
- Queue size limit to prevent excessive wait times
- Proper error handling to avoid blocking

### Cost

**Expected:** ~$2.40/day = $72/month for 1000 questions/day
**Optimization:** Use prompt caching to reduce by ~$4/month

---

## Appendix A: Complete Example Service

See section 5 for full production-ready `ClaudeQuestionQueue` implementation.

## Appendix B: Additional Resources

### Official Documentation

- **Anthropic API Docs:** https://docs.claude.com/
- **Python SDK GitHub:** https://github.com/anthropics/anthropic-sdk-python
- **Rate Limits:** https://docs.claude.com/en/api/rate-limits
- **Pricing:** https://www.anthropic.com/pricing

### Python Asyncio Resources

- **asyncio Queues:** https://docs.python.org/3/library/asyncio-queue.html
- **Semaphores:** https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
- **Coroutines:** https://docs.python.org/3/library/asyncio-task.html

### Rate Limiting Libraries

- **aiolimiter:** https://github.com/mjpieters/aiolimiter
- **tenacity:** https://github.com/jd/tenacity (retry logic)

---

## Appendix C: Configuration File Templates

### `config/settings.yaml` additions:

```yaml
# Claude API Configuration
claude:
  model: "claude-sonnet-4-5-20250929"
  timeout_sec: 10
  max_retries: 2
  max_tokens: 150
  temperature: 0.7

  # Queue settings
  max_queue_size: 100
  num_workers: 10
  max_concurrent_api_calls: 10

  # Rate limiting
  user_rate_limit_sec: 60

  # Response formatting
  max_response_chars: 450
  truncate_suffix: "..."
```

### `.env.example`:

```bash
# OBS WebSocket
OBS_WEBSOCKET_PASSWORD=your_password_here

# Twitch
TWITCH_STREAM_KEY=your_stream_key_here

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Claude API (NEW)
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx...
```

---

**End of Research Document**
