#!/usr/bin/env python3
"""Graphics-Intensive RDP Performance Test with cProfile + snakeviz profiling.

Run this script, then visualize with:
    snakeviz sessions/graphics_XXXX/profile.prof
"""

import asyncio
import cProfile
import io
import os
import pstats
import sys
import time
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from simple_rdp import RDPClient  # noqa: E402


@dataclass
class PerformanceMetrics:
    """Performance tracking"""

    frames: list[tuple[float, bytes]] = field(default_factory=list)  # (timestamp, png_data)
    start_time: float = 0
    end_time: float = 0

    # Timing breakdowns
    screenshot_times: list[float] = field(default_factory=list)
    png_encode_times: list[float] = field(default_factory=list)

    @property
    def total_frames(self) -> int:
        return len(self.frames)

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0

    @property
    def avg_fps(self) -> float:
        return self.total_frames / self.duration_seconds if self.duration_seconds > 0 else 0

    @property
    def total_size_mb(self) -> float:
        return sum(len(d) for _, d in self.frames) / (1024 * 1024)


async def capture_at_10fps(client: RDPClient, metrics: PerformanceMetrics, stop_event: asyncio.Event):
    """Capture frames at exactly 10 FPS with detailed timing"""
    target_interval = 0.1  # 100ms = 10 FPS
    frame_count = 0

    while not stop_event.is_set():
        loop_start = time.perf_counter()

        try:
            # Time screenshot
            t0 = time.perf_counter()
            screenshot = await client.screenshot()
            t1 = time.perf_counter()
            metrics.screenshot_times.append(t1 - t0)

            # Time PNG encoding
            t2 = time.perf_counter()
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG", optimize=False)
            png_data = buffer.getvalue()
            t3 = time.perf_counter()
            metrics.png_encode_times.append(t3 - t2)

            metrics.frames.append((time.perf_counter(), png_data))
            frame_count += 1

            if frame_count % 50 == 0:
                avg_ss = sum(metrics.screenshot_times[-50:]) / 50 * 1000
                avg_png = sum(metrics.png_encode_times[-50:]) / 50 * 1000
                print(f"    [Capture] {frame_count} frames | screenshot: {avg_ss:.1f}ms, png: {avg_png:.1f}ms")

        except Exception as e:
            print(f"    [Capture Error] {e}")

        # Sleep for remainder of interval
        elapsed = time.perf_counter() - loop_start
        sleep_time = max(0, target_interval - elapsed)
        await asyncio.sleep(sleep_time)


async def graphic_intensive_actions(client: RDPClient, duration_seconds: int = 30):
    """Perform graphic-intensive UI actions every 0.5 seconds.
    Shorter duration for profiling.
    """
    print(f"\n=== Starting {duration_seconds}s of graphic-intensive actions ===\n")

    action_interval = 0.5  # 0.5 seconds between actions

    # Define a sequence of actions that create lots of visual changes
    actions = [
        # Open Task Manager: Ctrl+Shift+Escape
        (
            "Open Task Manager",
            [("ctrl", True), ("shift", True), ("escape", True)],
            [("escape", False), ("shift", False), ("ctrl", False)],
        ),
        # Wait and close: Alt+F4
        ("Close Window", [("alt", True), ("f4", True)], [("f4", False), ("alt", False)]),
        # Open Windows Search: Windows key
        ("Open Search", [("win", True)], [("win", False)]),
        # Close search: Escape
        ("Close Search", [("escape", True)], [("escape", False)]),
        # Open Run dialog: Win+R
        ("Open Run", [("win", True), ("r", True)], [("r", False), ("win", False)]),
        # Close Run: Escape
        ("Close Run", [("escape", True)], [("escape", False)]),
        # Open Settings: Win+I
        ("Open Settings", [("win", True), ("i", True)], [("i", False), ("win", False)]),
        # Close Settings: Alt+F4
        ("Close Settings", [("alt", True), ("f4", True)], [("f4", False), ("alt", False)]),
        # Open Explorer: Win+E
        ("Open Explorer", [("win", True), ("e", True)], [("e", False), ("win", False)]),
        # Close Explorer: Alt+F4
        ("Close Explorer", [("alt", True), ("f4", True)], [("f4", False), ("alt", False)]),
        # Show Desktop: Win+D
        ("Show Desktop", [("win", True), ("d", True)], [("d", False), ("win", False)]),
        # Restore Desktop: Win+D again
        ("Restore Desktop", [("win", True), ("d", True)], [("d", False), ("win", False)]),
    ]

    # Scancode mapping
    scancodes = {
        "escape": (0x01, False),
        "tab": (0x0F, False),
        "a": (0x1E, False),
        "d": (0x20, False),
        "e": (0x12, False),
        "f4": (0x3E, False),
        "i": (0x17, False),
        "r": (0x13, False),
        "ctrl": (0x1D, False),
        "shift": (0x2A, False),
        "alt": (0x38, False),
        "win": (0x5B, True),  # Extended key
    }

    start_time = time.time()
    action_count = 0
    action_idx = 0

    while (time.time() - start_time) < duration_seconds:
        action_name, press_keys, release_keys = actions[action_idx]
        action_idx = (action_idx + 1) % len(actions)
        action_count += 1

        elapsed = time.time() - start_time
        print(f"  [{elapsed:5.1f}s] Action {action_count}: {action_name}")

        try:
            # Press keys
            for key, is_press in press_keys:
                scancode, extended = scancodes.get(key, (0, False))
                await client.send_key(scancode, is_press=is_press, is_release=False)
                await asyncio.sleep(0.02)

            # Small delay
            await asyncio.sleep(0.05)

            # Release keys
            for key, is_release in release_keys:
                scancode, extended = scancodes.get(key, (0, False))
                await client.send_key(scancode, is_press=False, is_release=is_release)
                await asyncio.sleep(0.02)

        except Exception as e:
            print(f"    [Action Error] {e}")

        # Wait for next action
        await asyncio.sleep(action_interval)

    print(f"\n=== Completed {action_count} actions in {duration_seconds}s ===\n")


