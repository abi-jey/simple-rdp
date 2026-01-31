"""Tests for Input Handler."""

import pytest

from simple_rdp.input import InputHandler
from simple_rdp.input import KeyModifier
from simple_rdp.input import MouseButton


class TestMouseButton:
    """Tests for MouseButton enum."""

    def test_mouse_buttons_exist(self):
        """Test that all mouse buttons are defined."""
        assert MouseButton.LEFT
        assert MouseButton.RIGHT
        assert MouseButton.MIDDLE


class TestKeyModifier:
    """Tests for KeyModifier enum."""

    def test_key_modifiers_exist(self):
        """Test that all key modifiers are defined."""
        assert KeyModifier.SHIFT
        assert KeyModifier.CTRL
        assert KeyModifier.ALT
        assert KeyModifier.WIN


class TestInputHandler:
    """Tests for InputHandler class."""

    def test_initial_state(self):
        """Test initial state of InputHandler."""
        handler = InputHandler()
        assert handler.is_enabled is False

    def test_enable_disable(self):
        """Test enable and disable functionality."""
        handler = InputHandler()
        handler.enable()
        assert handler.is_enabled is True
        handler.disable()
        assert handler.is_enabled is False

    def test_move_mouse_not_implemented(self):
        """Test that move_mouse raises NotImplementedError."""
        handler = InputHandler()
        with pytest.raises(NotImplementedError):
            handler.move_mouse(100, 200)

    def test_click_not_implemented(self):
        """Test that click raises NotImplementedError."""
        handler = InputHandler()
        with pytest.raises(NotImplementedError):
            handler.click(100, 200)

    def test_type_text_not_implemented(self):
        """Test that type_text raises NotImplementedError."""
        handler = InputHandler()
        with pytest.raises(NotImplementedError):
            handler.type_text("hello")
