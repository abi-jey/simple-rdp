#!/usr/bin/env python3
"""
FPS Limit Test for simple-rdp

Tests different target FPS rates to find the maximum sustainable rate.
Monitors memory usage to detect leaks.

Run with:
    python tests/e2e/test_fps_limits.py
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
from simple_rdp.display import Display  # noqa: E402


@dataclass
class FPSTestResult:
    """Result from testing a specific FPS target."""

    target_fps: int
    duration_seconds: float
    frames_captured: int
    actual_fps: float
    avg_capture_ms: float
    max_capture_ms: float
    memory_start_mb: float
    memory_end_mb: float
    memory_peak_mb: float
    buffer_delay_avg_ms: float
    success: bool
    error: str = ""


async def test_fps_rate(
    client: RDPClient,
    display: Display,
    target_fps: int,
    duration: float = 10.0,
) -> FPSTestResult:
    """Test a specific FPS rate and collect metrics."""

    print(f"\n{'=' * 60}")
    print(f"Testing target FPS: {target_fps}")
    print(f"{'=' * 60}")

    # Start memory tracking
    gc.collect()
    tracemalloc.start()
    memory_start = tracemalloc.get_traced_memory()[0] / (1024 * 1024)

    target_interval = 1.0 / target_fps
    frames = 0
    capture_times: list[float] = []
    buffer_delays: list[float] = []
    memory_samples: list[float] = []

    start_time = time.perf_counter()
    last_report = start_time

    try:
        while (time.perf_counter() - start_time) < duration:
            loop_start = time.perf_counter()

            # Capture screenshot
            t0 = time.perf_counter()
            screenshot = await client.screenshot()
            t1 = time.perf_counter()
            capture_times.append((t1 - t0) * 1000)

            # Add to display (raw frame storage)
            await display.add_frame(screenshot)
            frames += 1

            # Sample buffer delay
            buffer_delays.append(display.buffer_delay_seconds * 1000)

            # Periodic reporting and memory sampling
            if time.perf_counter() - last_report >= 2.0:
                current_mem = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
                memory_samples.append(current_mem)
                elapsed = time.perf_counter() - start_time
                current_fps = frames / elapsed
                print(
                    f"  [{elapsed:.1f}s] {frames} frames | "
                    f"FPS: {current_fps:.1f}/{target_fps} | "
                    f"Capture: {capture_times[-1]:.1f}ms | "
                    f"Buffer: {display.raw_frame_count} frames | "
                    f"Mem: {current_mem:.1f}MB | "
                    f"EffectiveFPS: {display.effective_fps:.1f}"
                )
                last_report = time.perf_counter()

            # Sleep for remainder of interval
            elapsed = time.perf_counter() - loop_start
            sleep_time = max(0, target_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        end_time = time.perf_counter()
        memory_end, memory_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        actual_fps = frames / (end_time - start_time)

        return FPSTestResult(
            target_fps=target_fps,
            duration_seconds=end_time - start_time,
            frames_captured=frames,
            actual_fps=actual_fps,
            avg_capture_ms=sum(capture_times) / len(capture_times) if capture_times else 0,
            max_capture_ms=max(capture_times) if capture_times else 0,
            memory_start_mb=memory_start,
            memory_end_mb=memory_end / (1024 * 1024),
            memory_peak_mb=memory_peak / (1024 * 1024),
            buffer_delay_avg_ms=sum(buffer_delays) / len(buffer_delays) if buffer_delays else 0,
            success=True,
        )

    except Exception as e:
        tracemalloc.stop()
        return FPSTestResult(
            target_fps=target_fps,
            duration_seconds=time.perf_counter() - start_time,
            frames_captured=frames,
            actual_fps=frames / max(0.1, time.perf_counter() - start_time),
            avg_capture_ms=sum(capture_times) / len(capture_times) if capture_times else 0,
            max_capture_ms=max(capture_times) if capture_times else 0,
            memory_start_mb=memory_start,
            memory_end_mb=0,
            memory_peak_mb=0,
            buffer_delay_avg_ms=0,
            success=False,
            error=str(e),
        )


async def test_with_encoding(
    client: RDPClient,
    display: Display,
    target_fps: int,
    duration: float = 15.0,
) -> FPSTestResult:
    """Test FPS with video encoding enabled."""

    print(f"\n{'=' * 60}")
    print(f"Testing FPS: {target_fps} WITH VIDEO ENCODING")
    print(f"{'=' * 60}")

    gc.collect()
    tracemalloc.start()
    memory_start = tracemalloc.get_traced_memory()[0] / (1024 * 1024)

    # Start encoding
    await display.start_encoding()

    target_interval = 1.0 / target_fps
    frames = 0
    capture_times: list[float] = []
    buffer_delays: list[float] = []

    start_time = time.perf_counter()
    last_report = start_time

    try:
        while (time.perf_counter() - start_time) < duration:
            loop_start = time.perf_counter()

            t0 = time.perf_counter()
            screenshot = await client.screenshot()
            t1 = time.perf_counter()
            capture_times.append((t1 - t0) * 1000)

            await display.add_frame(screenshot)
            frames += 1
            buffer_delays.append(display.buffer_delay_seconds * 1000)

            if time.perf_counter() - last_report >= 2.0:
                current_mem = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
                elapsed = time.perf_counter() - start_time
                current_fps = frames / elapsed
                print(
                    f"  [{elapsed:.1f}s] {frames} frames | "
                    f"FPS: {current_fps:.1f}/{target_fps} | "
                    f"VideoBuffer: {display.video_buffer_size_mb:.1f}MB | "
                    f"RecDuration: {display.recording_duration_seconds:.1f}s | "
                    f"Mem: {current_mem:.1f}MB"
                )
                last_report = time.perf_counter()

            elapsed = time.perf_counter() - loop_start
            sleep_time = max(0, target_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        end_time = time.perf_counter()

        # Stop encoding
        await display.stop_encoding()

        memory_end, memory_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        return FPSTestResult(
            target_fps=target_fps,
            duration_seconds=end_time - start_time,
            frames_captured=frames,
            actual_fps=frames / (end_time - start_time),
            avg_capture_ms=sum(capture_times) / len(capture_times) if capture_times else 0,
            max_capture_ms=max(capture_times) if capture_times else 0,
            memory_start_mb=memory_start,
            memory_end_mb=memory_end / (1024 * 1024),
            memory_peak_mb=memory_peak / (1024 * 1024),
            buffer_delay_avg_ms=sum(buffer_delays) / len(buffer_delays) if buffer_delays else 0,
            success=True,
        )

    except Exception as e:
        await display.stop_encoding()
        tracemalloc.stop()
        return FPSTestResult(
            target_fps=target_fps,
            duration_seconds=time.perf_counter() - start_time,
            frames_captured=frames,
            actual_fps=0,
            avg_capture_ms=0,
            max_capture_ms=0,
            memory_start_mb=memory_start,
            memory_end_mb=0,
            memory_peak_mb=0,
            buffer_delay_avg_ms=0,
            success=False,
            error=str(e),
        )


def print_results(results: list[FPSTestResult]) -> None:
    """Print a summary table of all results."""

    print("\n" + "=" * 100)
    print("                              FPS TEST RESULTS SUMMARY")
    print("=" * 100)
    print(
        f"{'Target':>8} | {'Actual':>8} | {'Frames':>8} | {'Avg(ms)':>8} | "
        f"{'Max(ms)':>8} | {'MemStart':>10} | {'MemEnd':>10} | {'MemPeak':>10} | {'Status':>8}"
    )
    print("-" * 100)

    for r in results:
        status = "✓ OK" if r.success else f"✗ {r.error[:20]}"
        print(
            f"{r.target_fps:>8} | {r.actual_fps:>7.1f} | {r.frames_captured:>8} | "
            f"{r.avg_capture_ms:>7.2f} | {r.max_capture_ms:>7.2f} | "
            f"{r.memory_start_mb:>9.1f}M | {r.memory_end_mb:>9.1f}M | "
            f"{r.memory_peak_mb:>9.1f}M | {status}"
        )

    print("=" * 100)

    # Find maximum sustainable FPS
    successful = [r for r in results if r.success and r.actual_fps >= r.target_fps * 0.9]
    if successful:
        best = max(successful, key=lambda r: r.actual_fps)
        print(f"\n🏆 Maximum sustainable FPS: {best.actual_fps:.1f} (target: {best.target_fps})")

    # Check for memory leaks
    if results:
        first = results[0]
        last = results[-1]
        mem_growth = last.memory_end_mb - first.memory_start_mb
        if mem_growth > 50:
            print(f"\n⚠️  Memory grew by {mem_growth:.1f}MB - possible leak!")
        else:
            print(f"\n✓ Memory stable (growth: {mem_growth:.1f}MB)")


async def main() -> None:
    host = os.environ.get("RDP_HOST", "192.168.1.243")
    user = os.environ.get("RDP_USER", "abja")
    password = os.environ.get("RDP_PASS", "changeme")

    print(f"Connecting to {host} as {user}...")

    client = RDPClient(host, username=user, password=password, width=1920, height=1080)

    try:
        await client.connect()
        print("Connected! Waiting for desktop...")
        await asyncio.sleep(3)

        display = Display(width=1920, height=1080, fps=60, max_raw_frames=500)
        display.initialize_screen()

        # Initialize with a frame
        initial = await client.screenshot()
        await display.add_frame(initial)

        results: list[FPSTestResult] = []

        # Test different FPS targets (without encoding first)
        test_fps_values = [10, 30, 60, 100, 150]

        for target_fps in test_fps_values:
            display.clear_raw_frames()
            gc.collect()
            result = await test_fps_rate(client, display, target_fps, duration=10.0)
            results.append(result)
            await asyncio.sleep(2)  # Cool-down

        # Now test with encoding
        print("\n\n" + "=" * 60)
        print("          TESTING WITH VIDEO ENCODING")
        print("=" * 60)

        encoding_results: list[FPSTestResult] = []
        for target_fps in [30, 60]:
            display.clear_raw_frames()
            display.clear_video_chunks()
            gc.collect()
            result = await test_with_encoding(client, display, target_fps, duration=15.0)
            encoding_results.append(result)
            await asyncio.sleep(2)

        # Print all results
        print("\n\n" + "#" * 100)
        print("                         RAW CAPTURE (NO ENCODING)")
        print("#" * 100)
        print_results(results)

        print("\n" + "#" * 100)
        print("                         WITH VIDEO ENCODING")
        print("#" * 100)
        print_results(encoding_results)

        # Print display stats
        print("\n")
        display.print_stats()

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
