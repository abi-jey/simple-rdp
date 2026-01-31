"""Tests for Screen Capture."""

import pytest

from simple_rdp.screen import ScreenBuffer, ScreenCapture


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


class TestScreenCapture:
    """Tests for ScreenCapture class."""

    def test_initial_state(self):
        """Test initial state of ScreenCapture."""
        capture = ScreenCapture()
        assert capture.resolution is None
        assert capture.get_last_frame() is None

    def test_capture_not_implemented(self):
        """Test that capture raises NotImplementedError."""
        capture = ScreenCapture()
        with pytest.raises(NotImplementedError):
            capture.capture()
