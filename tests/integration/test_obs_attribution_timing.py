"""Performance test for attribution update timing (T074a).

Validates SC-013: Attribution updates must complete in <1 second.
"""

import pytest
import time
import asyncio
from src.services.obs_attribution_updater import OBSAttributionUpdater
from src.config.settings import Settings


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.performance
@pytest.mark.asyncio
async def test_attribution_update_timing_sc013():
    """Test that attribution updates complete in <1 second (SC-013)."""
    try:
        settings = Settings()
        updater = OBSAttributionUpdater(settings.obs)

        await updater.ensure_text_source()

        # Measure single update time
        start = time.time()
        await updater.update_attribution(
            source_name="MIT OpenCourseWare 6.0001",
            title="What is Computation?",
            license_type="CC BY-NC-SA 4.0",
        )
        elapsed = time.time() - start

        # SC-013 requirement: <1 second
        assert elapsed < 1.0, f"Attribution update took {elapsed:.3f}s (exceeds 1s requirement)"

        print(f"\n✓ Attribution update completed in {elapsed * 1000:.1f}ms (SC-013: <1000ms)")

    except ConnectionRefusedError:
        pytest.skip("OBS not running or WebSocket not enabled")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.performance
@pytest.mark.asyncio
async def test_attribution_timing_percentiles():
    """Test attribution timing across multiple updates to get percentiles."""
    try:
        settings = Settings()
        updater = OBSAttributionUpdater(settings.obs)

        await updater.ensure_text_source()

        # Measure 100 updates
        times = []
        test_data = [
            ("MIT OCW", "Python Basics", "CC BY-NC-SA 4.0"),
            ("Harvard CS50", "Introduction to CS", "CC BY-NC-SA 4.0"),
            ("Khan Academy", "JavaScript Tutorial", "CC BY-NC-SA 3.0"),
            ("Blender Foundation", "Big Buck Bunny", "CC BY 3.0"),
        ]

        for i in range(100):
            source, title, license_type = test_data[i % len(test_data)]

            start = time.time()
            await updater.update_attribution(
                source_name=source,
                title=f"{title} #{i}",
                license_type=license_type,
            )
            times.append(time.time() - start)

        # Calculate percentiles
        times.sort()
        p50 = times[len(times) // 2]
        p95 = times[int(len(times) * 0.95)]
        p99 = times[int(len(times) * 0.99)]
        max_time = max(times)
        avg_time = sum(times) / len(times)

        print(f"\nAttribution Timing Statistics (n=100):")
        print(f"  Average: {avg_time * 1000:.1f}ms")
        print(f"  P50 (median): {p50 * 1000:.1f}ms")
        print(f"  P95: {p95 * 1000:.1f}ms")
        print(f"  P99: {p99 * 1000:.1f}ms")
        print(f"  Maximum: {max_time * 1000:.1f}ms")

        # All updates should meet SC-013
        assert max_time < 1.0, f"Slowest update took {max_time * 1000:.0f}ms (exceeds 1s)"
        assert p95 < 0.5, f"95th percentile at {p95 * 1000:.0f}ms (should be well under 1s)"

    except ConnectionRefusedError:
        pytest.skip("OBS not running or WebSocket not enabled")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.performance
@pytest.mark.asyncio
async def test_attribution_timing_under_load():
    """Test attribution timing with concurrent updates."""
    try:
        settings = Settings()
        updater = OBSAttributionUpdater(settings.obs)

        await updater.ensure_text_source()

        # Run 10 updates concurrently
        async def single_update(i):
            start = time.time()
            await updater.update_attribution(
                source_name=f"Source {i}",
                title=f"Title {i}",
                license_type="CC BY 4.0",
            )
            return time.time() - start

        # Launch concurrent updates
        start_all = time.time()
        times = await asyncio.gather(*[single_update(i) for i in range(10)])
        total_elapsed = time.time() - start_all

        # Individual updates should still be fast
        max_individual = max(times)
        assert max_individual < 1.0, f"Update under load took {max_individual * 1000:.0f}ms"

        print(f"\nConcurrent Attribution Updates:")
        print(f"  10 updates completed in {total_elapsed * 1000:.1f}ms")
        print(f"  Slowest individual update: {max_individual * 1000:.1f}ms")

    except ConnectionRefusedError:
        pytest.skip("OBS not running or WebSocket not enabled")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.performance
@pytest.mark.asyncio
async def test_attribution_cold_start_timing():
    """Test attribution timing on first update (cold start)."""
    try:
        settings = Settings()
        updater = OBSAttributionUpdater(settings.obs)

        # Measure cold start (includes ensure_text_source)
        start = time.time()
        await updater.ensure_text_source()
        await updater.update_attribution(
            source_name="Test Source",
            title="Cold Start Test",
            license_type="CC BY 4.0",
        )
        cold_start_time = time.time() - start

        # Measure warm update
        start = time.time()
        await updater.update_attribution(
            source_name="Test Source 2",
            title="Warm Update Test",
            license_type="CC BY 4.0",
        )
        warm_update_time = time.time() - start

        print(f"\nAttribution Timing Analysis:")
        print(f"  Cold start (first update): {cold_start_time * 1000:.1f}ms")
        print(f"  Warm update (subsequent): {warm_update_time * 1000:.1f}ms")

        # Even cold start should be reasonable
        assert cold_start_time < 2.0, f"Cold start took {cold_start_time * 1000:.0f}ms (too slow)"
        assert warm_update_time < 1.0, f"Warm update took {warm_update_time * 1000:.0f}ms"

    except ConnectionRefusedError:
        pytest.skip("OBS not running or WebSocket not enabled")
