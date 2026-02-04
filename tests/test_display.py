"""Tests for Display class."""

import asyncio

import pytest

from simple_rdp.display import Display
from simple_rdp.display import PipelineStats
from simple_rdp.display import VideoChunk


class TestVideoChunk:
    """Tests for VideoChunk dataclass."""

    def test_video_chunk_creation(self) -> None:
        """Test VideoChunk creation."""
        chunk = VideoChunk(data=b"\x00" * 50, timestamp=1.0, sequence=0)
        assert chunk.data == b"\x00" * 50
        assert chunk.timestamp == 1.0
        assert chunk.sequence == 0

    def test_video_chunk_size_bytes(self) -> None:
        """Test VideoChunk size_bytes property."""
        chunk = VideoChunk(data=b"\x00" * 50, timestamp=1.0, sequence=0)
        assert chunk.size_bytes == 50


class TestPipelineStats:
    """Tests for PipelineStats dataclass."""

    def test_pipeline_stats_creation(self) -> None:
        """Test PipelineStats creation."""
        stats = PipelineStats(
            bitmap_to_buffer_ms=1.0,
            frame_to_ffmpeg_ms=2.0,
            ffmpeg_latency_ms=3.0,
            frames_received=100,
            frames_encoded=90,
            chunks_produced=80,
            queue_drops=5,
            bitmaps_applied=50,
            consumer_lag_chunks=10,
        )
        assert stats.bitmap_to_buffer_ms == 1.0
        assert stats.frame_to_ffmpeg_ms == 2.0
        assert stats.ffmpeg_latency_ms == 3.0
        assert stats.frames_received == 100
        assert stats.frames_encoded == 90
        assert stats.chunks_produced == 80
        assert stats.queue_drops == 5
        assert stats.bitmaps_applied == 50
        assert stats.consumer_lag_chunks == 10

    def test_pipeline_stats_total_e2e(self) -> None:
        """Test total_e2e_estimate_ms is calculated correctly."""
        stats = PipelineStats(
            bitmap_to_buffer_ms=1.0,
            frame_to_ffmpeg_ms=2.0,
            ffmpeg_latency_ms=3.0,
        )
        assert stats.total_e2e_estimate_ms == 6.0  # 1 + 2 + 3


class TestDisplay:
    """Tests for Display class."""

    def test_initial_state(self) -> None:
        """Test initial state of Display."""
        display = Display(width=1920, height=1080)
        assert display.width == 1920
        assert display.height == 1080
        assert display.fps == 30
        assert display.is_streaming is False

    def test_display_custom_params(self) -> None:
        """Test Display with custom parameters."""
        display = Display(
            width=1280,
            height=720,
            fps=60,
            queue_size=100,
        )
        assert display.width == 1280
        assert display.height == 720
        assert display.fps == 60
        assert display._queue_size == 100

    def test_display_stats(self) -> None:
        """Test display statistics."""
        display = Display(width=1920, height=1080, fps=30)
        stats = display.stats
        assert stats["frames_received"] == 0
        assert stats["frames_encoded"] == 0
        assert stats["chunks_produced"] == 0
        assert stats["queue_drops"] == 0
        assert stats["bitmaps_applied"] == 0

    def test_recording_duration_not_recording(self) -> None:
        """Test recording_duration_seconds is 0 when not recording."""
        display = Display(width=100, height=100)
        assert display.recording_duration_seconds == 0.0

    def test_effective_fps_no_frames(self) -> None:
        """Test effective_fps is 0 when no frames."""
        display = Display(width=100, height=100)
        assert display.effective_fps == 0.0

    def test_consumer_lag_chunks_starts_at_zero(self) -> None:
        """Test consumer_lag_chunks starts at 0."""
        display = Display(width=100, height=100)
        assert display.consumer_lag_chunks == 0

    def test_is_consumer_behind_false_initially(self) -> None:
        """Test is_consumer_behind returns False initially."""
        display = Display(width=100, height=100)
        assert display.is_consumer_behind() is False
        assert display.is_consumer_behind(threshold=0) is False

    def test_get_pipeline_stats(self) -> None:
        """Test get_pipeline_stats returns PipelineStats."""
        display = Display(width=100, height=100)
        stats = display.get_pipeline_stats()
        assert isinstance(stats, PipelineStats)
        assert stats.frames_received == 0
        assert stats.frames_encoded == 0
        assert stats.chunks_produced == 0
        assert stats.consumer_lag_chunks == 0

    def test_raw_display_image_property(self) -> None:
        """Test raw_display_image property."""
        display = Display(width=100, height=100)
        assert display.raw_display_image is None
        display.initialize_screen()
        assert display.raw_display_image is not None
        assert display.raw_display_image.size == (100, 100)


