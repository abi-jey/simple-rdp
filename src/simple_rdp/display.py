"""
Screen Capture - Handles screen data from RDP sessions.

Provides a Display class that manages:
- Raw frame buffer (no PNG encoding overhead)
- Live ffmpeg video encoding via subprocess
- Async video output queue with 100MB cap
"""

from __future__ import annotations

import asyncio
import contextlib
import subprocess
import time
from asyncio import Queue
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from logging import getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

logger = getLogger(__name__)


@dataclass
class ScreenBuffer:
    """Represents a captured screen frame."""

    width: int
    height: int
    data: bytes
    format: str = "RGB"
    timestamp: float = field(default_factory=time.perf_counter)

    @property
    def size_bytes(self) -> int:
        """Return the size of the raw data in bytes."""
        return len(self.data)


@dataclass
class VideoChunk:
    """A chunk of encoded video data."""

    data: bytes
    timestamp: float
    sequence: int

    @property
    def size_bytes(self) -> int:
        return len(self.data)


class Display:
    """
    Manages screen capture with live video encoding.

    Features:
    - Raw frame buffer (stores uncompressed RGB data for speed)
    - Live ffmpeg encoding to H.264 video stream
    - Async video output queue with configurable size limit
    - Automatic old data eviction when buffer exceeds limit
    """

    # Default buffer limits
    DEFAULT_MAX_VIDEO_BUFFER_MB = 100
    DEFAULT_MAX_RAW_FRAMES = 300  # ~3 seconds at 100fps, ~1.5GB for 1080p

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        max_video_buffer_mb: float = DEFAULT_MAX_VIDEO_BUFFER_MB,
        max_raw_frames: int = DEFAULT_MAX_RAW_FRAMES,
    ) -> None:
        """
        Initialize the display manager.

        Args:
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Target frames per second for video encoding.
            max_video_buffer_mb: Maximum video buffer size in MB before eviction.
            max_raw_frames: Maximum number of raw frames to keep in memory.
        """
        self._width = width
        self._height = height
        self._fps = fps
        self._max_video_buffer_bytes = int(max_video_buffer_mb * 1024 * 1024)
        self._max_raw_frames = max_raw_frames

        # Raw frame storage (deque for O(1) append and popleft)
        self._raw_frames: deque[ScreenBuffer] = deque(maxlen=max_raw_frames)
        self._frame_count = 0

        # Video encoding state
        self._ffmpeg_process: subprocess.Popen[bytes] | None = None
        self._encoding_task: asyncio.Task[None] | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._running = False

        # Video output buffer (chunked encoded video)
        self._video_chunks: deque[VideoChunk] = deque()
        self._video_buffer_size = 0
        self._chunk_sequence = 0

        # Async queue for new chunks (for consumers)
        self._video_queue: Queue[VideoChunk] = Queue()

        # Stats
        self._stats = {
            "frames_received": 0,
            "frames_encoded": 0,
            "bytes_encoded": 0,
            "chunks_evicted": 0,
            "encoding_errors": 0,
        }

        # Lock for thread-safe frame access
        self._frame_lock = asyncio.Lock()

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def fps(self) -> int:
        return self._fps

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def raw_frame_count(self) -> int:
        return len(self._raw_frames)

    @property
    def video_buffer_size_mb(self) -> float:
        return self._video_buffer_size / (1024 * 1024)

    @property
    def stats(self) -> dict[str, int]:
        return self._stats.copy()

    @property
    def is_encoding(self) -> bool:
        return self._running and self._ffmpeg_process is not None

    async def start_encoding(self) -> None:
        """Start the ffmpeg encoding process."""
        if self._running:
            return

        self._running = True

        # Start ffmpeg process
        # Input: raw RGB24 frames via stdin
        # Output: H.264 fragmented MP4 to stdout (for streaming)
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{self._width}x{self._height}",
            "-r",
            str(self._fps),
            "-i",
            "pipe:0",  # stdin
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",  # Fastest encoding
            "-tune",
            "zerolatency",  # Low latency
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "23",
            "-f",
            "mpegts",  # MPEG-TS for streaming (self-contained chunks)
            "pipe:1",  # stdout
        ]

        logger.info(f"Starting ffmpeg encoder: {self._width}x{self._height} @ {self._fps}fps")

        self._ffmpeg_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # Suppress ffmpeg logs
            bufsize=0,  # Unbuffered
        )

        # Start reader task to consume ffmpeg output
        self._reader_task = asyncio.create_task(self._read_video_output())

        logger.info("Ffmpeg encoder started")

    async def stop_encoding(self) -> None:
        """Stop the ffmpeg encoding process."""
        self._running = False

        if self._ffmpeg_process:
            # Close stdin to signal EOF
            if self._ffmpeg_process.stdin:
                try:
                    self._ffmpeg_process.stdin.close()
                except Exception as e:
                    logger.debug(f"Error closing ffmpeg stdin (expected during shutdown): {e}")

            # Wait for process to finish
            try:
                self._ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ffmpeg_process.kill()

            self._ffmpeg_process = None

        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

        logger.info("Ffmpeg encoder stopped")

    async def add_frame(self, image: Image.Image) -> None:
        """
        Add a frame from a PIL Image.

        This converts the image to raw RGB bytes and stores it,
        then sends to ffmpeg for encoding.

        Args:
            image: PIL Image to add (will be converted to RGB if needed).
        """
        # Convert to RGB if needed and get raw bytes
        if image.mode != "RGB":
            image = image.convert("RGB")

        raw_data = image.tobytes()

        await self.add_raw_frame(raw_data)

    async def add_raw_frame(self, data: bytes) -> None:
        """
        Add a raw RGB frame.

        Args:
            data: Raw RGB24 bytes (width * height * 3 bytes).
        """
        timestamp = time.perf_counter()

        frame = ScreenBuffer(
            width=self._width,
            height=self._height,
            data=data,
            format="RGB",
            timestamp=timestamp,
        )

        async with self._frame_lock:
            self._raw_frames.append(frame)
            self._frame_count += 1
            self._stats["frames_received"] += 1

        # Send to ffmpeg if encoding
        if self._ffmpeg_process and self._ffmpeg_process.stdin:
            try:
                self._ffmpeg_process.stdin.write(data)
                self._ffmpeg_process.stdin.flush()
                self._stats["frames_encoded"] += 1
            except (BrokenPipeError, OSError) as e:
                self._stats["encoding_errors"] += 1
                logger.debug(f"Error writing to ffmpeg: {e}")

    async def _read_video_output(self) -> None:
        """Read encoded video from ffmpeg stdout and buffer it."""
        CHUNK_SIZE = 65536  # 64KB chunks

        while self._running and self._ffmpeg_process:
            try:
                # Read in a thread to avoid blocking
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(
                    None,
                    lambda: self._ffmpeg_process.stdout.read(CHUNK_SIZE)
                    if self._ffmpeg_process and self._ffmpeg_process.stdout
                    else b"",
                )

                if not data:
                    await asyncio.sleep(0.01)
                    continue

                # Create chunk
                chunk = VideoChunk(
                    data=data,
                    timestamp=time.perf_counter(),
                    sequence=self._chunk_sequence,
                )
                self._chunk_sequence += 1

                # Add to buffer
                self._video_chunks.append(chunk)
                self._video_buffer_size += chunk.size_bytes
                self._stats["bytes_encoded"] += chunk.size_bytes

                # Put in queue for consumers (drop if full - intentional back-pressure)
                try:
                    self._video_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    logger.debug("Video queue full, dropping chunk (back-pressure)")

                # Evict old chunks if over limit
                while self._video_buffer_size > self._max_video_buffer_bytes and self._video_chunks:
                    old_chunk = self._video_chunks.popleft()
                    self._video_buffer_size -= old_chunk.size_bytes
                    self._stats["chunks_evicted"] += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Error reading video output: {e}")
                await asyncio.sleep(0.01)

    def get_latest_frame(self) -> ScreenBuffer | None:
        """Get the most recent raw frame."""
        if self._raw_frames:
            return self._raw_frames[-1]
        return None

    def get_frames(self, count: int | None = None) -> list[ScreenBuffer]:
        """
        Get recent raw frames.

        Args:
            count: Number of frames to get. None for all.

        Returns:
            List of ScreenBuffer frames (oldest first).
        """
        if count is None:
            return list(self._raw_frames)
        return list(self._raw_frames)[-count:]

    def get_video_chunks(self) -> list[VideoChunk]:
        """Get all buffered video chunks."""
        return list(self._video_chunks)

    async def get_next_video_chunk(self, timeout: float = 1.0) -> VideoChunk | None:
        """
        Wait for and return the next video chunk.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            VideoChunk or None if timeout.
        """
        try:
            return await asyncio.wait_for(self._video_queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    def clear_raw_frames(self) -> None:
        """Clear all raw frames from buffer."""
        self._raw_frames.clear()

    def clear_video_chunks(self) -> None:
        """Clear all video chunks from buffer."""
        self._video_chunks.clear()
        self._video_buffer_size = 0

    async def save_video(self, path: str) -> bool:
        """
        Save all buffered video chunks to a file.

        Args:
            path: Output file path.

        Returns:
            True if successful.
        """
        try:
            with open(path, "wb") as f:
                for chunk in self._video_chunks:
                    f.write(chunk.data)
            logger.info(f"Saved {self.video_buffer_size_mb:.2f} MB video to {path}")
            return True
        except Exception as e:
            logger.error(f"Error saving video: {e}")
            return False

    async def save_raw_frames_as_video(self, path: str, fps: int | None = None) -> bool:
        """
        Encode raw frames to video file using ffmpeg.

        This is useful when not using live encoding.

        Args:
            path: Output file path.
            fps: Frames per second (default: self._fps).

        Returns:
            True if successful.
        """
        if not self._raw_frames:
            logger.warning("No frames to save")
            return False

        fps = fps or self._fps

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{self._width}x{self._height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "23",
            path,
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            if process.stdin:
                for frame in self._raw_frames:
                    process.stdin.write(frame.data)
                process.stdin.close()

            process.wait()

            logger.info(f"Saved {len(self._raw_frames)} frames to {path}")
            return True
        except Exception as e:
            logger.error(f"Error saving video: {e}")
            return False

    def print_stats(self) -> None:
        """Print current statistics."""
        print(f"\n{'=' * 50}")
        print("           DISPLAY STATS")
        print(f"{'=' * 50}")
        print(f"📷 Raw frames in buffer:  {self.raw_frame_count}")
        print(f"   Total frames received: {self._stats['frames_received']}")
        print(f"🎬 Frames encoded:        {self._stats['frames_encoded']}")
        print(f"💾 Video buffer:          {self.video_buffer_size_mb:.2f} MB")
        print(f"   Bytes encoded:         {self._stats['bytes_encoded'] / 1024 / 1024:.2f} MB")
        print(f"   Chunks evicted:        {self._stats['chunks_evicted']}")
        print(f"❌ Encoding errors:       {self._stats['encoding_errors']}")
        print(f"{'=' * 50}\n")
