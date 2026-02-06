#!/usr/bin/env python3
"""E2E Test for Display Class - Video Streaming Pipeline.

Tests the new Display architecture:
- "Always-on" background streaming (fMP4)
- Async video queue for consumers
- Pipeline statistics
- Automatic recording to temp file
"""

import asyncio
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from simple_rdp import RDPClient  # noqa: E402


async def consume_video_stream(client: RDPClient, duration: int):
    """Consume video chunks from the client's queue."""
    start_time = time.time()
    chunk_count = 0
    total_bytes = 0

    print(f"\n[Consumer] Starting stream consumption for {duration}s...")

    while (time.time() - start_time) < duration:
        # Wait for next chunk with short timeout
        chunk = await client.get_next_video_chunk(timeout=1.0)

        if chunk:
            chunk_count += 1
            total_bytes += chunk.size_bytes

            # Every 30 chunks (approx 1 sec), print lag stats
            if chunk_count % 30 == 0:
                stats = client.get_pipeline_stats()
                print(
                    f"  [Consumer] Rx {chunk_count} chunks | Lag: {stats.consumer_lag_chunks} | "
                    f"E2E Latency Est: {stats.total_e2e_estimate_ms:.1f}ms",
                )
        else:
            # Timeout implies no data or stream ended
            if not client.is_streaming and not client.is_connected:
                break
            # If still connected but no data, might be a quiet screen or lag
            await asyncio.sleep(0.01)

    print(f"\n[Consumer] Finished. Total chunks: {chunk_count}, Total bytes: {total_bytes / 1024:.1f} KB")
    return chunk_count, total_bytes


async def run_test(duration: int):
    """Main test logic."""
    host = os.environ.get("RDP_HOST", "")
    username = os.environ.get("RDP_USER", "")
    password = os.environ.get("RDP_PASS", "")

    if not host or not username or not password:
        print("ERROR: Set RDP_HOST, RDP_USER, RDP_PASS environment variables")
        return

    # Use a recording file to verify output
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    recording_path = f"test_recording_{session_id}.mp4"

    print(f"\nConnecting to {host} as {username}...")

    # Initialize client with recording enabled
    client = RDPClient(
        host,
        username=username,
        password=password,
        width=1920,
        height=1080,
        capture_fps=30,
        record_to=recording_path,
    )

    try:
        await client.connect()
        print("Connected! Video streaming should be active.")

        # Verify streaming state
        if not client.is_streaming:
            print("ERROR: Streaming is not active after connect!")
            return

        # Run consumer in parallel with some UI actions
        consumer_task = asyncio.create_task(consume_video_stream(client, duration))

        # Perform some simple actions to generate video changes
        print("\nPerforming UI actions to generate video content...")
        for i in range(5):
            await client.mouse_move(100 + i * 50, 100 + i * 50)
            await asyncio.sleep(0.5)
            await client.send_text("test")
            await asyncio.sleep(0.5)

        # Wait for consumer to finish duration
        await consumer_task

        # Check stats before disconnect
        stats = client.get_pipeline_stats()
        print("\nFinal Pipeline Stats:")
        print(f"  Frames Received: {stats.frames_received}")
        print(f"  Frames Encoded:  {stats.frames_encoded}")
        print(f"  Chunks Produced: {stats.chunks_produced}")
        print(f"  Queue Drops:     {stats.queue_drops}")

    finally:
        print("\nDisconnecting...")
        await client.disconnect()

    # Verify recording file
    if os.path.exists(recording_path):
        size_mb = os.path.getsize(recording_path) / (1024 * 1024)
        print(f"\n✅ Recording saved successfully: {recording_path} ({size_mb:.2f} MB)")
        # Clean up
        os.remove(recording_path)
    else:
        print(f"\n❌ Recording file not found: {recording_path}")


def main():
    duration = int(os.environ.get("DURATION", "10"))

    print("=" * 60)
    print("     DISPLAY PIPELINE E2E TEST")
    print("=" * 60)

    asyncio.run(run_test(duration))


if __name__ == "__main__":
    main()
