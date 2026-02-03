"""
Pointer visibility test - Verifies cursor compositing in recordings.

This test specifically tests pointer visibility with clear movement patterns:
- Rectangular path around screen edges
- Circular motion in center
- Diagonal selection (drag) patterns

The pointer should be visible in the recording at all times.
"""

import asyncio
import logging
import math
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.logging import RichHandler

from simple_rdp import RDPClient

load_dotenv()


async def rectangular_pattern(client: RDPClient, width: int, height: int) -> None:
    """
    Move mouse in a rectangular pattern around screen edges.

    This creates a clear, visible path that's easy to verify in recordings.
    """
    print("\n  === Rectangular Pattern ===")
    margin = 100
    steps = 20
    delay = 0.1

    corners = [
        (margin, margin),  # Top-left
        (width - margin, margin),  # Top-right
        (width - margin, height - margin),  # Bottom-right
        (margin, height - margin),  # Bottom-left
        (margin, margin),  # Back to top-left
    ]

    for i in range(len(corners) - 1):
        x1, y1 = corners[i]
        x2, y2 = corners[i + 1]

        for step in range(steps + 1):
            t = step / steps
            x = int(x1 + (x2 - x1) * t)
            y = int(y1 + (y2 - y1) * t)
            await client.mouse_move(x, y)
            await asyncio.sleep(delay)

        print(f"    Corner {i + 1} -> {i + 2}: ({x2}, {y2})")


async def circular_pattern(client: RDPClient, width: int, height: int) -> None:
    """
    Move mouse in a circular pattern in the center of the screen.

    Creates a smooth circular motion that's visually distinct.
    """
    print("\n  === Circular Pattern ===")
    cx, cy = width // 2, height // 2
    radius = 200
    steps = 60  # Full circle
    delay = 0.05

    for step in range(steps + 1):
        angle = (step / steps) * 2 * math.pi
        x = int(cx + radius * math.cos(angle))
        y = int(cy + radius * math.sin(angle))
        await client.mouse_move(x, y)
        await asyncio.sleep(delay)

    print(f"    Completed circle at center ({cx}, {cy}), radius {radius}")


