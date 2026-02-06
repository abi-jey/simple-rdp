#!/usr/bin/env python3
"""Performance Test for simple-rdp (Mouse-only version)
- Measures maximum frame capture rate
- Tracks memory usage over time
- 100 seconds of mouse movements to generate screen updates
- Creates video and reports all statistics
"""

import asyncio
import io
import os
import random
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


async def mouse_stress_test(client: RDPClient, duration_seconds: int = 100):
    """Perform intensive mouse movements to generate screen updates.
    This is a safe stress test that won't disconnect the session.
    """
    print(f"\n=== Starting {duration_seconds}s of mouse movement stress test ===\n")

    width = 1920
    height = 1080

    start_time = time.time()
    move_count = 0
    click_count = 0

    patterns = [
        "horizontal_sweep",
        "vertical_sweep",
        "diagonal",
        "random_jumps",
        "circle",
        "spiral",
    ]

    pattern_idx = 0
    pattern_start = time.time()
    pattern_duration = 10  # Change pattern every 10 seconds

    x, y = width // 2, height // 2

    while (time.time() - start_time) < duration_seconds:
        elapsed = time.time() - start_time

        # Switch patterns every N seconds
        if time.time() - pattern_start > pattern_duration:
            pattern_idx = (pattern_idx + 1) % len(patterns)
            pattern_start = time.time()
            print(f"  [{elapsed:.0f}s] Switching to pattern: {patterns[pattern_idx]}")

        pattern = patterns[pattern_idx]

        if pattern == "horizontal_sweep":
            # Sweep horizontally
            x = int((time.time() * 200) % width)
            y = height // 2 + int(50 * (time.time() % 2 - 1))

        elif pattern == "vertical_sweep":
            # Sweep vertically
            x = width // 2 + int(50 * (time.time() % 2 - 1))
            y = int((time.time() * 200) % height)

        elif pattern == "diagonal":
            # Diagonal movement
            t = (time.time() * 100) % max(width, height)
            x = int(t % width)
            y = int(t % height)

        elif pattern == "random_jumps":
            # Random position jumps (generates lots of screen changes)
            if move_count % 5 == 0:  # Jump every 5th move
                x = random.randint(100, width - 100)
                y = random.randint(100, height - 100)
            else:
                x = max(0, min(width - 1, x + random.randint(-20, 20)))
                y = max(0, min(height - 1, y + random.randint(-20, 20)))

        elif pattern == "circle":
            # Circular motion
            t = time.time() * 2
            radius = 200
            cx, cy = width // 2, height // 2
            x = int(cx + radius * (1 + 0.5 * (t % 3)) * (t % 6.28 - 3.14) / 3.14)
            y = int(cy + radius * (1 + 0.5 * (t % 3)) * ((t + 1.57) % 6.28 - 3.14) / 3.14)
            x = max(0, min(width - 1, x))
            y = max(0, min(height - 1, y))

        elif pattern == "spiral":
            # Spiral from center
            t = time.time() - pattern_start
            radius = t * 30
            angle = t * 4
            cx, cy = width // 2, height // 2
            x = int(cx + radius * (angle % 6.28 - 3.14) / 3.14)
            y = int(cy + radius * ((angle + 1.57) % 6.28 - 3.14) / 3.14)
            x = max(0, min(width - 1, x))
            y = max(0, min(height - 1, y))

        # Move mouse
        await client.mouse_move(x, y)
        move_count += 1

        # Occasional click (but not too many to avoid accidental actions)
        if move_count % 100 == 0:
            # Click in a safe area (bottom right, unlikely to do anything)
            await client.mouse_click(width - 50, height - 50)
            click_count += 1

        # Small delay between moves (50 moves/sec)
        await asyncio.sleep(0.02)

        if move_count % 500 == 0:
            print(f"  [{elapsed:.1f}s] Mouse moves: {move_count}, Clicks: {click_count}")

    print(f"\n=== Completed {move_count} mouse moves, {click_count} clicks ===\n")


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

        # Run mouse stress test for 100 seconds
        await mouse_stress_test(client, duration_seconds=100)

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
