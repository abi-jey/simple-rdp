"""Tests for Screen and Display classes."""

import asyncio

import pytest

from simple_rdp.display import Display
from simple_rdp.display import ScreenBuffer
from simple_rdp.display import VideoChunk


class TestScreenBuffer:
    """Tests for ScreenBuffer dataclass."""

    def test_screen_buffer_creation(self) -> None:
        """Test ScreenBuffer can be created with required fields."""
        buffer = ScreenBuffer(width=1920, height=1080, data=b"\x00" * 100)
        assert buffer.width == 1920
        assert buffer.height == 1080
        assert buffer.format == "RGB"

    def test_screen_buffer_custom_format(self) -> None:
        """Test ScreenBuffer with custom format."""
        buffer = ScreenBuffer(width=800, height=600, data=b"\x00", format="RGBA")
        assert buffer.format == "RGBA"

    def test_screen_buffer_size_bytes(self) -> None:
        """Test ScreenBuffer size_bytes property."""
        data = b"\x00" * 100
        buffer = ScreenBuffer(width=100, height=100, data=data)
        assert buffer.size_bytes == 100

    def test_screen_buffer_timestamp(self) -> None:
        """Test ScreenBuffer has timestamp."""
        buffer = ScreenBuffer(width=100, height=100, data=b"\x00")
        assert buffer.timestamp > 0


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


class TestDisplay:
    """Tests for Display class."""

    def test_initial_state(self) -> None:
        """Test initial state of Display."""
        display = Display(width=1920, height=1080)
        assert display.width == 1920
        assert display.height == 1080
        assert display.frame_count == 0

    def test_display_custom_params(self) -> None:
        """Test Display with custom parameters."""
        display = Display(
            width=1280,
            height=720,
            fps=60,
            max_video_buffer_mb=50,
            max_raw_frames=100,
        )
        assert display.width == 1280
        assert display.height == 720
        assert display.fps == 60

    def test_display_stats(self) -> None:
        """Test display statistics."""
        display = Display(width=1920, height=1080, fps=30)
        stats = display.stats
        assert stats["frames_received"] == 0
        assert stats["frames_encoded"] == 0
        assert stats["encoding_errors"] == 0
        assert stats["chunks_evicted"] == 0
        assert stats["bytes_encoded"] == 0

    def test_display_raw_frame_count(self) -> None:
        """Test raw frame count property."""
        display = Display(width=100, height=100)
        assert display.raw_frame_count == 0

    def test_display_video_buffer_size_mb(self) -> None:
        """Test video buffer size property."""
        display = Display(width=100, height=100)
        assert display.video_buffer_size_mb == 0.0

    def test_display_is_encoding_false_initially(self) -> None:
        """Test is_encoding is False initially."""
        display = Display(width=100, height=100)
        assert display.is_encoding is False

    def test_get_latest_frame_empty(self) -> None:
        """Test get_latest_frame when no frames."""
        display = Display(width=100, height=100)
        assert display.get_latest_frame() is None

    def test_get_frames_empty(self) -> None:
        """Test get_frames when no frames."""
        display = Display(width=100, height=100)
        assert display.get_frames() == []
        assert display.get_frames(count=5) == []

    def test_get_video_chunks_empty(self) -> None:
        """Test get_video_chunks when no chunks."""
        display = Display(width=100, height=100)
        assert display.get_video_chunks() == []

    def test_clear_raw_frames(self) -> None:
        """Test clear_raw_frames."""
        display = Display(width=100, height=100)
        display.clear_raw_frames()
        assert display.raw_frame_count == 0

    def test_clear_video_chunks(self) -> None:
        """Test clear_video_chunks."""
        display = Display(width=100, height=100)
        display.clear_video_chunks()
        assert display.video_buffer_size_mb == 0.0


class TestDisplayAsync:
    """Async tests for Display class."""

    @pytest.mark.asyncio
    async def test_add_raw_frame(self) -> None:
        """Test adding a raw frame."""
        display = Display(width=10, height=10)
        # RGB data: 10x10 = 100 pixels * 3 bytes = 300 bytes
        frame_data = b"\x00" * 300
        await display.add_raw_frame(frame_data)
        assert display.frame_count == 1
        assert display.raw_frame_count == 1
        assert display.stats["frames_received"] == 1

    @pytest.mark.asyncio
    async def test_add_multiple_frames(self) -> None:
        """Test adding multiple frames."""
        display = Display(width=10, height=10)
        frame_data = b"\x00" * 300
        for _ in range(5):
            await display.add_raw_frame(frame_data)
        assert display.frame_count == 5
        assert display.raw_frame_count == 5

    @pytest.mark.asyncio
    async def test_get_latest_frame_after_add(self) -> None:
        """Test get_latest_frame after adding frames."""
        display = Display(width=10, height=10)
        frame_data = b"\xFF" * 300
        await display.add_raw_frame(frame_data)
        latest = display.get_latest_frame()
        assert latest is not None
        assert latest.data == frame_data

    @pytest.mark.asyncio
    async def test_get_next_video_chunk_timeout(self) -> None:
        """Test get_next_video_chunk times out when no chunks."""
        display = Display(width=10, height=10)
        chunk = await display.get_next_video_chunk(timeout=0.1)
        assert chunk is None

    @pytest.mark.asyncio
    async def test_get_frames_all(self) -> None:
        """Test get_frames returns all frames."""
        display = Display(width=10, height=10)
        frame_data = b"\x00" * 300
        for _ in range(3):
            await display.add_raw_frame(frame_data)
        frames = display.get_frames()
        assert len(frames) == 3

    @pytest.mark.asyncio
    async def test_get_frames_with_count(self) -> None:
        """Test get_frames with count parameter."""
        display = Display(width=10, height=10)
        frame_data = b"\x00" * 300
        for _ in range(5):
            await display.add_raw_frame(frame_data)
        frames = display.get_frames(count=2)
        assert len(frames) == 2

    @pytest.mark.asyncio
    async def test_clear_raw_frames_after_add(self) -> None:
        """Test clearing raw frames after adding some."""
        display = Display(width=10, height=10)
        frame_data = b"\x00" * 300
        await display.add_raw_frame(frame_data)
        await display.add_raw_frame(frame_data)
        assert display.raw_frame_count == 2
        display.clear_raw_frames()
        assert display.raw_frame_count == 0

    @pytest.mark.asyncio
    async def test_add_frame_from_image(self) -> None:
        """Test adding frame from PIL Image."""
        from PIL import Image
        
        display = Display(width=10, height=10)
        img = Image.new("RGB", (10, 10), color="red")
        await display.add_frame(img)
        assert display.frame_count == 1
        assert display.raw_frame_count == 1

    @pytest.mark.asyncio
    async def test_add_frame_converts_rgba_to_rgb(self) -> None:
        """Test adding RGBA image converts to RGB."""
        from PIL import Image
        
        display = Display(width=10, height=10)
        img = Image.new("RGBA", (10, 10), color=(255, 0, 0, 128))
        await display.add_frame(img)
        assert display.frame_count == 1
        # Frame should be stored as RGB
        frame = display.get_latest_frame()
        assert frame is not None
        assert frame.format == "RGB"

    @pytest.mark.asyncio
    async def test_save_video_empty(self) -> None:
        """Test saving video with no chunks."""
        import tempfile
        import os
        
        display = Display(width=10, height=10)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            path = f.name
        
        try:
            result = await display.save_video(path)
            assert result is True
            # File should exist but be empty
            assert os.path.exists(path)
        finally:
            if os.path.exists(path):
                os.unlink(path)
