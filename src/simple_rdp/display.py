"""
Display - Handles screen capture and video encoding from RDP sessions.

Provides a Display class that manages:
- Screen buffer (PIL Image of current screen state)
- Screenshot capture
- Live ffmpeg video encoding via subprocess
- Async video output queue for real-time streaming
- Automatic temp file recording with optional transcode on cleanup

Architecture:
    Bitmap Update → _raw_display_image (clean desktop)
                          ↓
                  _final_display_image (desktop + pointer)
                          ↓
                     add_frame()
                          ↓
                    ffmpeg stdin
                          ↓
                    ffmpeg stdout
                          ↓
              ┌───────────┴───────────┐
              ↓                       ↓
        _video_queue              temp .ts file
              ↓                       ↓
    get_next_video_chunk()      transcode to MP4
                                  (on cleanup)

Consumer Lag Detection:
    The video queue holds up to ~20 seconds of encoded video chunks.
    Use `consumer_lag_chunks` property to check how far behind a consumer is.
    A lag of >10 chunks indicates the consumer is falling behind.
    If the queue fills up, new chunks are dropped (back-pressure).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import subprocess
import tempfile
import time
from asyncio import Queue
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
class VideoChunk:
    """A chunk of encoded video data."""

    data: bytes
    timestamp: float
    sequence: int

    @property
    def size_bytes(self) -> int:
        return len(self.data)


@dataclass
class PipelineStats:
    """
    Statistics for the video encoding pipeline.

    These stats help diagnose latency and throughput issues in the
    bitmap → display → ffmpeg → output pipeline.

    Attributes:
        bitmap_to_buffer_ms: Average time to decompress and apply bitmap updates.
        frame_to_ffmpeg_ms: Average time to write a frame to ffmpeg stdin.
        ffmpeg_latency_ms: Estimated ffmpeg processing latency (input to output).
        total_e2e_estimate_ms: Estimated total end-to-end latency.
        frames_received: Total frames received from capture loop.
        frames_encoded: Total frames written to ffmpeg.
        chunks_produced: Total video chunks produced by ffmpeg.
        queue_drops: Number of chunks dropped due to full queue.
        bitmaps_applied: Number of bitmap updates applied to display.
        consumer_lag_chunks: Current number of chunks waiting in queue.
    """

    bitmap_to_buffer_ms: float = 0.0
    frame_to_ffmpeg_ms: float = 0.0
    ffmpeg_latency_ms: float = 0.0
    total_e2e_estimate_ms: float = field(init=False)
    frames_received: int = 0
    frames_encoded: int = 0
    chunks_produced: int = 0
    queue_drops: int = 0
    bitmaps_applied: int = 0
    consumer_lag_chunks: int = 0

    def __post_init__(self) -> None:
        self.total_e2e_estimate_ms = self.bitmap_to_buffer_ms + self.frame_to_ffmpeg_ms + self.ffmpeg_latency_ms


class Display:
    """
    Manages screen capture and video encoding.

    Features:
    - Screen buffer (PIL Image representing current screen state)
    - Screenshot capture and saving
    - Live ffmpeg encoding to fragmented MP4 video stream
    - Async video output queue for real-time streaming consumers
    - Automatic temp file recording for full session capture
    - Optional transcode to MP4 on cleanup

    Video Pipeline:
        The display maintains two image buffers:
        - _raw_display_image: The clean desktop image from RDP bitmap updates
        - _final_display_image: The desktop with pointer composited (for output)

        When streaming is active, frames are:
        1. Captured at fixed FPS from _final_display_image
        2. Written to ffmpeg stdin as raw RGB
        3. Encoded to H.264 fragmented MP4
        4. Output chunks are written to both:
           - A temp .ts file (always, for full session recording)
           - An async queue (for real-time streaming via get_next_video_chunk())

    Consumer Lag:
        The video queue can hold ~600 chunks (~20 seconds at 30fps).
        Use `consumer_lag_chunks` to monitor how far behind a consumer is:
        - 0-10 chunks: Consumer is keeping up well
        - 10-50 chunks: Consumer is slightly behind (acceptable)
        - 50+ chunks: Consumer is significantly behind (may miss data)
        - Queue full (600): New chunks are dropped (back-pressure)

        Call `is_consumer_behind()` for a simple boolean check.
    """

    # Queue size: ~20 seconds at 30fps = 600 chunks
    DEFAULT_QUEUE_SIZE = 600

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        queue_size: int = DEFAULT_QUEUE_SIZE,
    ) -> None:
        """
        Initialize the display manager.

        Args:
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Target frames per second for video encoding.
            queue_size: Maximum video chunks in queue before dropping.
                        Default is 600 (~20 seconds at 30fps).
        """
        self._width = width
        self._height = height
        self._fps = fps
        self._queue_size = queue_size

        # Screen buffers:
        # - _raw_display_image: raw screen state from RDP bitmap updates (no pointer)
        # - _final_display_image: screen + pointer composited (for screenshots/video)
        self._raw_display_image: Image.Image | None = None
        self._final_display_image: Image.Image | None = None
        self._final_display_image_dirty: bool = True  # Needs redraw
        self._screen_lock = asyncio.Lock()

        # Pointer state and rate limiting
        self._pointer_x: int = 0
        self._pointer_y: int = 0
        self._pointer_visible: bool = True
        self._pointer_image: Image.Image | None = None
        self._pointer_hotspot: tuple[int, int] = (0, 0)
        self._last_pointer_update: float = 0.0
        self._pointer_update_interval: float = 1.0 / fps  # Cap to FPS

        # Video encoding state
        self._ffmpeg_process: subprocess.Popen[bytes] | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._streaming = False
        self._shutting_down = False

        # Temp file for recording (always used when streaming)
        self._temp_file: IO[bytes] | None = None
        self._temp_file_path: str | None = None

        # Async queue for video chunks (real-time streaming consumers)
        self._video_queue: Queue[VideoChunk] = Queue(maxsize=queue_size)
        self._chunk_sequence = 0

        # Timing for stats
        self._session_start_time: float = time.time()
        self._recording_start_time: float | None = None
        self._first_frame_time: float | None = None

        # Pipeline latency tracking
        self._bitmap_apply_times: list[float] = []  # Rolling window
        self._frame_write_times: list[float] = []  # Rolling window
        self._ffmpeg_latency_samples: list[float] = []  # Rolling window
        self._last_stdin_write_time: float = 0.0
        self._max_latency_samples = 100  # Keep last 100 samples

        # Diagnostic tracking
        self._last_diag_time: float = 0.0
        self._diag_interval: float = 5.0
        self._frames_since_diag: int = 0
        self._encode_time_total: float = 0.0

        # Stats counters
        self._stats = {
            "frames_received": 0,
            "frames_encoded": 0,
            "chunks_produced": 0,
            "queue_drops": 0,
            "bitmaps_applied": 0,
            "pointer_updates": 0,
            "pointer_updates_throttled": 0,
        }

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
    def is_streaming(self) -> bool:
        """True if video encoding/streaming is active."""
        return self._streaming and self._ffmpeg_process is not None

    @property
    def recording_duration_seconds(self) -> float:
        """Return how long encoding has been active."""
        if self._recording_start_time is None:
            return 0.0
        return time.time() - self._recording_start_time

    @property
    def session_duration_seconds(self) -> float:
        """Return how long since the display was created (wall-clock)."""
        return time.time() - self._session_start_time

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
    def consumer_lag_chunks(self) -> int:
        """
        Return the number of chunks waiting in the queue.

        This indicates how far behind a consumer calling get_next_video_chunk() is:
        - 0-10: Consumer is keeping up well
        - 10-50: Consumer is slightly behind
        - 50+: Consumer is significantly behind
        - 600 (queue full): Chunks are being dropped

        Use is_consumer_behind() for a simple boolean check.
        """
        return self._video_queue.qsize()

    def is_consumer_behind(self, threshold: int = 10) -> bool:
        """
        Check if the consumer is falling behind.

        Args:
            threshold: Number of queued chunks considered "behind". Default is 10.

        Returns:
            True if consumer_lag_chunks > threshold.

        Example:
            >>> if display.is_consumer_behind():
            ...     logger.warning("Video consumer is falling behind!")
        """
        return self._video_queue.qsize() > threshold

    @property
    def pointer_position(self) -> tuple[int, int]:
        """Return the current pointer position (x, y)."""
        return (self._pointer_x, self._pointer_y)

    @property
    def stats(self) -> dict[str, int]:
        """Return current statistics counters."""
        return self._stats.copy()

    def get_pipeline_stats(self) -> PipelineStats:
        """
        Get detailed pipeline statistics including latency measurements.

        Returns:
            PipelineStats dataclass with timing and counter information.

        Example:
            >>> stats = display.get_pipeline_stats()
            >>> print(f"E2E latency: {stats.total_e2e_estimate_ms:.1f}ms")
            >>> print(f"Consumer lag: {stats.consumer_lag_chunks} chunks")
        """
        # Calculate averages from rolling windows
        avg_bitmap = (
            sum(self._bitmap_apply_times) / len(self._bitmap_apply_times) * 1000 if self._bitmap_apply_times else 0.0
        )
        avg_frame = (
            sum(self._frame_write_times) / len(self._frame_write_times) * 1000 if self._frame_write_times else 0.0
        )
        avg_ffmpeg = (
            sum(self._ffmpeg_latency_samples) / len(self._ffmpeg_latency_samples) * 1000
            if self._ffmpeg_latency_samples
            else 0.0
        )

        return PipelineStats(
            bitmap_to_buffer_ms=avg_bitmap,
            frame_to_ffmpeg_ms=avg_frame,
            ffmpeg_latency_ms=avg_ffmpeg,
            frames_received=self._stats["frames_received"],
            frames_encoded=self._stats["frames_encoded"],
            chunks_produced=self._stats["chunks_produced"],
            queue_drops=self._stats["queue_drops"],
            bitmaps_applied=self._stats["bitmaps_applied"],
            consumer_lag_chunks=self._video_queue.qsize(),
        )

    @property
    def raw_display_image(self) -> Image.Image | None:
        """Return the raw display image (may be None if not initialized)."""
        return self._raw_display_image

    def initialize_screen(self) -> None:
        """Initialize the screen buffers with black images."""
        self._raw_display_image = Image.new("RGB", (self._width, self._height), (0, 0, 0))
        self._final_display_image = Image.new("RGB", (self._width, self._height), (0, 0, 0))
        self._final_display_image_dirty = True

    def _update_final_display_image(self) -> None:
        """Update the final display image with screen + pointer composited."""
        if self._raw_display_image is None:
            return

        # Reuse existing buffer if same size, otherwise create new
        if self._final_display_image is None or self._final_display_image.size != self._raw_display_image.size:
            self._final_display_image = Image.new("RGB", (self._width, self._height), (0, 0, 0))

        # Paste raw display onto final buffer
        self._final_display_image.paste(self._raw_display_image, (0, 0))

        # Composite pointer if visible
        if self._pointer_visible:
            pointer = self._pointer_image if self._pointer_image is not None else _get_default_pointer()
            hotspot = self._pointer_hotspot if self._pointer_image is not None else (0, 0)

            # Calculate position adjusted for hotspot
            px = self._pointer_x - hotspot[0]
            py = self._pointer_y - hotspot[1]

            # Only paste if within bounds
            if -pointer.width < px < self._width and -pointer.height < py < self._height:
                try:
                    if pointer.mode == "RGBA":
                        self._final_display_image.paste(pointer, (px, py), pointer)
                    else:
                        self._final_display_image.paste(pointer, (px, py))
                except Exception as e:
                    logger.debug(f"Error compositing pointer: {e}")

        self._final_display_image_dirty = False

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
            x: New X position (or None to keep current).
            y: New Y position (or None to keep current).
            visible: Visibility state (or None to keep current).
            image: New pointer image (or None to keep current).
            hotspot: New hotspot (or None to keep current).

        Returns:
            True if update was applied, False if throttled.
        """
        now = time.time()

        # Check rate limit for position-only updates
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
        self._final_display_image_dirty = True
        self._stats["pointer_updates"] += 1
        return True

    async def screenshot(self) -> Image.Image:
        """
        Capture the current screen with pointer composited.

        Returns:
            PIL Image of the current screen state with pointer overlay.
        """
        async with self._screen_lock:
            if self._raw_display_image is None:
                return Image.new("RGB", (self._width, self._height), (0, 0, 0))

            # Update final display image if dirty
            if self._final_display_image_dirty or self._final_display_image is None:
                self._update_final_display_image()

            assert self._final_display_image is not None
            return self._final_display_image.copy()

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
        apply_start = time.perf_counter()

        async with self._screen_lock:
            if self._raw_display_image is None:
                self.initialize_screen()

            if self._raw_display_image is None:
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

                # Paste onto raw display image
                self._raw_display_image.paste(img, (x, y))
                self._stats["bitmaps_applied"] += 1
                self._final_display_image_dirty = True

            except Exception as e:
                logger.debug(f"Error applying bitmap: {e}")

        # Track bitmap apply time
        apply_time = time.perf_counter() - apply_start
        self._bitmap_apply_times.append(apply_time)
        if len(self._bitmap_apply_times) > self._max_latency_samples:
            self._bitmap_apply_times.pop(0)

    async def start_streaming(self) -> None:
        """
        Start video streaming.

        Frames are encoded to fragmented MP4 format. Output is available via:
        - get_next_video_chunk(): Real-time streaming to consumers
        - Temp file: Full session recording (transcoded on cleanup if record_to set)

        Use stop_streaming() to stop encoding.
        """
        if self._streaming:
            logger.warning("Streaming already active")
            return

        self._streaming = True
        self._recording_start_time = time.time()
        self._first_frame_time = None
        self._shutting_down = False

        # Create temp file for recording
        fd, self._temp_file_path = tempfile.mkstemp(suffix=".ts", prefix="rdp_recording_")
        self._temp_file = os.fdopen(fd, "wb")
        logger.debug(f"Recording to temp file: {self._temp_file_path}")

        # Start ffmpeg process
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
            "pipe:0",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "28",
            "-g",
            "15",
            "-keyint_min",
            "15",
            "-bf",
            "0",
            "-flags",
            "+cgop",
            "-f",
            "mp4",
            "-movflags",
            "frag_keyframe+empty_moov+default_base_moof",
            "-frag_duration",
            "33333",
            "-min_frag_duration",
            "0",
            "pipe:1",
        ]

        logger.info(f"Starting streaming encoder: {self._width}x{self._height} @ {self._fps}fps (fMP4)")

        frame_size = self._width * self._height * 3
        self._ffmpeg_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=frame_size,
        )

        # Start reader task to consume ffmpeg output
        self._reader_task = asyncio.create_task(self._read_video_output())
        self._stderr_task = asyncio.create_task(self._read_ffmpeg_stderr())

        logger.info("Streaming encoder started")

    async def stop_streaming(self, record_to: str | None = None) -> None:
        """
        Stop video streaming and optionally save recording.

        Args:
            record_to: If provided, transcode the temp recording to this path (MP4).
                      If None, the temp file is deleted.
        """
        if not self._streaming:
            return

        self._shutting_down = True
        self._streaming = False

        await self._stop_ffmpeg()

        # Handle recording file
        temp_path = self._temp_file_path
        if temp_path and os.path.exists(temp_path):
            if record_to:
                logger.info(f"Transcoding recording to: {record_to}")
                success = self.transcode(temp_path, record_to)
                if success:
                    logger.info(f"Recording saved to: {record_to}")
                else:
                    logger.error(f"Failed to transcode recording to: {record_to}")

            # Clean up temp file
            try:
                os.unlink(temp_path)
                logger.debug(f"Deleted temp file: {temp_path}")
            except Exception as e:
                logger.debug(f"Error deleting temp file: {e}")

        self._temp_file_path = None
        self._shutting_down = False
        self._recording_start_time = None
        logger.info("Streaming stopped")

    async def _stop_ffmpeg(self) -> None:
        """Internal: stop the ffmpeg process."""
        # Close temp file
        if self._temp_file:
            try:
                self._temp_file.close()
            except Exception as e:
                logger.debug(f"Error closing temp file: {e}")
            self._temp_file = None

        if self._ffmpeg_process:
            if self._ffmpeg_process.stdin:
                try:
                    self._ffmpeg_process.stdin.close()
                except Exception as e:
                    logger.debug(f"Error closing ffmpeg stdin: {e}")

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

        This converts the image to raw RGB bytes and sends to ffmpeg
        for encoding. The pointer is composited onto the frame.

        Args:
            image: PIL Image to add (will be converted to RGB if needed).
        """
        # Update final display image with pointer composited
        if self._final_display_image_dirty or self._final_display_image is None:
            self._update_final_display_image()

        # Use final display image (with pointer) if available
        frame_image = self._final_display_image if self._final_display_image is not None else image

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
        timestamp = time.time()

        if self._first_frame_time is None:
            self._first_frame_time = timestamp

        self._stats["frames_received"] += 1

        # Send to ffmpeg if encoding
        if self._streaming and not self._shutting_down and self._ffmpeg_process and self._ffmpeg_process.stdin:
            try:
                write_start = time.perf_counter()
                self._last_stdin_write_time = write_start

                loop = asyncio.get_event_loop()
                stdin = self._ffmpeg_process.stdin
                await loop.run_in_executor(None, lambda: (stdin.write(data), stdin.flush()))

                write_time = time.perf_counter() - write_start
                self._frame_write_times.append(write_time)
                if len(self._frame_write_times) > self._max_latency_samples:
                    self._frame_write_times.pop(0)

                self._encode_time_total += write_time
                self._frames_since_diag += 1
                self._stats["frames_encoded"] += 1

                # Log diagnostics periodically
                now = time.time()
                if now - self._last_diag_time >= self._diag_interval:
                    self._log_diagnostics()
                    self._last_diag_time = now

            except (BrokenPipeError, OSError):
                pass

    def _log_diagnostics(self) -> None:
        """Log backend pipeline diagnostics."""
        if self._frames_since_diag == 0:
            return

        avg_encode_ms = (self._encode_time_total / self._frames_since_diag) * 1000
        target_frame_time_ms = 1000 / self._fps

        headroom_ms = target_frame_time_ms - avg_encode_ms
        status = "OK" if headroom_ms > 0 else "BEHIND"

        queue_size = self._video_queue.qsize()
        queue_pct = (queue_size / self._queue_size) * 100

        logger.info(
            f"Pipeline: {status} by {abs(headroom_ms):.1f}ms | "
            f"encode={avg_encode_ms:.1f}ms/frame | "
            f"queue={queue_size}/{self._queue_size} ({queue_pct:.0f}%) | "
            f"drops={self._stats['queue_drops']} | "
            f"fps_in={self._frames_since_diag / self._diag_interval:.1f}"
        )

        self._frames_since_diag = 0
        self._encode_time_total = 0.0

    async def _read_video_output(self) -> None:
        """Read encoded video from ffmpeg stdout and distribute to queue and file."""
        CHUNK_SIZE = 65536  # 64KB chunks
        loop = asyncio.get_event_loop()

        def _read_chunk() -> bytes:
            if self._ffmpeg_process and self._ffmpeg_process.stdout:
                return self._ffmpeg_process.stdout.read(CHUNK_SIZE)
            return b""

        while self._streaming and self._ffmpeg_process:
            try:
                if self._ffmpeg_process and self._ffmpeg_process.stdout:
                    data = await loop.run_in_executor(None, _read_chunk)
                else:
                    data = b""

                if not data:
                    await asyncio.sleep(0.01)
                    continue

                # Track ffmpeg latency (time from last stdin write to stdout read)
                if self._last_stdin_write_time > 0:
                    ffmpeg_latency = time.perf_counter() - self._last_stdin_write_time
                    self._ffmpeg_latency_samples.append(ffmpeg_latency)
                    if len(self._ffmpeg_latency_samples) > self._max_latency_samples:
                        self._ffmpeg_latency_samples.pop(0)

                # Write to temp file
                if self._temp_file:
                    try:
                        self._temp_file.write(data)
                        self._temp_file.flush()
                    except Exception as e:
                        logger.debug(f"Error writing to temp file: {e}")

                # Create chunk
                chunk = VideoChunk(
                    data=data,
                    timestamp=time.perf_counter(),
                    sequence=self._chunk_sequence,
                )
                self._chunk_sequence += 1
                self._stats["chunks_produced"] += 1

                # Put in queue (drop if full - back-pressure)
                try:
                    self._video_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    self._stats["queue_drops"] += 1
                    logger.debug("Video queue full, dropping chunk (back-pressure)")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Error reading video output: {e}")
                await asyncio.sleep(0.01)

    async def get_next_video_chunk(self, timeout: float = 1.0) -> VideoChunk | None:
        """
        Wait for and return the next video chunk.

        This is the primary method for real-time video streaming consumers.
        Chunks are fragmented MP4 data that can be fed to a media source.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            VideoChunk containing encoded video data, or None if timeout.

        Example:
            >>> while True:
            ...     chunk = await display.get_next_video_chunk()
            ...     if chunk:
            ...         websocket.send(chunk.data)
        """
        try:
            return await asyncio.wait_for(self._video_queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    @staticmethod
    def transcode(input_path: str, output_path: str) -> bool:
        """
        Transcode a video file to another format.

        Uses ffmpeg with stream copy (no re-encoding) for fast conversion.
        Typically used to convert MPEG-TS temp files to MP4.

        Args:
            input_path: Path to input video file.
            output_path: Path to output video file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    input_path,
                    "-c",
                    "copy",
                    output_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Transcode failed: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("ffmpeg not found. Please install ffmpeg.")
            return False

    def print_stats(self) -> None:
        """Print current statistics to stdout."""
        stats = self.get_pipeline_stats()
        print(f"\n{'=' * 50}")
        print("           DISPLAY STATS")
        print(f"{'=' * 50}")
        print(f"Screen buffer:       {'Initialized' if self._raw_display_image else 'Not initialized'}")
        print(f"Streaming:           {'Active' if self.is_streaming else 'Inactive'}")
        print(f"Recording duration:  {self.recording_duration_seconds:.1f}s")
        print(f"Effective FPS:       {self.effective_fps:.1f}")
        print(f"{'=' * 50}")
        print("           PIPELINE STATS")
        print(f"{'=' * 50}")
        print(f"Bitmap apply:        {stats.bitmap_to_buffer_ms:.2f}ms avg")
        print(f"Frame write:         {stats.frame_to_ffmpeg_ms:.2f}ms avg")
        print(f"FFmpeg latency:      {stats.ffmpeg_latency_ms:.2f}ms avg")
        print(f"E2E estimate:        {stats.total_e2e_estimate_ms:.2f}ms")
        print(f"{'=' * 50}")
        print("           COUNTERS")
        print(f"{'=' * 50}")
        print(f"Bitmaps applied:     {stats.bitmaps_applied}")
        print(f"Frames received:     {stats.frames_received}")
        print(f"Frames encoded:      {stats.frames_encoded}")
        print(f"Chunks produced:     {stats.chunks_produced}")
        print(f"Consumer lag:        {stats.consumer_lag_chunks} chunks")
        print(f"Queue drops:         {stats.queue_drops}")
        print(f"{'=' * 50}\n")
