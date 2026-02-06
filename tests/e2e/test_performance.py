#!/usr/bin/env python3
"""Performance Test for simple-rdp
- Measures maximum frame capture rate
- Tracks memory usage over time
- 100 seconds of intensive UI operations using keyboard shortcuts
- Creates video and reports all statistics
"""

import asyncio
import io
import os
import subprocess
import sys
import time
import tracemalloc
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from simple_rdp import RDPClient  # noqa: E402
from simple_rdp.pdu import INPUT_EVENT_SCANCODE  # noqa: E402
from simple_rdp.pdu import build_scancode_event  # noqa: E402


@dataclass
class FrameStats:
    """Statistics for a captured frame"""

    timestamp: float
    capture_time_ms: float  # Time to capture this frame
    memory_mb: float  # Current memory usage
    frame_size_bytes: int  # Size of frame data


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics"""

    frames: list[FrameStats] = field(default_factory=list)
    frame_data: list[bytes] = field(default_factory=list)  # Raw PNG data
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
    def max_fps(self) -> float:
        if len(self.frames) < 2:
            return 0
        # Calculate instantaneous FPS between frames
        fps_values = []
        for i in range(1, len(self.frames)):
            dt = self.frames[i].timestamp - self.frames[i - 1].timestamp
            if dt > 0:
                fps_values.append(1.0 / dt)
        return max(fps_values) if fps_values else 0

    @property
    def min_capture_time_ms(self) -> float:
        return min(f.capture_time_ms for f in self.frames) if self.frames else 0

    @property
    def max_capture_time_ms(self) -> float:
        return max(f.capture_time_ms for f in self.frames) if self.frames else 0

    @property
    def avg_capture_time_ms(self) -> float:
        return sum(f.capture_time_ms for f in self.frames) / len(self.frames) if self.frames else 0

    @property
    def peak_memory_mb(self) -> float:
        return max(f.memory_mb for f in self.frames) if self.frames else 0

    @property
    def total_frame_data_mb(self) -> float:
        return sum(len(d) for d in self.frame_data) / (1024 * 1024)


# Windows keyboard scancodes
SCANCODES = {
    "escape": 0x01,
    "tab": 0x0F,
    "d": 0x20,
    "e": 0x12,
    "r": 0x13,
    "i": 0x17,
    "a": 0x1E,
    "s": 0x1F,
    "x": 0x2D,
    "m": 0x32,
    "f4": 0x3E,
    "f11": 0x57,
    "ctrl": 0x1D,
    "shift": 0x2A,
    "alt": 0x38,
    "win": 0x5B,  # Extended
    "up": 0x48,  # Extended
    "down": 0x50,  # Extended
    "left": 0x4B,  # Extended
    "right": 0x4D,  # Extended
    "space": 0x39,
    "enter": 0x1C,
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
}

EXTENDED_KEYS = {"win", "up", "down", "left", "right"}


async def send_scancode(client: RDPClient, scancode: int, is_release: bool = False, is_extended: bool = False):
    """Send a scancode with extended key support"""
    event_time = int(time.time() * 1000) & 0xFFFFFFFF
    event_data = build_scancode_event(scancode, is_release=is_release, is_extended=is_extended)
    await client._send_input_events([(event_time, INPUT_EVENT_SCANCODE, event_data)])


async def key_press(client: RDPClient, key: str, delay: float = 0.05):
    """Press and release a key"""
    scancode = SCANCODES.get(key, 0)
    extended = key in EXTENDED_KEYS
    await send_scancode(client, scancode, is_release=False, is_extended=extended)
    await asyncio.sleep(delay)
    await send_scancode(client, scancode, is_release=True, is_extended=extended)


async def key_combo(client: RDPClient, *keys: str, delay: float = 0.05):
    """Press a key combination (e.g., Win+D, Alt+Tab)"""
    # Press all keys
    for key in keys:
        scancode = SCANCODES.get(key, 0)
        extended = key in EXTENDED_KEYS
        await send_scancode(client, scancode, is_release=False, is_extended=extended)
        await asyncio.sleep(0.02)

    await asyncio.sleep(delay)

    # Release all keys in reverse order
    for key in reversed(keys):
        scancode = SCANCODES.get(key, 0)
        extended = key in EXTENDED_KEYS
        await send_scancode(client, scancode, is_release=True, is_extended=extended)
        await asyncio.sleep(0.02)


async def capture_loop(client: RDPClient, metrics: PerformanceMetrics, stop_event: asyncio.Event):
    """Capture frames as fast as possible and record statistics"""
    frame_count = 0

    while not stop_event.is_set():
        try:
            # Measure capture time
            start = time.perf_counter()
            screenshot = await client.screenshot()
            capture_time = (time.perf_counter() - start) * 1000  # ms

            # Get memory stats
            current, peak = tracemalloc.get_traced_memory()
            memory_mb = current / (1024 * 1024)

            # Convert to PNG bytes in memory
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG", optimize=False)
            png_data = buffer.getvalue()

            # Record stats
            stats = FrameStats(
                timestamp=time.perf_counter(),
                capture_time_ms=capture_time,
                memory_mb=memory_mb,
                frame_size_bytes=len(png_data),
            )
            metrics.frames.append(stats)
            metrics.frame_data.append(png_data)

            frame_count += 1
            if frame_count % 100 == 0:
                print(f"  Captured {frame_count} frames, Memory: {memory_mb:.1f}MB, Last capture: {capture_time:.1f}ms")

            # Small yield to allow other tasks
            await asyncio.sleep(0.001)

        except Exception as e:
            print(f"  Capture error: {e}")
            await asyncio.sleep(0.1)


async def intensive_ui_operations(client: RDPClient, duration_seconds: int = 100):
    """Perform intensive UI operations using keyboard shortcuts.
    Designed to stress-test screen updates.
    """
    print(f"\n=== Starting {duration_seconds}s of intensive UI operations ===\n")

    operations = [
        # Open and close various windows rapidly
        ("Win+E (Explorer)", lambda: key_combo(client, "win", "e")),
        ("Wait", lambda: asyncio.sleep(1.5)),
        ("Win+Up (Maximize)", lambda: key_combo(client, "win", "up")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Win+Down (Restore)", lambda: key_combo(client, "win", "down")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Win+Left (Snap left)", lambda: key_combo(client, "win", "left")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Win+Right (Snap right)", lambda: key_combo(client, "win", "right")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Alt+F4 (Close)", lambda: key_combo(client, "alt", "f4")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        # Task view and desktop switching
        ("Win+Tab (Task View)", lambda: key_combo(client, "win", "tab")),
        ("Wait", lambda: asyncio.sleep(1.0)),
        ("Escape", lambda: key_press(client, "escape")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        # Show desktop and restore
        ("Win+D (Show Desktop)", lambda: key_combo(client, "win", "d")),
        ("Wait", lambda: asyncio.sleep(0.8)),
        ("Win+D (Restore)", lambda: key_combo(client, "win", "d")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        # Open Settings
        ("Win+I (Settings)", lambda: key_combo(client, "win", "i")),
        ("Wait", lambda: asyncio.sleep(1.5)),
        ("Win+Up (Maximize)", lambda: key_combo(client, "win", "up")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Win+Down (Minimize)", lambda: key_combo(client, "win", "down")),
        ("Win+Down (Minimize)", lambda: key_combo(client, "win", "down")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Alt+F4 (Close)", lambda: key_combo(client, "alt", "f4")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        # Action Center
        ("Win+A (Action Center)", lambda: key_combo(client, "win", "a")),
        ("Wait", lambda: asyncio.sleep(1.0)),
        ("Escape", lambda: key_press(client, "escape")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        # Search
        ("Win+S (Search)", lambda: key_combo(client, "win", "s")),
        ("Wait", lambda: asyncio.sleep(1.0)),
        ("Escape", lambda: key_press(client, "escape")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        # Quick Link Menu
        ("Win+X (Quick Link)", lambda: key_combo(client, "win", "x")),
        ("Wait", lambda: asyncio.sleep(0.8)),
        ("Escape", lambda: key_press(client, "escape")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        # Open Run dialog
        ("Win+R (Run)", lambda: key_combo(client, "win", "r")),
        ("Wait", lambda: asyncio.sleep(0.8)),
        ("Escape", lambda: key_press(client, "escape")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        # Task Manager
        ("Ctrl+Shift+Esc (Task Manager)", lambda: key_combo(client, "ctrl", "shift", "escape")),
        ("Wait", lambda: asyncio.sleep(1.5)),
        ("Alt+F4 (Close)", lambda: key_combo(client, "alt", "f4")),
        ("Wait", lambda: asyncio.sleep(0.5)),
        # More Explorer windows for window switching
        ("Win+E (Explorer 1)", lambda: key_combo(client, "win", "e")),
        ("Wait", lambda: asyncio.sleep(1.0)),
        ("Win+E (Explorer 2)", lambda: key_combo(client, "win", "e")),
        ("Wait", lambda: asyncio.sleep(1.0)),
        ("Win+E (Explorer 3)", lambda: key_combo(client, "win", "e")),
        ("Wait", lambda: asyncio.sleep(1.0)),
        # Rapid Alt+Tab switching
        ("Alt+Tab", lambda: key_combo(client, "alt", "tab")),
        ("Wait", lambda: asyncio.sleep(0.3)),
        ("Alt+Tab", lambda: key_combo(client, "alt", "tab")),
        ("Wait", lambda: asyncio.sleep(0.3)),
        ("Alt+Tab", lambda: key_combo(client, "alt", "tab")),
        ("Wait", lambda: asyncio.sleep(0.3)),
        # Cascade snap operations
        ("Win+Left", lambda: key_combo(client, "win", "left")),
        ("Wait", lambda: asyncio.sleep(0.3)),
        ("Win+Right", lambda: key_combo(client, "win", "right")),
        ("Wait", lambda: asyncio.sleep(0.3)),
        ("Win+Up", lambda: key_combo(client, "win", "up")),
        ("Wait", lambda: asyncio.sleep(0.3)),
        ("Win+Down", lambda: key_combo(client, "win", "down")),
        ("Wait", lambda: asyncio.sleep(0.3)),
        # Minimize all and restore
        ("Win+M (Minimize All)", lambda: key_combo(client, "win", "m")),
        ("Wait", lambda: asyncio.sleep(1.0)),
        ("Win+Shift+M (Restore)", lambda: key_combo(client, "win", "shift", "m")),
        ("Wait", lambda: asyncio.sleep(1.0)),
        # Close all explorers
        ("Alt+F4 (Close)", lambda: key_combo(client, "alt", "f4")),
        ("Wait", lambda: asyncio.sleep(0.3)),
        ("Alt+F4 (Close)", lambda: key_combo(client, "alt", "f4")),
        ("Wait", lambda: asyncio.sleep(0.3)),
        ("Alt+F4 (Close)", lambda: key_combo(client, "alt", "f4")),
        ("Wait", lambda: asyncio.sleep(0.5)),
    ]

    start_time = time.time()
    cycle = 0
    op_count = 0

    while (time.time() - start_time) < duration_seconds:
        cycle += 1
        print(f"  Cycle {cycle} (elapsed: {time.time() - start_time:.1f}s)")

        for name, action in operations:
            if (time.time() - start_time) >= duration_seconds:
                break

            if not name.startswith("Wait"):
                op_count += 1
                print(f"    [{op_count}] {name}")

            await action()

    print(f"\n=== Completed {op_count} operations in {cycle} cycles ===\n")


def create_video(metrics: PerformanceMetrics, output_dir: str) -> tuple[str, float]:
    """Save frames and create video, return path and size in MB"""
    print(f"\nSaving {len(metrics.frame_data)} frames to disk...")

    # Save all frames
    for i, png_data in enumerate(metrics.frame_data):
        frame_path = os.path.join(output_dir, f"frame_{i:05d}.png")
        with open(frame_path, "wb") as f:
            f.write(png_data)
        if (i + 1) % 200 == 0:
            print(f"  Saved {i + 1}/{len(metrics.frame_data)} frames")

    print("  All frames saved!")

    # Calculate actual FPS for video
    actual_fps = metrics.avg_fps
    # Use actual FPS for playback, but cap at reasonable value
    video_fps = min(max(5, int(actual_fps)), 60)

    video_path = os.path.join(output_dir, "recording.mp4")
    frame_pattern = os.path.join(output_dir, "frame_%05d.png")

    print(f"\nCreating video at {video_fps} FPS...")

    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(video_fps),
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
        print(f"  FFmpeg error: {result.stderr}")
        return "", 0

    video_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"  Video created: {video_path}")

    return video_path, video_size_mb


def print_report(metrics: PerformanceMetrics, video_path: str, video_size_mb: float):
    """Print comprehensive performance report"""
    print("\n" + "=" * 70)
    print("                    PERFORMANCE TEST REPORT")
    print("=" * 70)

    print("\n📊 CAPTURE STATISTICS:")
    print(f"   Total frames captured:     {metrics.total_frames:,}")
    print(f"   Test duration:             {metrics.duration_seconds:.2f} seconds")
    print(f"   Average FPS:               {metrics.avg_fps:.2f}")
    print(f"   Peak instantaneous FPS:    {metrics.max_fps:.2f}")

    print("\n⏱️  CAPTURE TIMING:")
    print(f"   Min capture time:          {metrics.min_capture_time_ms:.2f} ms")
    print(f"   Max capture time:          {metrics.max_capture_time_ms:.2f} ms")
    print(f"   Avg capture time:          {metrics.avg_capture_time_ms:.2f} ms")
    print(f"   Theoretical max FPS:       {1000 / metrics.avg_capture_time_ms:.2f}")

    print("\n💾 MEMORY USAGE:")
    print(f"   Peak memory (traced):      {metrics.peak_memory_mb:.2f} MB")
    print(f"   Total frame data in RAM:   {metrics.total_frame_data_mb:.2f} MB")
    print(f"   Avg frame size (PNG):      {metrics.total_frame_data_mb * 1024 / metrics.total_frames:.2f} KB")

    print("\n🎬 VIDEO OUTPUT:")
    print(f"   Video file:                {video_path}")
    print(f"   Video size:                {video_size_mb:.2f} MB")
    print(f"   Compression ratio:         {metrics.total_frame_data_mb / video_size_mb:.1f}x")
    print(f"   Video duration:            {metrics.total_frames / metrics.avg_fps:.1f} seconds (at capture rate)")

    # Frame rate over time analysis
    if len(metrics.frames) > 10:
        # Analyze FPS in 10-second buckets
        print("\n📈 FPS OVER TIME (10s buckets):")
        bucket_size = 10.0
        buckets = {}
        first_ts = metrics.frames[0].timestamp
        for f in metrics.frames:
            bucket = int((f.timestamp - first_ts) / bucket_size)
            if bucket not in buckets:
                buckets[bucket] = 0
            buckets[bucket] += 1

        for bucket, count in sorted(buckets.items()):
            fps = count / bucket_size
            bar = "█" * int(fps / 2)
            print(f"   {bucket * 10:3d}-{(bucket + 1) * 10:3d}s: {fps:5.1f} FPS {bar}")

    print("\n" + "=" * 70)


async def main():
    host = os.environ.get("RDP_HOST", "")
    username = os.environ.get("RDP_USER", "")
    password = os.environ.get("RDP_PASS", "")

    if not host or not username or not password:
        print("ERROR: Set RDP_HOST, RDP_USER, RDP_PASS environment variables (or use .env file)")
        return

    # Create session directory
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(os.path.dirname(__file__), "sessions", f"perf_{session_id}")
    os.makedirs(session_dir, exist_ok=True)
    print(f"Session directory: {session_dir}")

    # Start memory tracking
    tracemalloc.start()

    metrics = PerformanceMetrics()
    stop_capture = asyncio.Event()

    print(f"\nConnecting to {host} as {username}...")

    client = RDPClient(host, username=username, password=password, width=1920, height=1080, show_wallpaper=True)

    try:
        await client.connect()
        print("Connected! Waiting for initial screen...")
        await asyncio.sleep(3)

        # Start capture task (runs as fast as possible)
        print("\nStarting high-speed frame capture...")
        metrics.start_time = time.perf_counter()
        capture_task = asyncio.create_task(capture_loop(client, metrics, stop_capture))

        # Give capture a moment to start
        await asyncio.sleep(0.5)

        # Run intensive UI operations for 100 seconds
        await intensive_ui_operations(client, duration_seconds=100)

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
        video_path, video_size_mb = create_video(metrics, session_dir)

        # Print final report
        print_report(metrics, video_path, video_size_mb)

    # Stop memory tracking
    tracemalloc.stop()


if __name__ == "__main__":
    asyncio.run(main())