class TestDisplayAsync:
    """Async tests for Display class."""

    @pytest.mark.asyncio
    async def test_screenshot_empty(self) -> None:
        """Test screenshot when not initialized."""
        display = Display(width=100, height=100)
        img = await display.screenshot()
        assert img.size == (100, 100)
        # Should be black
        assert img.getpixel((0, 0)) == (0, 0, 0)

    @pytest.mark.asyncio
    async def test_screenshot_after_init(self) -> None:
        """Test screenshot after initialization."""
        display = Display(width=100, height=100)
        display.initialize_screen()
        img = await display.screenshot()
        assert img.size == (100, 100)
        assert img.getpixel((0, 0)) == (0, 0, 0)

    @pytest.mark.asyncio
    async def test_get_next_video_chunk_timeout(self) -> None:
        """Test get_next_video_chunk times out when no chunks."""
        display = Display(width=10, height=10)
        chunk = await display.get_next_video_chunk(timeout=0.1)
        assert chunk is None

    @pytest.mark.asyncio
    async def test_apply_bitmap(self) -> None:
        """Test applying bitmap updates."""
        display = Display(width=100, height=100)
        display.initialize_screen()

        # Create a 10x10 red bitmap (BGR format, 32bpp)
        bitmap_data = b"\x00\x00\xff\x00" * 100  # BGR + X for 10x10

        await display.apply_bitmap(
            x=10,
            y=10,
            width=10,
            height=10,
            data=bitmap_data,
            bpp=32,
        )

        stats = display.stats
        assert stats["bitmaps_applied"] == 1

    @pytest.mark.asyncio
    async def test_add_raw_frame(self) -> None:
        """Test adding a raw frame."""
        display = Display(width=10, height=10)
        display.initialize_screen()
        # RGB data: 10x10 = 100 pixels * 3 bytes = 300 bytes
        frame_data = b"\x00" * 300
        await display.add_raw_frame(frame_data)
        stats = display.stats
        assert stats["frames_received"] == 1

    @pytest.mark.asyncio
    async def test_add_multiple_frames(self) -> None:
        """Test adding multiple frames."""
        display = Display(width=10, height=10)
        display.initialize_screen()
        frame_data = b"\x00" * 300
        for _ in range(5):
            await display.add_raw_frame(frame_data)
        stats = display.stats
        assert stats["frames_received"] == 5

    @pytest.mark.asyncio
    async def test_effective_fps_with_frames(self) -> None:
        """Test effective_fps after adding frames."""
        display = Display(width=10, height=10)
        display.initialize_screen()
        frame_data = b"\x00" * 300
        await display.add_raw_frame(frame_data)
        await display.add_raw_frame(frame_data)
        # After 2 frames, effective_fps should be calculable
        assert display.effective_fps >= 0

    @pytest.mark.asyncio
    async def test_add_frame_from_image(self) -> None:
        """Test adding frame from PIL Image."""
        from PIL import Image

        display = Display(width=10, height=10)
        display.initialize_screen()
        img = Image.new("RGB", (10, 10), color="red")
        await display.add_frame(img)
        stats = display.stats
        assert stats["frames_received"] == 1

    @pytest.mark.asyncio
    async def test_add_frame_converts_rgba_to_rgb(self) -> None:
        """Test adding RGBA image converts to RGB."""
        from PIL import Image

        display = Display(width=10, height=10)
        display.initialize_screen()
        img = Image.new("RGBA", (10, 10), color=(255, 0, 0, 128))
        await display.add_frame(img)
        stats = display.stats
        assert stats["frames_received"] == 1


