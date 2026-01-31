"""
Example v2: Video recording of RDP session with automated interactions.

This example demonstrates:
- Continuous frame capture at 5 FPS in a background task
- Automated mouse and keyboard interactions over 1 minute
- Saving captured frames to session folder
- Converting frames to video using ffmpeg
"""

import asyncio
import contextlib
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from rich.logging import RichHandler

from simple_rdp import RDPClient

load_dotenv()


class FrameBuffer:
    """Thread-safe buffer for storing captured frames."""

    def __init__(self):
        self.frames: list[Image.Image] = []
        self.timestamps: list[float] = []
        self._lock = asyncio.Lock()
        self.start_time: float = 0

    async def add_frame(self, frame: Image.Image) -> int:
        """Add a frame to the buffer. Returns the frame index."""
        async with self._lock:
            self.frames.append(frame)
            self.timestamps.append(time.time() - self.start_time)
            return len(self.frames) - 1

    async def get_frame_count(self) -> int:
        """Get the current number of frames."""
        async with self._lock:
            return len(self.frames)

    def save_all(self, session_dir: Path) -> int:
        """Save all frames to disk. Returns number of frames saved."""
        session_dir.mkdir(parents=True, exist_ok=True)

        for i, frame in enumerate(self.frames):
            frame_path = session_dir / f"frame_{i:05d}.png"
            frame.save(frame_path)

        return len(self.frames)


async def capture_task(
    client: RDPClient,
    buffer: FrameBuffer,
    fps: float = 5.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """
    Background task that captures frames at the specified FPS.

    Args:
        client: The RDP client to capture from.
        buffer: The frame buffer to store captures.
        fps: Frames per second (default: 5).
        stop_event: Event to signal when to stop capturing.
    """
    frame_interval = 1.0 / fps
    buffer.start_time = time.time()

    while stop_event is None or not stop_event.is_set():
        loop_start = time.time()

        try:
            # Capture frame (returns PIL Image in memory)
            frame = await client.screenshot()
            frame_idx = await buffer.add_frame(frame)

            if frame_idx % 10 == 0:
                print(f"  [Capture] Frame {frame_idx} captured")
        except Exception as e:
            print(f"  [Capture] Error: {e}")

        # Maintain target FPS
        elapsed = time.time() - loop_start
        sleep_time = max(0, frame_interval - elapsed)
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)


async def perform_interactions(client: RDPClient) -> None:
    """
    Perform automated mouse and keyboard interactions.

    This runs for approximately 1 minute, performing various UI interactions.
    """
    print("\n=== Starting automated interactions ===\n")

    # Screen dimensions (assuming 1920x1080)
    width, height = 1920, 1080

    # Windows button location (bottom-left, Start button)
    start_button = (28, height - 28)  # ~center of Start button

    # Clock/system tray location (bottom-right)
    clock_area = (width - 100, height - 28)

    # Center of screen
    center = (width // 2, height // 2)

    interactions = [
        # Phase 1: Initial setup (0-10 seconds)
        ("Move mouse to center", lambda: client.mouse_move(*center)),
        ("Wait", lambda: asyncio.sleep(1)),
        ("Click center", lambda: client.mouse_click(*center)),
        ("Wait", lambda: asyncio.sleep(2)),
        # Phase 2: Windows Start menu (10-20 seconds)
        ("Move to Start button", lambda: client.mouse_move(*start_button)),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Click Start button", lambda: client.mouse_click(*start_button)),
        ("Wait for Start menu", lambda: asyncio.sleep(2)),
        ("Press Windows key to toggle", lambda: client.send_key(0x5B)),
        ("Wait", lambda: asyncio.sleep(1)),
        # Phase 3: Open Start menu with keyboard (20-30 seconds)
        ("Press Windows key", lambda: client.send_key(0x5B)),
        ("Wait for menu", lambda: asyncio.sleep(1.5)),
        ("Type 'settings'", lambda: client.send_text("settings")),
        ("Wait for search", lambda: asyncio.sleep(2)),
        ("Press Escape", lambda: client.send_key(0x01)),
        ("Wait", lambda: asyncio.sleep(1)),
        # Phase 4: Mouse movements (30-40 seconds)
        ("Move mouse top-left", lambda: client.mouse_move(100, 100)),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Move mouse top-right", lambda: client.mouse_move(width - 100, 100)),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Move mouse bottom-right", lambda: client.mouse_move(width - 100, height - 100)),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Move mouse bottom-left", lambda: client.mouse_move(100, height - 100)),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Move mouse to center", lambda: client.mouse_move(*center)),
        ("Wait", lambda: asyncio.sleep(1)),
        # Phase 5: Click on clock/system tray (40-50 seconds)
        ("Move to clock area", lambda: client.mouse_move(*clock_area)),
        ("Wait", lambda: asyncio.sleep(0.5)),
        ("Click clock", lambda: client.mouse_click(*clock_area)),
        ("Wait for calendar popup", lambda: asyncio.sleep(3)),
        ("Press Escape to close", lambda: client.send_key(0x01)),
        ("Wait", lambda: asyncio.sleep(1)),
        # Phase 6: Final interactions (50-60 seconds)
        ("Press Windows key", lambda: client.send_key(0x5B)),
        ("Wait", lambda: asyncio.sleep(1.5)),
        ("Type 'notepad'", lambda: client.send_text("notepad")),
        ("Wait", lambda: asyncio.sleep(2)),
        ("Press Escape", lambda: client.send_key(0x01)),
        ("Wait", lambda: asyncio.sleep(1)),
        ("Move to center", lambda: client.mouse_move(*center)),
        ("Final wait", lambda: asyncio.sleep(2)),
    ]

    for i, (description, action) in enumerate(interactions):
        print(f"  [{i + 1}/{len(interactions)}] {description}")
        await action()


