"""
Input types and utilities for RDP sessions.

Provides enums and dataclasses for mouse and keyboard input.
The actual input transmission is handled by RDPClient methods.
"""

from dataclasses import dataclass
from enum import Enum
from enum import auto


class MouseButton(Enum):
    """Mouse button identifiers."""

    LEFT = auto()
    RIGHT = auto()
    MIDDLE = auto()


class KeyModifier(Enum):
    """Keyboard modifier keys."""

    SHIFT = auto()
    CTRL = auto()
    ALT = auto()
    WIN = auto()


@dataclass
class MouseEvent:
    """Represents a mouse event."""

    x: int
    y: int
    button: MouseButton | None = None
    pressed: bool = False


@dataclass
class KeyEvent:
    """Represents a keyboard event."""

    key_code: int
    pressed: bool = True
    modifiers: tuple[KeyModifier, ...] = ()


__all__ = ["MouseButton", "KeyModifier", "MouseEvent", "KeyEvent"]
