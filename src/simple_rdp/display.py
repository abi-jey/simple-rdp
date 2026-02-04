"""
Display - Handles screen capture and video encoding from RDP sessions.

Provides a Display class that manages:
- Screen buffer (PIL Image of current screen state)
- Screenshot capture
- Raw frame buffer for video
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
from typing import IO

from PIL import Image

logger = getLogger(__name__)


def _create_default_pointer() -> Image.Image:
    """
    Create a default arrow pointer image.

    Returns a 16x24 pixel white arrow cursor with black outline,
    similar to the standard Windows arrow cursor.
    """
    # Arrow cursor bitmap (16x24 pixels)
    # 0 = transparent, 1 = black (outline), 2 = white (fill)
    cursor_data = [
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 2, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 2, 2, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0, 0, 0, 0],
        [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0, 0, 0],
        [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0, 0],
        [1, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 0, 0, 0],
        [1, 2, 2, 2, 1, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 2, 1, 0, 1, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 1, 0, 0, 1, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0],
        [1, 1, 0, 0, 0, 0, 1, 2, 2, 1, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0, 1, 2, 2, 1, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0],
    ]

    # Color mapping: (R, G, B, A)
    colors = {
        0: (0, 0, 0, 0),  # Transparent
        1: (0, 0, 0, 255),  # Black outline
        2: (255, 255, 255, 255),  # White fill
    }

    width = len(cursor_data[0])
    height = len(cursor_data)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    for y, row in enumerate(cursor_data):
        for x, pixel in enumerate(row):
            img.putpixel((x, y), colors[pixel])

    return img


# Default pointer (lazy-loaded singleton)
_DEFAULT_POINTER: Image.Image | None = None


def _get_default_pointer() -> Image.Image:
    """Get the default pointer image (lazy-loaded singleton)."""
    global _DEFAULT_POINTER
    if _DEFAULT_POINTER is None:
        _DEFAULT_POINTER = _create_default_pointer()
    return _DEFAULT_POINTER


@dataclass
class ScreenBuffer:
    """Represents a captured screen frame."""

    width: int
    height: int
    data: bytes
    format: str = "RGB"
    timestamp: float = field(default_factory=time.time)  # Wall-clock time

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
    Manages screen capture and video encoding.

    Features:
    - Screen buffer (PIL Image representing current screen state)
    - Screenshot capture and saving
    - Raw frame buffer (stores uncompressed RGB data for speed)
    - Live ffmpeg encoding to H.264 video stream
    - Async video output queue with configurable size limit
    - Automatic old data eviction when buffer exceeds limit
    """

    # Default buffer limits
    DEFAULT_MAX_VIDEO_BUFFER_MB = 100
    DEFAULT_RAW_BUFFER_SECONDS = 10  # Keep ~10 seconds of raw frames

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        max_video_buffer_mb: float = DEFAULT_MAX_VIDEO_BUFFER_MB,
        max_raw_frames: int | None = None,
    ) -> None:
        """
        Initialize the display manager.

        Args:
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Target frames per second for video encoding.
            max_video_buffer_mb: Maximum video buffer size in MB before eviction.
            max_raw_frames: Maximum raw frames to buffer. Defaults to fps * 10 (~10 seconds).
        """
        self._width = width
        self._height = height
        self._fps = fps
        self._max_video_buffer_bytes = int(max_video_buffer_mb * 1024 * 1024)
        # Default to ~10 seconds of buffer based on fps
        self._max_raw_frames = max_raw_frames if max_raw_frames is not None else fps * self.DEFAULT_RAW_BUFFER_SECONDS

        # Screen buffers:
        # - _screen_buffer: raw screen state from RDP bitmap updates (no pointer)
        # - _consumer_buffer: screen + pointer composited (for screenshots/video)
        self._screen_buffer: Image.Image | None = None
        self._consumer_buffer: Image.Image | None = None
        self._consumer_buffer_dirty: bool = True  # Needs redraw
        self._screen_lock = asyncio.Lock()

        # Pointer state and rate limiting
        self._pointer_x: int = 0
        self._pointer_y: int = 0
        self._pointer_visible: bool = True
        self._pointer_image: Image.Image | None = None
        self._pointer_hotspot: tuple[int, int] = (0, 0)
        self._last_pointer_update: float = 0.0
        self._pointer_update_interval: float = 1.0 / fps  # Cap to FPS

        # Raw frame storage (deque for O(1) append and popleft)
        self._raw_frames: deque[ScreenBuffer] = deque(maxlen=max_raw_frames)
        self._frame_count = 0

        # Video encoding state
        self._ffmpeg_process: subprocess.Popen[bytes] | None = None
        self._encoding_task: asyncio.Task[None] | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None  # For ffmpeg error logging
        self._streaming = False  # Encoding to memory buffer for streaming
        self._shutting_down = False  # Flag to prevent writes during shutdown
        self._recording_to_file = False  # Recording taps into streaming output
        self._recording_path: str | None = None  # Path for file recording
        self._recording_file: IO[bytes] | None = None  # File handle for recording

        # Video output buffer (chunked encoded video for streaming)
        self._video_chunks: deque[VideoChunk] = deque()
        self._video_buffer_size = 0
        self._chunk_sequence = 0

        # Async queue for new chunks (for consumers)
        self._video_queue: Queue[VideoChunk] = Queue(maxsize=100)  # Bounded queue

        # Session and recording timing (wall-clock times)
        self._session_start_time: float = time.time()  # When display was created
        self._recording_start_time: float | None = None
        self._first_frame_time: float | None = None

        # Diagnostic tracking
        self._last_diag_time: float = 0.0
        self._diag_interval: float = 5.0  # Log diagnostics every 5 seconds
        self._frames_since_diag: int = 0
        self._encode_time_total: float = 0.0
        self._queue_drops: int = 0

        # Stats
        self._stats = {
            "frames_received": 0,
            "frames_encoded": 0,
            "bytes_encoded": 0,
            "chunks_evicted": 0,
            "encoding_errors": 0,
            "bitmaps_applied": 0,
            "pointer_updates": 0,
            "pointer_updates_throttled": 0,
            "queue_drops": 0,
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
    def max_raw_frames(self) -> int:
        """Maximum number of raw frames that can be buffered."""
        return self._max_raw_frames

    @property
    def raw_buffer_seconds(self) -> float:
        """Current raw frame buffer size in seconds (based on fps)."""
        return len(self._raw_frames) / self._fps if self._fps > 0 else 0.0

    @property
    def max_raw_buffer_seconds(self) -> float:
        """Maximum raw frame buffer size in seconds."""
        return self._max_raw_frames / self._fps if self._fps > 0 else 0.0

    @property
    def video_buffer_size_mb(self) -> float:
        return self._video_buffer_size / (1024 * 1024)

    @property
    def stats(self) -> dict[str, int]:
        return self._stats.copy()

    @property
    def is_streaming(self) -> bool:
        """True if streaming to memory buffer is active."""
        return self._streaming and self._ffmpeg_process is not None

    @property
    def is_file_recording(self) -> bool:
        """True if recording directly to file is active."""
        return self._recording_to_file

    @property
    def is_encoding(self) -> bool:
        """True if any encoding (streaming or file recording) is active."""
        return self._ffmpeg_process is not None

    @property
    def recording_duration_seconds(self) -> float:
        """Return how long encoding (streaming or file) has been active."""
        if self._recording_start_time is None:
            return 0.0
        return time.time() - self._recording_start_time

    @property
    def session_duration_seconds(self) -> float:
        """Return how long since the session started (wall-clock)."""
        return time.time() - self._session_start_time

    @property
    def session_start_time(self) -> float:
        """Return the wall-clock timestamp when the session started."""
        return self._session_start_time

    @property
    def buffer_time_range(self) -> tuple[float, float]:
        """
        Return the time range of buffered frames as (oldest_time, newest_time).

        Times are relative to session start (in seconds).
        Returns (0, 0) if no frames are buffered.
        """
        if not self._raw_frames:
            return (0.0, 0.0)
        oldest = self._raw_frames[0].timestamp - self._session_start_time
        newest = self._raw_frames[-1].timestamp - self._session_start_time
        return (oldest, newest)

    @property
    def buffer_delay_seconds(self) -> float:
        """
        Return the delay between oldest buffered frame and now.

        This indicates how far behind real-time the buffer is.
        Returns 0 if no frames are buffered.
        """
        if not self._raw_frames:
            return 0.0
        oldest_frame = self._raw_frames[0]
        return time.time() - oldest_frame.timestamp

    @property
    def effective_fps(self) -> float:
        """
        Return the actual frames per second being received.

        Calculated from frames received since first frame.
        Returns 0 if not enough data.
        """
        if self._first_frame_time is None or self._stats["frames_received"] < 2:
            return 0.0
        elapsed = time.time() - self._first_frame_time
        if elapsed <= 0:
            return 0.0
        return self._stats["frames_received"] / elapsed

    @property
    def screen_buffer(self) -> Image.Image | None:
        """Return the current screen buffer (may be None if not initialized)."""
        return self._screen_buffer

    def initialize_screen(self) -> None:
        """Initialize the screen buffers with black images."""
        self._screen_buffer = Image.new("RGB", (self._width, self._height), (0, 0, 0))
        self._consumer_buffer = Image.new("RGB", (self._width, self._height), (0, 0, 0))
        self._consumer_buffer_dirty = True

    def _update_consumer_buffer(self) -> None:
        """Update the consumer buffer with screen + pointer composited."""
        if self._screen_buffer is None:
            return

        # Reuse existing consumer buffer if same size, otherwise create new
        if self._consumer_buffer is None or self._consumer_buffer.size != self._screen_buffer.size:
            self._consumer_buffer = Image.new("RGB", (self._width, self._height), (0, 0, 0))

        # Paste screen buffer onto consumer buffer (faster than copy())
        self._consumer_buffer.paste(self._screen_buffer, (0, 0))

        # Composite pointer if visible
        if self._pointer_visible:
            # Use custom pointer if available, otherwise use default arrow
            pointer = self._pointer_image if self._pointer_image is not None else _get_default_pointer()
            hotspot = self._pointer_hotspot if self._pointer_image is not None else (0, 0)

            # Calculate position adjusted for hotspot
            px = self._pointer_x - hotspot[0]
            py = self._pointer_y - hotspot[1]

            # Only paste if within bounds
            if -pointer.width < px < self._width and -pointer.height < py < self._height:
                try:
                    # Use alpha composite if pointer has alpha channel
                    if pointer.mode == "RGBA":
                        self._consumer_buffer.paste(pointer, (px, py), pointer)
                    else:
                        self._consumer_buffer.paste(pointer, (px, py))
                except Exception as e:
                    logger.debug(f"Error compositing pointer: {e}")

        self._consumer_buffer_dirty = False

    def update_pointer(
        self,
        x: int | None = None,
        y: int | None = None,
        visible: bool | None = None,
        image: Image.Image | None = None,
        hotspot: tuple[int, int] | None = None,
    ) -> bool:
        """
        Update pointer state with FPS-based rate limiting.

        Args:
            x: New X position (or None to keep current)
            y: New Y position (or None to keep current)
            visible: Visibility state (or None to keep current)
            image: New pointer image (or None to keep current)
            hotspot: New hotspot (or None to keep current)

        Returns:
            True if update was applied, False if throttled
        """
        now = time.time()

        # Check rate limit for position-only updates (combine conditions per SIM102)
        is_position_only = image is None and hotspot is None and visible is None
        if is_position_only and now - self._last_pointer_update < self._pointer_update_interval:
            self._stats["pointer_updates_throttled"] += 1
            return False

        # Apply updates
        if x is not None:
            self._pointer_x = x
        if y is not None:
            self._pointer_y = y
        if visible is not None:
            self._pointer_visible = visible
        if image is not None:
            self._pointer_image = image
        if hotspot is not None:
            self._pointer_hotspot = hotspot

        self._last_pointer_update = now
        self._consumer_buffer_dirty = True
        self._stats["pointer_updates"] += 1
        return True

    async def screenshot(self) -> Image.Image:
        """
        Capture the current screen with pointer composited.

        Returns:
            PIL Image of the current screen state with pointer overlay.
        """
        async with self._screen_lock:
            if self._screen_buffer is None:
                return Image.new("RGB", (self._width, self._height), (0, 0, 0))

            # Update consumer buffer if dirty
            if self._consumer_buffer_dirty or self._consumer_buffer is None:
                self._update_consumer_buffer()

            # At this point consumer_buffer is guaranteed to be set by _update_consumer_buffer
            assert self._consumer_buffer is not None
            return self._consumer_buffer.copy()

    async def save_screenshot(self, path: str) -> None:
        """
        Save a screenshot to a file.

        Args:
            path: File path to save the screenshot.
        """
        img = await self.screenshot()
        img.save(path)
        logger.info(f"Screenshot saved to {path}")

    async def apply_bitmap(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        data: bytes,
        bpp: int = 32,
    ) -> None:
        """
        Apply a bitmap update to the screen buffer.

        This is called by the RDP client when it receives bitmap updates
        from the server.

        Args:
            x: Destination X coordinate.
            y: Destination Y coordinate.
            width: Bitmap width.
            height: Bitmap height.
            data: Raw bitmap data (already decompressed, RGB format).
            bpp: Bits per pixel of the source data.
        """
        async with self._screen_lock:
            if self._screen_buffer is None:
                self.initialize_screen()

            # After initialization, screen_buffer should exist
            if self._screen_buffer is None:
                return

            try:
                # Determine raw mode based on bpp
                if bpp == 32:
                    rawmode = "BGRX"
                    expected_size = width * height * 4
                elif bpp == 24:
                    rawmode = "BGR"
                    expected_size = width * height * 3
                elif bpp in (15, 16):
                    rawmode = "BGR;16" if bpp == 16 else "BGR;15"
                    expected_size = width * height * 2
                elif bpp == 8:
                    rawmode = "P"
                    expected_size = width * height
                else:
                    logger.debug(f"Unsupported bpp: {bpp}")
                    return

                if len(data) < expected_size:
                    logger.debug(f"Bitmap data too short: {len(data)} < {expected_size}")
                    return

                # Create image from raw data
                img = Image.frombytes("RGB", (width, height), data[:expected_size], "raw", rawmode)

                # Flip vertically (RDP sends bottom-up)
                img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

                # Paste onto screen buffer
                self._screen_buffer.paste(img, (x, y))
                self._stats["bitmaps_applied"] += 1
                self._consumer_buffer_dirty = True  # Mark for redraw with pointer

                # Note: Raw frame capture is handled by RDPClient's capture loop at fixed FPS
                # If encoding is active, frames are sent to ffmpeg in add_frame()

            except Exception as e:
                logger.debug(f"Error applying bitmap: {e}")

    async def start_streaming(self) -> None:
        """
        Start streaming video to memory buffer.

        Frames are encoded to fragmented MP4 format and stored in chunks for
        live consumption via get_next_video_chunk().

        This is ideal for real-time streaming to network consumers.
        For recording directly to a file, use start_file_recording().
        """
        if self._streaming or self._recording_to_file:
            logger.warning("Encoding already active")
            return

        self._streaming = True
        self._recording_start_time = time.time()  # Wall-clock time
        self._first_frame_time = None  # Reset for new session

        # Start ffmpeg process
        # Input: raw RGB24 frames via stdin
        # Output: H.264 in fragmented MP4 for MSE browser playback
        # Key settings for low-latency streaming:
        # - frag_keyframe: new fragment at each keyframe
        # - empty_moov: no samples in initial moov (required for streaming)
        # - frag_every_frame: fragment on every frame for lowest latency
        # - -g 1: keyframe on EVERY frame initially to get video flowing fast
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
            "zerolatency",  # Critical: outputs NALUs immediately
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "28",  # Slightly lower quality for faster encoding
            "-g",
            "15",  # Keyframe every 15 frames (0.5 sec at 30fps) - faster initial video
            "-keyint_min",
            "15",  # Minimum keyframe interval
            "-bf",
            "0",  # No B-frames
            "-flags",
            "+cgop",  # Closed GOP
            "-f",
            "mp4",
            "-movflags",
            "frag_keyframe+empty_moov+default_base_moof",
            "-frag_duration",
            "33333",  # ~33ms fragments (one frame at 30fps)
            "-min_frag_duration",
            "0",  # Allow very small fragments
            "pipe:1",  # stdout
        ]

        logger.info(f"Starting streaming encoder: {self._width}x{self._height} @ {self._fps}fps (fMP4)")

        # Calculate optimal buffer size (one frame worth of raw RGB data)
        frame_size = self._width * self._height * 3

        self._ffmpeg_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # Capture stderr for debugging
            bufsize=frame_size,  # Buffer one frame for better throughput
        )

        # Start reader task to consume ffmpeg output
        self._reader_task = asyncio.create_task(self._read_video_output())

        # Start stderr reader for debugging
        self._stderr_task = asyncio.create_task(self._read_ffmpeg_stderr())

        logger.info("Streaming encoder started")

    async def start_file_recording(self, path: str) -> None:
        """
        Start recording video to a file.

        Recording taps into the streaming output - chunks are written to both
        the memory buffer and the file. If streaming is not active, it will
        be started automatically.

        This allows unlimited recording duration (no memory limits) while
        optionally also streaming chunks for live consumption.

        Args:
            path: Output file path (e.g., "recording.mp4").
                  Should use .ts extension for MPEG-TS format.

        Note:
            Recording uses the same MPEG-TS format as streaming.
            For MP4, use save_buffer_as_video() after stopping.
        """
        if self._recording_to_file:
            logger.warning("File recording already active")
            return

        # Start streaming if not already active (we tap into its output)
        if not self._streaming:
            await self.start_streaming()

        # Open file for writing (we manage the file handle lifecycle manually)
        try:
            self._recording_file = open(path, "wb")  # noqa: SIM115
            self._recording_to_file = True
            self._recording_path = path
            logger.info(f"File recording started: {path}")
        except Exception as e:
            logger.error(f"Failed to start file recording: {e}")
            raise

    async def stop_streaming(self) -> None:
        """Stop streaming to memory buffer."""
        if not self._streaming:
            return

        # Set shutting_down first to prevent any new writes
        self._shutting_down = True
        self._streaming = False
        await self._stop_ffmpeg()
        self._shutting_down = False  # Reset for potential restart
        logger.info("Streaming stopped")

    async def stop_file_recording(self) -> None:
        """Stop file recording.

        This closes the recording file but does NOT stop streaming.
        Streaming continues independently until stop_streaming() is called.
        """
        if not self._recording_to_file:
            return

        path = self._recording_path
        self._recording_to_file = False
        self._recording_path = None

        # Close the recording file
        if self._recording_file:
            try:
                self._recording_file.close()
            except Exception as e:
                logger.debug(f"Error closing recording file: {e}")
            self._recording_file = None

        logger.info(f"File recording stopped: {path}")

    async def _stop_ffmpeg(self) -> None:
        """Internal: stop the ffmpeg process and close any open recording file."""
        self._recording_start_time = None

        # Close recording file if open
        if self._recording_file:
            try:
                self._recording_file.close()
            except Exception as e:
                logger.debug(f"Error closing recording file: {e}")
            self._recording_file = None
            self._recording_to_file = False
            self._recording_path = None

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

        if self._stderr_task:
            self._stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stderr_task
            self._stderr_task = None

    async def _read_ffmpeg_stderr(self) -> None:
        """Read and log ffmpeg stderr for debugging."""
        loop = asyncio.get_event_loop()

        def _read_stderr() -> bytes:
            if self._ffmpeg_process and self._ffmpeg_process.stderr:
                return self._ffmpeg_process.stderr.readline()
            return b""

        while self._streaming and self._ffmpeg_process:
            try:
                line = await loop.run_in_executor(None, _read_stderr)
                if line:
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded:
                        logger.debug(f"ffmpeg: {decoded}")
                else:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception:
                break

    async def add_frame(self, image: Image.Image) -> None:
        """
        Add a frame from a PIL Image.

        This converts the image to raw RGB bytes and stores it,
        then sends to ffmpeg for encoding. The pointer is composited
        onto the frame before encoding.

        Args:
            image: PIL Image to add (will be converted to RGB if needed).
        """
        # Update consumer buffer with pointer composited
        if self._consumer_buffer_dirty or self._consumer_buffer is None:
            self._update_consumer_buffer()

        # Use consumer buffer (with pointer) if available, otherwise original image
        frame_image = self._consumer_buffer if self._consumer_buffer is not None else image

        # Convert to RGB if needed and get raw bytes
        if frame_image.mode != "RGB":
            frame_image = frame_image.convert("RGB")

        raw_data = frame_image.tobytes()

        await self.add_raw_frame(raw_data)

    async def add_raw_frame(self, data: bytes) -> None:
        """
        Add a raw RGB frame.

        Args:
            data: Raw RGB24 bytes (width * height * 3 bytes).
        """
        timestamp = time.time()  # Wall-clock time for accurate seeking

        # Track first frame time for effective FPS calculation
        if self._first_frame_time is None:
            self._first_frame_time = timestamp

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

        # Send to ffmpeg if encoding (skip if shutting down or not streaming)
        if self._streaming and not self._shutting_down and self._ffmpeg_process and self._ffmpeg_process.stdin:
            try:
                encode_start = time.perf_counter()
                # Use run_in_executor to avoid blocking the event loop
                loop = asyncio.get_event_loop()
                stdin = self._ffmpeg_process.stdin
                await loop.run_in_executor(None, lambda: (stdin.write(data), stdin.flush()))
                encode_time = time.perf_counter() - encode_start
                self._encode_time_total += encode_time
                self._frames_since_diag += 1
                self._stats["frames_encoded"] += 1

                # Log diagnostics periodically
                now = time.time()
                if now - self._last_diag_time >= self._diag_interval:
                    self._log_diagnostics()
                    self._last_diag_time = now

            except (BrokenPipeError, OSError):
                # Expected during shutdown - silently ignore
                pass

    def _log_diagnostics(self) -> None:
        """Log backend pipeline diagnostics."""
        if self._frames_since_diag == 0:
            return

        avg_encode_ms = (self._encode_time_total / self._frames_since_diag) * 1000
        target_frame_time_ms = 1000 / self._fps

        # Calculate if we're ahead or behind
        headroom_ms = target_frame_time_ms - avg_encode_ms
        status = "✅ AHEAD" if headroom_ms > 0 else "⚠️ BEHIND"

        queue_size = self._video_queue.qsize()
        queue_status = "ok" if queue_size < 50 else "⚠️ HIGH" if queue_size < 90 else "🔴 FULL"

        logger.info(
            f"📊 Backend: {status} by {abs(headroom_ms):.1f}ms | "
            f"encode={avg_encode_ms:.1f}ms/frame | "
            f"target={target_frame_time_ms:.1f}ms | "
            f"queue={queue_size}/100 ({queue_status}) | "
            f"drops={self._stats['queue_drops']} | "
            f"fps_in={self._frames_since_diag / self._diag_interval:.1f}"
        )

        # Reset counters
        self._frames_since_diag = 0
        self._encode_time_total = 0.0

    async def _read_video_output(self) -> None:
        """Read encoded video from ffmpeg stdout, buffer it, and write to file if recording."""
        CHUNK_SIZE = 65536  # 64KB chunks
        loop = asyncio.get_event_loop()

        def _read_chunk() -> bytes:
            """Helper to read a chunk from ffmpeg stdout."""
            if self._ffmpeg_process and self._ffmpeg_process.stdout:
                return self._ffmpeg_process.stdout.read(CHUNK_SIZE)
            return b""

        while self._streaming and self._ffmpeg_process:
            try:
                # Use run_in_executor to read without blocking the event loop
                if self._ffmpeg_process and self._ffmpeg_process.stdout:
                    # Non-blocking read using executor
                    data = await loop.run_in_executor(None, _read_chunk)
                else:
                    data = b""

                if not data:
                    await asyncio.sleep(0.01)
                    continue

                # Write to file if recording is active
                if self._recording_to_file and self._recording_file:
                    try:
                        self._recording_file.write(data)
                        self._recording_file.flush()
                    except Exception as e:
                        logger.debug(f"Error writing to recording file: {e}")

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
                    self._stats["queue_drops"] += 1
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
            Each frame has a wall-clock timestamp for true timing.
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

    async def save_buffer_as_video(self, path: str, use_true_timing: bool = True) -> bool:
        """
        Encode the raw frame buffer to a video file.

        This saves the current in-memory raw frame buffer (rolling window) to
        a video file. Frames older than max_raw_frames have been discarded.

        When use_true_timing=True (default), the video duration will match
        the actual elapsed wall-clock time between frames. This means if
        frames were dropped, the video still has correct real-world timing.

        For full session recording without buffer limits, use start_file_recording().

        Args:
            path: Output file path.
            use_true_timing: If True, video duration matches real elapsed time.
                             If False, uses fixed fps (may not match real time).

        Returns:
            True if successful.
        """
        if not self._raw_frames:
            logger.warning("No frames to save")
            return False

        frames = list(self._raw_frames)

        # Calculate actual elapsed time and effective FPS for true timing
        if len(frames) >= 2:
            elapsed_time = frames[-1].timestamp - frames[0].timestamp
            actual_fps = len(frames) / elapsed_time if elapsed_time > 0 else self._fps
        else:
            elapsed_time = 0
            actual_fps = self._fps

        # Use actual fps for true timing, or configured fps
        output_fps = actual_fps if use_true_timing else self._fps

        logger.info(
            f"Saving {len(frames)} frames, elapsed: {elapsed_time:.2f}s, "
            f"fps: {output_fps:.1f} (true_timing={use_true_timing})"
        )

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
            str(output_fps),
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
                for frame in frames:
                    process.stdin.write(frame.data)
                process.stdin.close()

            process.wait()

            logger.info(
                f"Saved video to {path} (duration: {elapsed_time:.2f}s, {len(frames)} frames at {output_fps:.1f} fps)"
            )
            return True
        except Exception as e:
            logger.error(f"Error saving video: {e}")
            return False

    def print_stats(self) -> None:
        """Print current statistics."""
        print(f"\n{'=' * 50}")
        print("           DISPLAY STATS")
        print(f"{'=' * 50}")
        print(f"🖥️  Screen buffer:         {'Initialized' if self._screen_buffer else 'Not initialized'}")
        raw_info = f"{self.raw_frame_count} / {self.max_raw_frames}"
        raw_secs = f"({self.raw_buffer_seconds:.1f}s / {self.max_raw_buffer_seconds:.1f}s)"
        print(f"📷 Raw frames in buffer:  {raw_info} {raw_secs}")
        print(f"   Total frames received: {self._stats['frames_received']}")
        print(f"   Bitmaps applied:       {self._stats['bitmaps_applied']}")
        print(f"⏱️  Recording duration:    {self.recording_duration_seconds:.1f}s")
        print(f"   Effective FPS:         {self.effective_fps:.1f}")
        print(f"   Buffer delay:          {self.buffer_delay_seconds:.2f}s")
        print(f"🎬 Frames encoded:        {self._stats['frames_encoded']}")
        print(f"💾 Video buffer:          {self.video_buffer_size_mb:.2f} MB")
        print(f"   Bytes encoded:         {self._stats['bytes_encoded'] / 1024 / 1024:.2f} MB")
        print(f"   Chunks evicted:        {self._stats['chunks_evicted']}")
        print(f"❌ Encoding errors:       {self._stats['encoding_errors']}")
        print(f"{'=' * 50}\n")
