#!/usr/bin/env python3
"""Graphics-Intensive RDP Performance Test
- Opens Task Manager, Windows Search, Edge browser repeatedly
- Captures screen at 10 FPS
- Creates video from captured frames
"""

import asyncio
import io
import os
import subprocess
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
    """Capture frames at exactly 10 FPS"""
    target_interval = 0.1  # 100ms = 10 FPS
    frame_count = 0

    while not stop_event.is_set():
        loop_start = time.perf_counter()

        try:
            screenshot = await client.screenshot()

            # Convert to PNG in memory
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG", optimize=False)
            png_data = buffer.getvalue()

            metrics.frames.append((time.perf_counter(), png_data))
            frame_count += 1

            if frame_count % 50 == 0:
                print(f"    [Capture] {frame_count} frames, {metrics.total_size_mb:.1f} MB in memory")

        except Exception as e:
            print(f"    [Capture Error] {e}")

        # Sleep for remainder of interval
        elapsed = time.perf_counter() - loop_start
        sleep_time = max(0, target_interval - elapsed)
        await asyncio.sleep(sleep_time)


async def graphic_intensive_actions(client: RDPClient, duration_seconds: int = 60):
    """Perform graphic-intensive UI actions every 0.5 seconds.
    Uses keyboard shortcuts to open/close windows rapidly.
    """
    print(f"\n=== Starting {duration_seconds}s of graphic-intensive actions ===\n")

    action_interval = 0.5  # 0.5 seconds between actions

    # Define a sequence of actions that create lots of visual changes
    # Using simple keys and combos that work reliably
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
        # Open Action Center: Win+A
        ("Open Action Center", [("win", True), ("a", True)], [("a", False), ("win", False)]),
        # Close Action Center: Escape
        ("Close", [("escape", True)], [("escape", False)]),
        # Show Desktop: Win+D
        ("Show Desktop", [("win", True), ("d", True)], [("d", False), ("win", False)]),
        # Restore Desktop: Win+D again
        ("Restore Desktop", [("win", True), ("d", True)], [("d", False), ("win", False)]),
        # Open Quick Link: Win+X
        ("Open Quick Link", [("win", True), ("x", True)], [("x", False), ("win", False)]),
        # Close Quick Link: Escape
        ("Close Quick Link", [("escape", True)], [("escape", False)]),
    ]

    # Scancode mapping
    scancodes = {
        "escape": (0x01, False),
        "tab": (0x0F, False),
        "1": (0x02, False),
        "2": (0x03, False),
        "3": (0x04, False),
        "4": (0x05, False),
        "5": (0x06, False),
        "a": (0x1E, False),
        "d": (0x20, False),
        "e": (0x12, False),
        "f4": (0x3E, False),
        "i": (0x17, False),
        "m": (0x32, False),
        "r": (0x13, False),
        "s": (0x1F, False),
        "x": (0x2D, False),
        "ctrl": (0x1D, False),
        "shift": (0x2A, False),
        "alt": (0x38, False),
        "win": (0x5B, True),  # Extended key
        "up": (0x48, True),
        "down": (0x50, True),
        "left": (0x4B, True),
        "right": (0x4D, True),
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


def create_video(metrics: PerformanceMetrics, output_dir: str, target_fps: int = 10) -> tuple[str, float]:
    """Save frames and create video"""
    print(f"\nSaving {metrics.total_frames} frames to disk...")

    for i, (_ts, png_data) in enumerate(metrics.frames):
        frame_path = os.path.join(output_dir, f"frame_{i:05d}.png")
        with open(frame_path, "wb") as f:
            f.write(png_data)
        if (i + 1) % 100 == 0:
            print(f"  Saved {i + 1}/{metrics.total_frames} frames")

    print("  All frames saved!")

    video_path = os.path.join(output_dir, "recording.mp4")
    frame_pattern = os.path.join(output_dir, "frame_%05d.png")

    print(f"\nCreating video at {target_fps} FPS...")

    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(target_fps),
        "-i",
        frame_pattern,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "23",
        video_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[-500:]}")
        return "", 0

    video_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"  Video created: {video_path}")

    return video_path, video_size_mb


def print_report(metrics: PerformanceMetrics, video_path: str, video_size_mb: float):
    """Print performance report"""
    print("\n" + "=" * 60)
    print("              PERFORMANCE REPORT")
    print("=" * 60)

    print("\n📊 CAPTURE STATISTICS:")
    print(f"   Total frames:         {metrics.total_frames:,}")
    print(f"   Duration:             {metrics.duration_seconds:.1f} seconds")
    print(f"   Average FPS:          {metrics.avg_fps:.2f}")
    print("   Target FPS:           10.00")

    print("\n💾 MEMORY & STORAGE:")
    print(f"   Total PNG data:       {metrics.total_size_mb:.2f} MB")
    print(f"   Avg frame size:       {metrics.total_size_mb * 1024 / metrics.total_frames:.1f} KB")
    print(f"   Video size:           {video_size_mb:.2f} MB")
    print(f"   Compression ratio:    {metrics.total_size_mb / video_size_mb:.1f}x")

    print("\n🎬 VIDEO:")
    print(f"   Path:                 {video_path}")
    print(f"   Duration:             {metrics.total_frames / 10:.1f} seconds")

    print("\n" + "=" * 60)


async def main():
    host = os.environ.get("RDP_HOST", "")
    username = os.environ.get("RDP_USER", "")
    password = os.environ.get("RDP_PASS", "")
    duration = int(os.environ.get("DURATION", "60"))  # Default 60 seconds

    if not host or not username or not password:
        print("ERROR: Set RDP_HOST, RDP_USER, RDP_PASS environment variables (or use .env file)")
        return

    # Create session directory
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(os.path.dirname(__file__), "sessions", f"graphics_{session_id}")
    os.makedirs(session_dir, exist_ok=True)
    print(f"Session directory: {session_dir}")
    print(f"Test duration: {duration} seconds")

    metrics = PerformanceMetrics()
    stop_capture = asyncio.Event()

    print(f"\nConnecting to {host} as {username}...")

    client = RDPClient(host, username=username, password=password, width=1920, height=1080, show_wallpaper=True)

    try:
        await client.connect()
        print("Connected! Waiting for initial screen...")
        await asyncio.sleep(3)

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

    # Create video
    if metrics.total_frames > 0:
        video_path, video_size_mb = create_video(metrics, session_dir, target_fps=10)
        print_report(metrics, video_path, video_size_mb)
    else:
        print("No frames captured!")


if __name__ == "__main__":
    asyncio.run(main())
