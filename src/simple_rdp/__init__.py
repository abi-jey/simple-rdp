"""
Simple RDP - A Python RDP client for automation.

This library provides RDP connectivity for automation purposes,
exposing screen capture and input transmission capabilities.
"""

from simple_rdp.client import RDPClient
from simple_rdp.input import InputHandler
from simple_rdp.screen import ScreenCapture

__version__ = "0.1.0"
__all__ = ["RDPClient", "ScreenCapture", "InputHandler"]
