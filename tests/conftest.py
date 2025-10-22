"""Pytest configuration and shared fixtures for OBS_bot tests.

Provides common fixtures for async testing, settings, and test database.
"""

import asyncio
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from src.config.settings import Settings, OBSSettings
from src.persistence.db import Database


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests.

    Provides session-scoped event loop for pytest-asyncio.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with safe defaults.

    Returns:
        Settings instance with test configuration
    """
    import os

    # Load from environment or use test defaults
    obs = OBSSettings(
        websocket_url=os.getenv("OBS_WEBSOCKET_URL", "ws://localhost:4455"),
        password=os.getenv("OBS_WEBSOCKET_PASSWORD", ""),
        connection_timeout_sec=10,
        reconnect_interval_sec=2,
        max_reconnect_attempts=3,
    )

    # Create minimal settings for testing
    # Note: Full Settings requires YAML loading, so we'll just use OBS settings
    # for integration tests. Unit tests can mock as needed.
    return obs


@pytest_asyncio.fixture
async def test_database(tmp_path: Path) -> AsyncGenerator[Database, None]:
    """Create temporary test database.

    Args:
        tmp_path: Pytest temporary directory

    Yields:
        Connected test database instance

    Teardown:
        Disconnects and removes test database
    """
    db_path = tmp_path / "test_obs_bot.db"
    db = Database(db_path)
    await db.connect()

    yield db

    await db.disconnect()
    # Database file auto-removed by tmp_path cleanup


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Configure logging for tests.

    Auto-used for all tests to ensure clean log output.
    """
    from src.config.logging import configure_logging

    configure_logging(level="DEBUG", log_format="text")


# Markers for test categorization
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (requires OBS running)")
    config.addinivalue_line("markers", "contract: Contract tests (API endpoint validation)")
    config.addinivalue_line("markers", "slow: Slow-running tests (streaming, long operations)")