def print_timing_stats(metrics: PerformanceMetrics):
    """Print detailed timing breakdown"""
    print("\n" + "=" * 60)
    print("              TIMING BREAKDOWN")
    print("=" * 60)

    if metrics.screenshot_times:
        ss_times = metrics.screenshot_times
        print(f"\n📷 SCREENSHOT TIMING ({len(ss_times)} samples):")
        print(f"   Average:    {sum(ss_times) / len(ss_times) * 1000:.2f} ms")
        print(f"   Min:        {min(ss_times) * 1000:.2f} ms")
        print(f"   Max:        {max(ss_times) * 1000:.2f} ms")
        print(f"   Total:      {sum(ss_times):.2f} s")

    if metrics.png_encode_times:
        png_times = metrics.png_encode_times
        print(f"\n🖼️  PNG ENCODING ({len(png_times)} samples):")
        print(f"   Average:    {sum(png_times) / len(png_times) * 1000:.2f} ms")
        print(f"   Min:        {min(png_times) * 1000:.2f} ms")
        print(f"   Max:        {max(png_times) * 1000:.2f} ms")
        print(f"   Total:      {sum(png_times):.2f} s")

    if metrics.screenshot_times and metrics.png_encode_times:
        total_ss = sum(metrics.screenshot_times)
        total_png = sum(metrics.png_encode_times)
        total_capture = total_ss + total_png
        print("\n⏱️  CAPTURE TIME DISTRIBUTION:")
        print(f"   Screenshot:  {total_ss / total_capture * 100:.1f}% ({total_ss:.2f}s)")
        print(f"   PNG encode:  {total_png / total_capture * 100:.1f}% ({total_png:.2f}s)")


async def run_test(session_dir: str, duration: int):
    """Main test logic to be profiled"""
    host = os.environ.get("RDP_HOST", "")
    username = os.environ.get("RDP_USER", "")
    password = os.environ.get("RDP_PASS", "")

    if not host or not username or not password:
        print("ERROR: Set RDP_HOST, RDP_USER, RDP_PASS environment variables (or use .env file)")
        return None

    metrics = PerformanceMetrics()
    stop_capture = asyncio.Event()

    print(f"\nConnecting to {host} as {username}...")

    client = RDPClient(host, username=username, password=password, width=1920, height=1080, show_wallpaper=True)

    try:
        await client.connect()
        print("Connected! Waiting for initial screen...")
        await asyncio.sleep(2)

        # Start capture at 10 FPS
        print("\nStarting 10 FPS capture...")
        metrics.start_time = time.perf_counter()
        capture_task = asyncio.create_task(capture_at_10fps(client, metrics, stop_capture))

        await asyncio.sleep(0.5)

        # Run graphic-intensive actions
        await graphic_intensive_actions(client, duration_seconds=duration)

        # Stop capture
        print("\nStopping capture...")
        stop_capture.set()
        await capture_task
        metrics.end_time = time.perf_counter()

        print(f"\nCapture complete: {metrics.total_frames} frames in {metrics.duration_seconds:.1f}s")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        stop_capture.set()
        metrics.end_time = time.perf_counter()
    finally:
        await client.disconnect()

    return metrics


def main():
    duration = int(os.environ.get("DURATION", "30"))  # Shorter default for profiling

    # Create session directory
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(os.path.dirname(__file__), "sessions", f"profile_{session_id}")
    os.makedirs(session_dir, exist_ok=True)

    profile_path = os.path.join(session_dir, "profile.prof")

    print("=" * 60)
    print("     GRAPHICS TEST WITH cProfile + SNAKEVIZ")
    print("=" * 60)
    print(f"\nSession directory: {session_dir}")
    print(f"Test duration: {duration} seconds")
    print(f"Profile output: {profile_path}")

    # Create profiler
    profiler = cProfile.Profile()

    # Run the test with profiling
    print("\n[Starting profiled test run...]")
    profiler.enable()

    metrics = asyncio.run(run_test(session_dir, duration))

    profiler.disable()
    print("[Profiling complete]")

    # Save profile data
    profiler.dump_stats(profile_path)
    print(f"\nProfile saved to: {profile_path}")

    # Print timing breakdown
    if metrics:
        print_timing_stats(metrics)

        print("\n" + "=" * 60)
        print("              PERFORMANCE SUMMARY")
        print("=" * 60)
        print(f"\n📊 Total frames:    {metrics.total_frames}")
        print(f"   Duration:        {metrics.duration_seconds:.1f}s")
        print(f"   Average FPS:     {metrics.avg_fps:.2f}")
        print(f"   Total PNG data:  {metrics.total_size_mb:.2f} MB")

    # Print top 20 functions by cumulative time
    print("\n" + "=" * 60)
    print("         TOP 20 FUNCTIONS BY CUMULATIVE TIME")
    print("=" * 60 + "\n")
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    stats.print_stats(20)

    print("\n" + "=" * 60)
    print("         VIEW FULL PROFILE WITH SNAKEVIZ")
    print("=" * 60)
    print("\nRun this command to visualize:")
    print(f"  snakeviz {profile_path}")
    print()

    return profile_path


if __name__ == "__main__":
    profile_path = main()
