#!/usr/bin/env python3
"""
Graphics Test with Display class - Raw frames + Live ffmpeg encoding.

Uses the new Display class which:
- Stores raw RGB frames (no PNG encoding overhead)
- Runs ffmpeg in background for live video encoding
- Maintains 100MB video output buffer with auto-eviction

Run with:
    export RDP_HOST=... RDP_USER=... RDP_PASS=... DURATION=30
    python example_display_profiled.py

Then visualize with:
    snakeviz sessions/display_XXXX/profile.prof
"""

import asyncio
import cProfile
import os
import pstats
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from simple_rdp import RDPClient  # noqa: E402
from simple_rdp.display import Display  # noqa: E402


class PerformanceTracker:
    """Track performance metrics during capture."""

    def __init__(self):
        self.screenshot_times: list[float] = []
        self.add_frame_times: list[float] = []
        self.start_time: float = 0
        self.end_time: float = 0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0

    def avg_ms(self, times: list[float]) -> float:
        return sum(times) / len(times) * 1000 if times else 0

    def print_stats(self):
        print(f"\n{'=' * 60}")
        print("           TIMING BREAKDOWN")
        print(f"{'=' * 60}")

        if self.screenshot_times:
            print(f"\n📷 SCREENSHOT ({len(self.screenshot_times)} samples):")
            print(f"   Average:  {self.avg_ms(self.screenshot_times):.2f} ms")
            print(f"   Min:      {min(self.screenshot_times) * 1000:.2f} ms")
            print(f"   Max:      {max(self.screenshot_times) * 1000:.2f} ms")
            print(f"   Total:    {sum(self.screenshot_times):.2f} s")

        if self.add_frame_times:
            print(f"\n🖼️  ADD FRAME (raw bytes + ffmpeg write) ({len(self.add_frame_times)} samples):")
            print(f"   Average:  {self.avg_ms(self.add_frame_times):.2f} ms")
            print(f"   Min:      {min(self.add_frame_times) * 1000:.2f} ms")
            print(f"   Max:      {max(self.add_frame_times) * 1000:.2f} ms")
            print(f"   Total:    {sum(self.add_frame_times):.2f} s")

        if self.screenshot_times and self.add_frame_times:
            total_ss = sum(self.screenshot_times)
            total_add = sum(self.add_frame_times)
            total = total_ss + total_add
            print("\n⏱️  TIME DISTRIBUTION:")
            print(f"   Screenshot:  {total_ss / total * 100:.1f}% ({total_ss:.2f}s)")
            print(f"   Add frame:   {total_add / total * 100:.1f}% ({total_add:.2f}s)")


async def capture_loop(
    client: RDPClient,
    display: Display,
    tracker: PerformanceTracker,
    stop_event: asyncio.Event,
    target_fps: int = 30,
):
    """
    Capture frames at target FPS using raw frame storage.

    This is MUCH faster than PNG encoding because:
    - image.tobytes() takes ~1-2ms vs PNG encoding ~150-200ms
    - ffmpeg encoding happens in separate process
    """
    target_interval = 1.0 / target_fps
    frame_count = 0

    while not stop_event.is_set():
        loop_start = time.perf_counter()

        try:
            # Get screenshot (just a buffer copy - very fast)
            t0 = time.perf_counter()
            screenshot = await client.screenshot()
            t1 = time.perf_counter()
            tracker.screenshot_times.append(t1 - t0)

            # Add to display (converts to raw bytes + sends to ffmpeg)
            t2 = time.perf_counter()
            await display.add_frame(screenshot)
            t3 = time.perf_counter()
            tracker.add_frame_times.append(t3 - t2)

            frame_count += 1

            if frame_count % 100 == 0:
                avg_ss = tracker.avg_ms(tracker.screenshot_times[-100:])
                avg_add = tracker.avg_ms(tracker.add_frame_times[-100:])
                print(
                    f"    [Capture] {frame_count} frames | "
                    f"screenshot: {avg_ss:.1f}ms, add_frame: {avg_add:.1f}ms | "
                    f"video buf: {display.video_buffer_size_mb:.1f}MB"
                )

        except Exception as e:
            print(f"    [Capture Error] {e}")

        # Sleep for remainder of interval
        elapsed = time.perf_counter() - loop_start
        sleep_time = max(0, target_interval - elapsed)
        await asyncio.sleep(sleep_time)


