"""Tests for Display class (screen-related functionality)."""

from simple_rdp.display import Display
from simple_rdp.display import PipelineStats


class TestDisplayScreen:
    """Tests for Display class screen functionality."""

    def test_initial_state(self):
        """Test initial state of Display."""
        display = Display(width=1920, height=1080)
        assert display.width == 1920
        assert display.height == 1080
        assert display.is_streaming is False

    def test_display_stats(self):
        """Test display statistics."""
        display = Display(width=1920, height=1080, fps=30)
        stats = display.stats
        assert stats["frames_received"] == 0
        assert stats["frames_encoded"] == 0
        assert stats["chunks_produced"] == 0
        assert stats["queue_drops"] == 0

    def test_get_pipeline_stats(self):
        """Test get_pipeline_stats returns PipelineStats."""
        display = Display(width=1920, height=1080, fps=30)
        stats = display.get_pipeline_stats()
        assert isinstance(stats, PipelineStats)
        assert stats.frames_received == 0
        assert stats.frames_encoded == 0
