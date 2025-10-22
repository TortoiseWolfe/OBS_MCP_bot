# Tier 1 OBS Streaming Foundation - Production Container
# Python 3.11+ required for asyncio improvements and performance

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# ffmpeg includes ffprobe for video metadata extraction (Tier 3)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY tests/ ./tests/
COPY pytest.ini .

# Create directories for runtime data
RUN mkdir -p /app/data /app/logs /app/content

# Set Python path
ENV PYTHONPATH=/app

# Health check (uses health API endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run as non-root user for security
RUN useradd -m -u 1000 obsbot && \
    chown -R obsbot:obsbot /app
USER obsbot

# Default command (can be overridden in docker-compose.yml)
CMD ["python", "-m", "src.main"]