def create_video_from_frames(session_dir: Path, output_path: Path, fps: int = 5) -> bool:
    """
    Create a video from saved frames using ffmpeg.

    Args:
        session_dir: Directory containing frame_XXXXX.png files.
        output_path: Path for the output video file.
        fps: Frames per second for the video.

    Returns:
        True if successful, False otherwise.
    """
    frame_pattern = session_dir / "frame_%05d.png"

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file if exists
        "-framerate",
        str(fps),
        "-i",
        str(frame_pattern),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "23",  # Quality (lower = better, 18-28 is reasonable)
        str(output_path),
    ]

    print(f"\nRunning ffmpeg: {' '.join(cmd)}")

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("ffmpeg not found. Please install ffmpeg to create videos.")
        return False


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler()])

    # Get RDP connection details from environment
    host = os.environ.get("RDP_HOST", "")
    username = os.environ.get("RDP_USER", "")
    password = os.environ.get("RDP_PASS", "")

    if not host or not username or not password:
        print("ERROR: Set RDP_HOST, RDP_USER, RDP_PASS environment variables (or use .env file)")
        return

    # Create session directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = Path("sessions") / timestamp
    print(f"\n{'=' * 60}")
    print(f"RDP Session Recording - {timestamp}")
    print(f"Session directory: {session_dir}")
    print(f"{'=' * 60}\n")

    # Initialize frame buffer
    buffer = FrameBuffer()
    stop_capture = asyncio.Event()

    async with RDPClient(host=host, username=username, password=password, show_wallpaper=True) as client:
        print("Connected to RDP server!\n")

        # Wait a moment for initial screen to render
        await asyncio.sleep(2)

        # Start background capture task (5 FPS)
        print("Starting frame capture at 5 FPS...")
        capture = asyncio.create_task(capture_task(client, buffer, fps=5.0, stop_event=stop_capture))

        try:
            # Perform automated interactions (~1 minute)
            await perform_interactions(client)

        finally:
            # Stop capture task
            print("\nStopping frame capture...")
            stop_capture.set()

            # Wait for capture task to finish
            try:
                await asyncio.wait_for(capture, timeout=2.0)
            except TimeoutError:
                capture.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await capture

    # Get final frame count
    frame_count = await buffer.get_frame_count()
    print(f"\n{'=' * 60}")
    print(f"Capture complete! {frame_count} frames captured")
    print(f"{'=' * 60}\n")

    # Save frames to disk
    print(f"Saving frames to {session_dir}...")
    saved_count = buffer.save_all(session_dir)
    print(f"Saved {saved_count} frames to disk")

    # Create video from frames
    video_path = session_dir / "recording.mp4"
    print(f"\nCreating video: {video_path}")

    if create_video_from_frames(session_dir, video_path, fps=5):
        print(f"\n✓ Video created successfully: {video_path}")

        # Show video file size
        if video_path.exists():
            size_mb = video_path.stat().st_size / (1024 * 1024)
            print(f"  Video size: {size_mb:.2f} MB")
            print(f"  Duration: ~{frame_count / 5:.1f} seconds")
    else:
        print("\n✗ Failed to create video")

    print(f"\n{'=' * 60}")
    print("Session complete!")
    print(f"  Frames: {session_dir}/frame_*.png")
    print(f"  Video:  {video_path}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
