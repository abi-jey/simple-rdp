"""Tests for Input types."""

from simple_rdp.input import KeyEvent
from simple_rdp.input import KeyModifier
from simple_rdp.input import MouseButton
from simple_rdp.input import MouseEvent


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


class TestMouseEvent:
    """Tests for MouseEvent dataclass."""

    def test_mouse_event_creation(self):
        """Test MouseEvent creation."""
        event = MouseEvent(x=100, y=200)
        assert event.x == 100
        assert event.y == 200
        assert event.button is None
        assert event.pressed is False

    def test_mouse_event_with_button(self):
        """Test MouseEvent with button."""
        event = MouseEvent(x=100, y=200, button=MouseButton.LEFT, pressed=True)
        assert event.button == MouseButton.LEFT
        assert event.pressed is True


class TestKeyEvent:
    """Tests for KeyEvent dataclass."""

    def test_key_event_creation(self):
        """Test KeyEvent creation."""
        event = KeyEvent(key_code=0x1C)
        assert event.key_code == 0x1C
        assert event.pressed is True
        assert event.modifiers == ()

    def test_key_event_with_modifiers(self):
        """Test KeyEvent with modifiers."""
        event = KeyEvent(key_code=0x1C, modifiers=(KeyModifier.CTRL, KeyModifier.SHIFT))
        assert event.modifiers == (KeyModifier.CTRL, KeyModifier.SHIFT)
