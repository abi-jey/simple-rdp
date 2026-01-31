"""Tests for Screen and Display classes."""

from simple_rdp.display import Display
from simple_rdp.display import ScreenBuffer


class TestScreenBuffer:
    """Tests for ScreenBuffer dataclass."""

    def test_screen_buffer_creation(self):
        """Test ScreenBuffer can be created with required fields."""
        buffer = ScreenBuffer(width=1920, height=1080, data=b"\x00" * 100)
        assert buffer.width == 1920
        assert buffer.height == 1080
        assert buffer.format == "RGB"

    def test_screen_buffer_custom_format(self):
        """Test ScreenBuffer with custom format."""
        buffer = ScreenBuffer(width=800, height=600, data=b"\x00", format="RGBA")
        assert buffer.format == "RGBA"


class TestDisplay:
    """Tests for Display class."""

    def test_initial_state(self):
        """Test initial state of Display."""
        display = Display(width=1920, height=1080)
        assert display.width == 1920
        assert display.height == 1080
        assert display.frame_count == 0

    def test_display_stats(self):
        """Test display statistics."""
        display = Display(width=1920, height=1080, fps=30)
        stats = display.stats
        assert stats["frames_received"] == 0
        assert stats["frames_encoded"] == 0
        assert stats["encoding_errors"] == 0