async def diagonal_selection_pattern(client: RDPClient, width: int, height: int) -> None:
    """
    Perform diagonal selection (drag) patterns.

    Simulates selection boxes being drawn diagonally across the screen.
    """
    print("\n  === Diagonal Selection Pattern ===")
    steps = 30
    delay = 0.05

    # Diagonal from top-left to center (drag)
    print("    Selection 1: Top-left to center")
    await client.mouse_move(100, 100)
    await asyncio.sleep(0.2)
    await client.mouse_button_down(100, 100, button="left")
    await asyncio.sleep(0.1)

    for step in range(steps + 1):
        t = step / steps
        x = int(100 + (width // 2 - 100) * t)
        y = int(100 + (height // 2 - 100) * t)
        await client.mouse_move(x, y)
        await asyncio.sleep(delay)

    await client.mouse_button_up(width // 2, height // 2, button="left")
    await asyncio.sleep(0.3)

    # Diagonal from top-right to bottom-left (drag)
    print("    Selection 2: Top-right to bottom-left")
    await client.mouse_move(width - 100, 100)
    await asyncio.sleep(0.2)
    await client.mouse_button_down(width - 100, 100, button="left")
    await asyncio.sleep(0.1)

    for step in range(steps + 1):
        t = step / steps
        x = int((width - 100) - (width - 200) * t)
        y = int(100 + (height - 200) * t)
        await client.mouse_move(x, y)
        await asyncio.sleep(delay)

    await client.mouse_button_up(100, height - 100, button="left")
    await asyncio.sleep(0.3)


async def spiral_pattern(client: RDPClient, width: int, height: int) -> None:
    """
    Move mouse in a spiral pattern from center outward.

    Creates an expanding spiral that's visually interesting.
    """
    print("\n  === Spiral Pattern ===")
    cx, cy = width // 2, height // 2
    max_radius = min(width, height) // 3
    rotations = 3
    points_per_rotation = 40
    total_points = rotations * points_per_rotation
    delay = 0.03

    for point in range(total_points + 1):
        t = point / total_points
        radius = max_radius * t
        angle = t * rotations * 2 * math.pi
        x = int(cx + radius * math.cos(angle))
        y = int(cy + radius * math.sin(angle))
        await client.mouse_move(x, y)
        await asyncio.sleep(delay)

    print(f"    Completed spiral with {rotations} rotations")


async def perform_pointer_test(client: RDPClient) -> None:
    """
    Perform all pointer visibility tests.
    """
    print("\n=== Pointer Visibility Test ===")
    print("Testing pointer compositing with various movement patterns...")

    # Screen dimensions (assuming 1920x1080)
    width, height = 1920, 1080

    # Initial position - center of screen
    print("\n  Moving pointer to center...")
    await client.mouse_move(width // 2, height // 2)
    await asyncio.sleep(1)

    # Pattern 1: Rectangle
    await rectangular_pattern(client, width, height)
    await asyncio.sleep(0.5)

    # Pattern 2: Circle
    await circular_pattern(client, width, height)
    await asyncio.sleep(0.5)

    # Pattern 3: Spiral
    await spiral_pattern(client, width, height)
    await asyncio.sleep(0.5)

    # Pattern 4: Diagonal selections
    await diagonal_selection_pattern(client, width, height)
    await asyncio.sleep(0.5)

    # Final position - center
    print("\n  Returning pointer to center...")
    await client.mouse_move(width // 2, height // 2)
    await asyncio.sleep(1)

    print("\n=== Pointer Test Complete ===\n")


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
    session_dir = Path("tests/e2e/sessions") / f"pointer_test_{timestamp}"
    session_dir.mkdir(parents=True, exist_ok=True)
    video_ts_path = session_dir / "pointer_test.ts"
    video_mp4_path = session_dir / "pointer_test.mp4"

    print(f"\n{'=' * 60}")
    print(f"Pointer Visibility Test - {timestamp}")
    print(f"Session directory: {session_dir}")
    print(f"Video output: {video_ts_path}")
    print(f"{'=' * 60}\n")

    async with RDPClient(host=host, username=username, password=password, show_wallpaper=True) as client:
        print("Connected to RDP server!\n")

        # Wait for initial screen to render
        await asyncio.sleep(2)

        # Start recording
        print("Starting recording...")
        await client.start_file_recording(str(video_ts_path))
        print(f"Recording to: {video_ts_path}")

        try:
            # Perform pointer visibility tests
            await perform_pointer_test(client)

        finally:
            # Stop recording
            print("Stopping recording...")
            await client.stop_file_recording()
            await client.stop_streaming()

    # Show results
    print(f"\n{'=' * 60}")
    print("Recording complete!")
    print(f"{'=' * 60}\n")

    if video_ts_path.exists():
        size_mb = video_ts_path.stat().st_size / (1024 * 1024)
        stats = client.get_recording_stats()
        print(f"✓ Video saved: {video_ts_path}")
        print(f"  Size: {size_mb:.2f} MB")
        print(f"  Frames encoded: {stats.get('frames_encoded', 'N/A')}")
        print(f"  Pointer updates: {stats.get('pointer_updates', 'N/A')}")
        print(f"  Pointer throttled: {stats.get('pointer_updates_throttled', 'N/A')}")

        # Transcode to MP4
        print("\nTranscoding to MP4...")
        if RDPClient.transcode(str(video_ts_path), str(video_mp4_path)):
            mp4_size_mb = video_mp4_path.stat().st_size / (1024 * 1024)
            print(f"✓ MP4 saved: {video_mp4_path}")
            print(f"  Size: {mp4_size_mb:.2f} MB")
        else:
            print("✗ Transcode failed")
    else:
        print("✗ Video file not found")

    print(f"\n{'=' * 60}")
    print("To verify pointer visibility:")
    print(f"  1. Open {video_mp4_path}")
    print("  2. Look for the white arrow cursor during movement patterns")
    print("  3. Cursor should be visible in rectangle, circle, and diagonal patterns")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