class TestDisplayPrintStats:
    """Tests for Display print_stats method."""

    def test_print_stats(self, capsys) -> None:
        """Test print_stats outputs to stdout."""
        display = Display(width=100, height=100)
        display.print_stats()
        captured = capsys.readouterr()
        assert "DISPLAY STATS" in captured.out
        assert "PIPELINE STATS" in captured.out
        assert "COUNTERS" in captured.out

    @pytest.mark.asyncio
    async def test_print_stats_after_frames(self, capsys) -> None:
        """Test print_stats after adding frames."""
        display = Display(width=10, height=10)
        display.initialize_screen()
        frame_data = b"\x00" * 300
        await display.add_raw_frame(frame_data)
        await display.add_raw_frame(frame_data)
        display.print_stats()
        captured = capsys.readouterr()
        # Should show frames received
        assert "Frames received" in captured.out


class TestDisplayEncoding:
    """Tests for Display encoding functionality."""

    @pytest.mark.asyncio
    async def test_stop_streaming_when_not_started(self) -> None:
        """Test stop_streaming when not started."""
        display = Display(width=10, height=10)
        # Should not raise
        await display.stop_streaming()
        assert display.is_streaming is False


class TestDisplayStatsDetails:
    """Tests for Display stats in more detail."""

    @pytest.mark.asyncio
    async def test_stats_are_copy(self) -> None:
        """Test that stats returns a copy, not the original dict."""
        display = Display(width=10, height=10)
        stats1 = display.stats
        stats1["frames_received"] = 999
        stats2 = display.stats
        assert stats2["frames_received"] == 0

    @pytest.mark.asyncio
    async def test_screen_lock_exists(self) -> None:
        """Test that _screen_lock exists and is an asyncio.Lock."""
        display = Display(width=10, height=10)
        assert hasattr(display, "_screen_lock")
        assert isinstance(display._screen_lock, asyncio.Lock)


class TestDisplayVideoQueue:
    """Tests for Display video queue management."""

    def test_video_queue_exists(self) -> None:
        """Test video queue is initialized."""
        display = Display(width=100, height=100)
        assert display._video_queue is not None

    def test_chunk_sequence_starts_at_zero(self) -> None:
        """Test chunk sequence counter starts at 0."""
        display = Display(width=100, height=100)
        assert display._chunk_sequence == 0

    def test_default_queue_size(self) -> None:
        """Test default queue size is 600."""
        display = Display(width=100, height=100)
        assert display._queue_size == Display.DEFAULT_QUEUE_SIZE
        assert display._queue_size == 600


class TestVideoChunkEdgeCases:
    """Edge case tests for VideoChunk."""

    def test_empty_chunk(self) -> None:
        """Test VideoChunk with empty data."""
        chunk = VideoChunk(data=b"", timestamp=0.0, sequence=0)
        assert chunk.size_bytes == 0

    def test_large_sequence(self) -> None:
        """Test VideoChunk with large sequence number."""
        chunk = VideoChunk(data=b"\x00", timestamp=1.0, sequence=999999)
        assert chunk.sequence == 999999

    def test_negative_timestamp(self) -> None:
        """Test VideoChunk with negative timestamp."""
        chunk = VideoChunk(data=b"\x00", timestamp=-1.0, sequence=0)
        assert chunk.timestamp == -1.0


class TestDisplayPointer:
    """Tests for Display pointer management."""

    def test_update_pointer_position(self) -> None:
        """Test updating pointer position."""
        display = Display(width=100, height=100)
        result = display.update_pointer(x=50, y=50)
        assert result is True
        assert display._pointer_x == 50
        assert display._pointer_y == 50

    def test_update_pointer_visibility(self) -> None:
        """Test updating pointer visibility."""
        display = Display(width=100, height=100)
        result = display.update_pointer(visible=False)
        assert result is True
        assert display._pointer_visible is False

    def test_update_pointer_image(self) -> None:
        """Test updating pointer image."""
        from PIL import Image

        display = Display(width=100, height=100)
        cursor = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
        result = display.update_pointer(image=cursor)
        assert result is True
        assert display._pointer_image is cursor

    def test_update_pointer_hotspot(self) -> None:
        """Test updating pointer hotspot."""
        display = Display(width=100, height=100)
        result = display.update_pointer(hotspot=(5, 5))
        assert result is True
        assert display._pointer_hotspot == (5, 5)


class TestDisplayTranscode:
    """Tests for Display transcode functionality."""

    def test_transcode_static_method_exists(self) -> None:
        """Test transcode is a static method."""
        assert hasattr(Display, "transcode")
        assert callable(Display.transcode)