async def ui_actions(client: RDPClient, duration_seconds: int = 30):
    """
    Perform UI actions to generate screen changes.
    Faster action interval since capture is now faster.
    """
    print(f"\n=== Starting {duration_seconds}s of UI actions ===\n")

    action_interval = 0.3  # Faster: 0.3s between actions

    actions = [
        (
            "Open Task Manager",
            [("ctrl", True), ("shift", True), ("escape", True)],
            [("escape", False), ("shift", False), ("ctrl", False)],
        ),
        ("Close Window", [("alt", True), ("f4", True)], [("f4", False), ("alt", False)]),
        ("Open Search", [("win", True)], [("win", False)]),
        ("Close Search", [("escape", True)], [("escape", False)]),
        ("Open Run", [("win", True), ("r", True)], [("r", False), ("win", False)]),
        ("Close Run", [("escape", True)], [("escape", False)]),
        ("Open Settings", [("win", True), ("i", True)], [("i", False), ("win", False)]),
        ("Close Settings", [("alt", True), ("f4", True)], [("f4", False), ("alt", False)]),
        ("Open Explorer", [("win", True), ("e", True)], [("e", False), ("win", False)]),
        ("Close Explorer", [("alt", True), ("f4", True)], [("f4", False), ("alt", False)]),
        ("Show Desktop", [("win", True), ("d", True)], [("d", False), ("win", False)]),
        ("Restore Desktop", [("win", True), ("d", True)], [("d", False), ("win", False)]),
    ]

    scancodes = {
        "escape": 0x01,
        "f4": 0x3E,
        "ctrl": 0x1D,
        "shift": 0x2A,
        "alt": 0x38,
        "win": 0x5B,
        "r": 0x13,
        "i": 0x17,
        "e": 0x12,
        "d": 0x20,
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
            for key, _ in press_keys:
                scancode = scancodes.get(key, 0)
                await client.send_key(scancode, is_press=True, is_release=False)
                await asyncio.sleep(0.015)

            await asyncio.sleep(0.03)

            for key, _ in release_keys:
                scancode = scancodes.get(key, 0)
                await client.send_key(scancode, is_press=False, is_release=True)
                await asyncio.sleep(0.015)

        except Exception as e:
            print(f"    [Action Error] {e}")

        await asyncio.sleep(action_interval)

    print(f"\n=== Completed {action_count} actions in {duration_seconds}s ===\n")


async def run_test(session_dir: str, duration: int, target_fps: int):
    """Main test logic."""
    host = os.environ.get("RDP_HOST", "")
    username = os.environ.get("RDP_USER", "")
    password = os.environ.get("RDP_PASS", "")

    if not host or not username or not password:
        print("ERROR: Set RDP_HOST, RDP_USER, RDP_PASS environment variables (or use .env file)")
        return None, None

    # Create display with 100MB video buffer limit
    display = Display(
        width=1920,
        height=1080,
        fps=target_fps,
        max_video_buffer_mb=100,
        max_raw_frames=500,  # Keep last 500 raw frames
    )

    tracker = PerformanceTracker()
    stop_capture = asyncio.Event()

    print(f"\nConnecting to {host} as {username}...")

    client = RDPClient(host, username=username, password=password, width=1920, height=1080, show_wallpaper=True)

    try:
        await client.connect()
        print("Connected! Waiting for initial screen...")
        await asyncio.sleep(2)

        # Start ffmpeg encoding
        print(f"\nStarting ffmpeg live encoding at {target_fps} FPS...")
        await display.start_encoding()

        # Start capture
        print(f"Starting {target_fps} FPS capture with raw frames...")
        tracker.start_time = time.perf_counter()
        capture_task = asyncio.create_task(capture_loop(client, display, tracker, stop_capture, target_fps))

        await asyncio.sleep(0.5)

        # Run UI actions
        await ui_actions(client, duration_seconds=duration)

        # Stop capture
        print("\nStopping capture...")
        stop_capture.set()
        await capture_task
        tracker.end_time = time.perf_counter()

        # Stop encoding
        await display.stop_encoding()

        print(f"\nCapture complete: {display.frame_count} frames in {tracker.duration:.1f}s")
        print(f"Actual FPS: {display.frame_count / tracker.duration:.2f}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        stop_capture.set()
        tracker.end_time = time.perf_counter()
    finally:
        await display.stop_encoding()
        await client.disconnect()

    return display, tracker


def main():
    duration = int(os.environ.get("DURATION", "30"))
    target_fps = int(os.environ.get("TARGET_FPS", "30"))  # Higher FPS now possible!

    # Create session directory
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(os.path.dirname(__file__), "sessions", f"display_{session_id}")
    os.makedirs(session_dir, exist_ok=True)

    profile_path = os.path.join(session_dir, "profile.prof")
    video_path = os.path.join(session_dir, "recording.ts")

    print("=" * 60)
    print("     DISPLAY CLASS TEST with cProfile + SNAKEVIZ")
    print("=" * 60)
    print(f"\nSession directory: {session_dir}")
    print(f"Test duration: {duration} seconds")
    print(f"Target FPS: {target_fps}")
    print(f"Profile output: {profile_path}")

    # Create profiler
    profiler = cProfile.Profile()

    # Run the test with profiling
    print("\n[Starting profiled test run...]")
    profiler.enable()

    display, tracker = asyncio.run(run_test(session_dir, duration, target_fps))

    profiler.disable()
    print("[Profiling complete]")

    # Save profile data
    profiler.dump_stats(profile_path)
    print(f"\nProfile saved to: {profile_path}")

    if display and tracker:
        # Print timing stats
        tracker.print_stats()

        # Print display stats
        display.print_stats()

        # Save video from buffer
        if display.video_buffer_size_mb > 0:
            print(f"\nSaving video buffer to {video_path}...")
            asyncio.run(display.save_video(video_path))
            video_size = os.path.getsize(video_path) / (1024 * 1024)
            print(f"Video saved: {video_size:.2f} MB")

        # Also save from raw frames as MP4
        raw_video_path = os.path.join(session_dir, "recording_raw.mp4")
        print(f"\nEncoding raw frames to {raw_video_path}...")
        asyncio.run(display.save_raw_frames_as_video(raw_video_path, fps=target_fps))
        if os.path.exists(raw_video_path):
            raw_video_size = os.path.getsize(raw_video_path) / (1024 * 1024)
            print(f"Raw frames video: {raw_video_size:.2f} MB")

        # Performance summary
        print("\n" + "=" * 60)
        print("              PERFORMANCE SUMMARY")
        print("=" * 60)
        print(f"\n📊 Total frames:     {display.frame_count}")
        print(f"   Duration:         {tracker.duration:.1f}s")
        print(f"   Actual FPS:       {display.frame_count / tracker.duration:.2f}")
        print(f"   Target FPS:       {target_fps}")

        raw_mb = display.raw_frame_count * 1920 * 1080 * 3 / (1024 * 1024)
        print(f"\n💾 Raw frames kept:  {display.raw_frame_count} ({raw_mb:.1f} MB)")
        print(f"   Video buffer:     {display.video_buffer_size_mb:.2f} MB")

    # Print top 20 functions
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
    main()
