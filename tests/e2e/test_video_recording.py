"""
Video recording of RDP session with automated interactions.

This example demonstrates:
- Native file recording using library's built-in ffmpeg streaming
- Automated mouse and keyboard interactions
- Pointer composited into video frames
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.logging import RichHandler

from simple_rdp import RDPClient

load_dotenv()


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
    session_dir.mkdir(parents=True, exist_ok=True)
    video_path = session_dir / "recording.ts"

    print(f"\n{'=' * 60}")
    print(f"RDP Session Recording - {timestamp}")
    print(f"Session directory: {session_dir}")
    print(f"Video output: {video_path}")
    print(f"{'=' * 60}\n")

    async with RDPClient(host=host, username=username, password=password, show_wallpaper=True) as client:
        print("Connected to RDP server!\n")

        # Wait a moment for initial screen to render
        await asyncio.sleep(2)

        # Start native file recording (uses library's built-in ffmpeg streaming)
        print("Starting native file recording...")
        await client.start_file_recording(str(video_path))
        print(f"Recording to: {video_path}")

        try:
            # Perform automated interactions (~1 minute)
            await perform_interactions(client)

        finally:
            # Stop recording
            print("\nStopping recording...")
            await client.stop_file_recording()
            await client.stop_streaming()

    # Show results
    print(f"\n{'=' * 60}")
    print("Recording complete!")
    print(f"{'=' * 60}\n")

    if video_path.exists():
        size_mb = video_path.stat().st_size / (1024 * 1024)
        stats = client.get_recording_stats()
        print(f"✓ Video saved: {video_path}")
        print(f"  Size: {size_mb:.2f} MB")
        print(f"  Frames encoded: {stats.get('frames_encoded', 'N/A')}")
        print(f"  Pointer updates: {stats.get('pointer_updates', 'N/A')}")
        print(f"  Pointer throttled: {stats.get('pointer_updates_throttled', 'N/A')}")
    else:
        print("✗ Video file not found")

    print(f"\n{'=' * 60}")
    print("Session complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
