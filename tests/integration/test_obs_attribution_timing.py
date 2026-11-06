"""Performance test for attribution update timing (T074a).

Validates SC-013: Attribution updates must complete in <1 second.
Needs a live OBS, so every test here is marked requires_obs and is left out of CI.
The ``attribution_updater`` fixture (conftest.py) connects and makes the text source
if it is missing.
"""

import asyncio
import time

import pytest

from src.models.content_library import SourceAttribution
from src.services.obs_attribution_updater import OBSAttributionUpdater


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.performance
@pytest.mark.asyncio
async def test_attribution_update_timing_sc013(attribution_updater, make_content):
    """Test that attribution updates complete in <1 second (SC-013)."""
    content = make_content(title="What is Computation?", source=SourceAttribution.MIT_OCW)

    # Measure single update time
    start = time.time()
    await attribution_updater.update_attribution(content)
    elapsed = time.time() - start

    # SC-013 requirement: <1 second
    assert elapsed < 1.0, f"Attribution update took {elapsed:.3f}s (exceeds 1s requirement)"

    print(f"\n✓ Attribution update completed in {elapsed * 1000:.1f}ms (SC-013: <1000ms)")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.performance
@pytest.mark.asyncio
async def test_attribution_timing_percentiles(attribution_updater, make_content):
    """Test attribution timing across multiple updates to get percentiles."""
    times = []
    test_data = [
        (SourceAttribution.MIT_OCW, "Python Basics", "CC BY-NC-SA 4.0"),
        (SourceAttribution.CS50, "Introduction to CS", "CC BY-NC-SA 4.0"),
        (SourceAttribution.KHAN_ACADEMY, "JavaScript Tutorial", "CC BY-NC-SA"),
        (SourceAttribution.BLENDER, "Big Buck Bunny", "CC BY 3.0"),
    ]

    # Measure 100 updates
    for i in range(100):
        source, title, license_type = test_data[i % len(test_data)]
        content = make_content(title=f"{title} #{i}", license_type=license_type, source=source)

        start = time.time()
        await attribution_updater.update_attribution(content)
        times.append(time.time() - start)

    # Calculate percentiles
    times.sort()
    p50 = times[len(times) // 2]
    p95 = times[int(len(times) * 0.95)]
    p99 = times[int(len(times) * 0.99)]
    max_time = max(times)
    avg_time = sum(times) / len(times)

    print("\nAttribution Timing Statistics (n=100):")
    print(f"  Average: {avg_time * 1000:.1f}ms")
    print(f"  P50 (median): {p50 * 1000:.1f}ms")
    print(f"  P95: {p95 * 1000:.1f}ms")
    print(f"  P99: {p99 * 1000:.1f}ms")
    print(f"  Maximum: {max_time * 1000:.1f}ms")

    # All updates should meet SC-013
    assert max_time < 1.0, f"Slowest update took {max_time * 1000:.0f}ms (exceeds 1s)"
    assert p95 < 0.5, f"95th percentile at {p95 * 1000:.0f}ms (should be well under 1s)"


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.performance
@pytest.mark.asyncio
async def test_attribution_timing_under_load(attribution_updater, make_content):
    """Test attribution timing with concurrent updates."""

    # Run 10 updates concurrently
    async def single_update(i):
        start = time.time()
        await attribution_updater.update_attribution(
            make_content(title=f"Title {i}", license_type="CC BY 4.0")
        )
        return time.time() - start

    # Launch concurrent updates
    start_all = time.time()
    times = await asyncio.gather(*[single_update(i) for i in range(10)])
    total_elapsed = time.time() - start_all

    # Individual updates should still be fast
    max_individual = max(times)
    assert max_individual < 1.0, f"Update under load took {max_individual * 1000:.0f}ms"

    print("\nConcurrent Attribution Updates:")
    print(f"  10 updates completed in {total_elapsed * 1000:.1f}ms")
    print(f"  Slowest individual update: {max_individual * 1000:.1f}ms")


@pytest.mark.integration
@pytest.mark.requires_obs
@pytest.mark.performance
@pytest.mark.asyncio
async def test_attribution_cold_start_timing(live_obs, make_content):
    """Test attribution timing on first update (cold start)."""
    updater = OBSAttributionUpdater(live_obs)

    # Measure cold start (includes checking the text source is there)
    start = time.time()
    assert await updater.verify_text_source_exists(), "No 'Content Attribution' text source in OBS"
    await updater.update_attribution(make_content(title="Cold Start Test", license_type="CC BY 4.0"))
    cold_start_time = time.time() - start

    # Measure warm update
    start = time.time()
    await updater.update_attribution(make_content(title="Warm Update Test", license_type="CC BY 4.0"))
    warm_update_time = time.time() - start

    await updater.clear_attribution()

    print("\nAttribution Timing Analysis:")
    print(f"  Cold start (first update): {cold_start_time * 1000:.1f}ms")
    print(f"  Warm update (subsequent): {warm_update_time * 1000:.1f}ms")

    # Even cold start should be reasonable
    assert cold_start_time < 2.0, f"Cold start took {cold_start_time * 1000:.0f}ms (too slow)"
    assert warm_update_time < 1.0, f"Warm update took {warm_update_time * 1000:.0f}ms"
