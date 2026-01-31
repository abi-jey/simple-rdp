"""
Screen Capture - Handles screen data from RDP sessions.
"""

from dataclasses import dataclass
from logging import getLogger

logger = getLogger(__name__)


@dataclass
class ScreenBuffer:
    """Represents a captured screen frame."""

    width: int
    height: int
    data: bytes
    format: str = "RGB"


class ScreenCapture:
    """
    Handles screen capture from RDP sessions.

    Provides methods to capture the current screen state and
    access screen data for automation purposes.
    """

    def __init__(self) -> None:
        """Initialize the screen capture handler."""
        self._last_frame: ScreenBuffer | None = None
        self._resolution: tuple[int, int] | None = None

    @property
    def resolution(self) -> tuple[int, int] | None:
        """Return the current screen resolution as (width, height)."""
        return self._resolution

    def capture(self) -> ScreenBuffer | None:
        """
        Capture the current screen state.

        Returns:
            ScreenBuffer containing the captured frame, or None if unavailable.
        """
        # TODO: Implement screen capture from RDP session
        raise NotImplementedError("Screen capture not yet implemented")

    def get_last_frame(self) -> ScreenBuffer | None:
        """
        Get the last captured frame without capturing a new one.

        Returns:
            The most recently captured ScreenBuffer, or None if no capture exists.
        """
        return self._last_frame
