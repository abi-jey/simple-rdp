"""
Simple RDP - A Python RDP client for automation.

This library provides RDP connectivity for automation purposes,
exposing screen capture and input transmission capabilities.
"""

from simple_rdp.client import RDPClient
from simple_rdp.display import Display
from simple_rdp.display import ScreenBuffer
from simple_rdp.input import KeyEvent
from simple_rdp.input import KeyModifier
from simple_rdp.input import MouseButton
from simple_rdp.input import MouseEvent

__version__ = "0.1.0"
__all__ = [
    "RDPClient",
    "Display",
    "ScreenBuffer",
    "MouseButton",
    "KeyModifier",
    "MouseEvent",
    "KeyEvent",
]
