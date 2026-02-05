#!/usr/bin/env python3
"""
FPS Limit Test for simple-rdp (New Architecture)

Tests different target FPS rates to find the maximum sustainable rate.
Monitors memory usage to detect leaks in the new streaming pipeline.
"""

import asyncio
import gc
import os
import sys
import time
import tracemalloc
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from simple_rdp import RDPClient  # noqa: E402


@dataclass
class FPSTestResult:
    """Result from testing a specific FPS target."""

    target_fps: int
    duration_seconds: float
    frames_captured: int
    frames_encoded: int
    actual_capture_fps: float
    actual_encode_fps: float
    memory_start_mb: float
    memory_end_mb: float
    memory_peak_mb: float
    avg_lag_chunks: float
    success: bool
    error: str = ""


async def test_streaming_fps(
    client: RDPClient,
    target_fps: int,
    duration: float = 15.0,
) -> FPSTestResult:
    """Test FPS with video encoding enabled."""

    print(f"\n{'=' * 60}")
    print(f"Testing FPS: {target_fps} WITH VIDEO ENCODING")
    print(f"{'=' * 60}")

    # Re-configure display with new target FPS
    # We need to hackily update the private display instance or re-create client
    # Since client owns display, we'll just update the existing display's fps attribute
    # and restart streaming.

    if client.is_streaming:
        await client.display.stop_streaming()

    # Update FPS
    client.display._fps = target_fps
    client.display._pointer_update_interval = 1.0 / target_fps

    gc.collect()
    tracemalloc.start()
    memory_start = tracemalloc.get_traced_memory()[0] / (1024 * 1024)

    # Start streaming
    await client.display.start_streaming()

    # Reset stats
    client.display._stats["frames_received"] = 0
    client.display._stats["frames_encoded"] = 0
    client.display._first_frame_time = None

    start_time = time.perf_counter()
    last_report = start_time

    lag_samples = []

    try:
        # Simulate a capture loop (since RDPClient has its own, we'll just run UI actions
        # and let the background capture loop do its work. But wait!
        # RDPClient's capture loop runs at `client.capture_fps`.
        # We can't easily change that on the fly without restarting the client.
        # So we will just measure what we get.

        # NOTE: Changing target_fps dynamically on RDPClient is tricky because the capture loop
        # is already running. For this test, we will assume the client was initialized
        # with a high enough FPS, or we should re-create the client.
        # But re-creating client is slow.
        # Let's just update the capture loop delay if possible, or accept this limitation.
        # Actually, let's inject frames manually to test the DISPLAY pipeline speed,
        # ignoring the RDPClient capture loop.

        frames_in = 0
        target_interval = 1.0 / target_fps

        while (time.perf_counter() - start_time) < duration:
            loop_start = time.perf_counter()

            # Inject a frame directly to display to test ITS limits
            # (We use the current screen buffer)
            if client.display._raw_display_image:
                await client.display.add_frame(client.display._raw_display_image)
                frames_in += 1

            # Sample lag
            lag = client.display.consumer_lag_chunks
            lag_samples.append(lag)

            # Consume chunks to prevent queue filling up
            while not client.display._video_queue.empty():
                client.display._video_queue.get_nowait()

            # Periodic reporting
            if time.perf_counter() - last_report >= 2.0:
                current_mem = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
                elapsed = time.perf_counter() - start_time
                stats = client.display.stats

                print(
                    f"  [{elapsed:.1f}s] In: {frames_in} | Enc: {stats['frames_encoded']} | "
                    f"Lag: {lag} | Mem: {current_mem:.1f}MB"
                )
                last_report = time.perf_counter()

            elapsed = time.perf_counter() - loop_start
            sleep_time = max(0, target_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        end_time = time.perf_counter()

        # Stop streaming
        await client.display.stop_streaming()

        memory_end, memory_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        stats = client.display.stats
        total_time = end_time - start_time

        return FPSTestResult(
            target_fps=target_fps,
            duration_seconds=total_time,
            frames_captured=frames_in,
            frames_encoded=stats["frames_encoded"],
            actual_capture_fps=frames_in / total_time,
            actual_encode_fps=stats["frames_encoded"] / total_time,
            memory_start_mb=memory_start,
            memory_end_mb=memory_end / (1024 * 1024),
            memory_peak_mb=memory_peak / (1024 * 1024),
            avg_lag_chunks=sum(lag_samples) / len(lag_samples) if lag_samples else 0,
            success=True,
        )

    except Exception as e:
        await client.display.stop_streaming()
        tracemalloc.stop()
        return FPSTestResult(
            target_fps=target_fps,
            duration_seconds=0,
            frames_captured=0,
            frames_encoded=0,
            actual_capture_fps=0,
            actual_encode_fps=0,
            memory_start_mb=0,
            memory_end_mb=0,
            memory_peak_mb=0,
            avg_lag_chunks=0,
            success=False,
            error=str(e),
        )


def print_results(results: list[FPSTestResult]) -> None:
    """Print a summary table of all results."""

    print("\n" + "=" * 100)
    print("                              FPS TEST RESULTS SUMMARY")
    print("=" * 100)
    print(
        f"{'Target':>8} | {'CapFPS':>8} | {'EncFPS':>8} | {'Lag(avg)':>8} | "
        f"{'MemStart':>10} | {'MemEnd':>10} | {'MemPeak':>10} | {'Status':>8}"
    )
    print("-" * 100)

    for r in results:
        status = "✓ OK" if r.success else f"✗ {r.error[:20]}"
        print(
            f"{r.target_fps:>8} | {r.actual_capture_fps:>8.1f} | {r.actual_encode_fps:>8.1f} | "
            f"{r.avg_lag_chunks:>8.1f} | "
            f"{r.memory_start_mb:>9.1f}M | {r.memory_end_mb:>9.1f}M | "
            f"{r.memory_peak_mb:>9.1f}M | {status}"
        )

    print("=" * 100)


async def main() -> None:
    host = os.environ.get("RDP_HOST", "")
    user = os.environ.get("RDP_USER", "")
    password = os.environ.get("RDP_PASS", "")

    if not host:
        print("Skipping test: RDP_HOST not set")
        return

    print(f"Connecting to {host} as {user}...")

    # We set a low capture_fps on the client itself because we will be driving
    # the display.add_frame manually to stress test the pipeline at different rates.
    client = RDPClient(host, username=user, password=password, width=1920, height=1080, capture_fps=1)

    try:
        await client.connect()
        print("Connected! Waiting for desktop...")
        await asyncio.sleep(2)

        # Pause the client's internal capture task to avoid interference
        if client._capture_task:
            client._capture_task.cancel()

        encoding_results: list[FPSTestResult] = []

        # Test 30 and 60 FPS
        for target_fps in [30, 60]:
            result = await test_streaming_fps(client, target_fps, duration=10.0)
            encoding_results.append(result)
            await asyncio.sleep(2)

        print_results(encoding_results)

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
