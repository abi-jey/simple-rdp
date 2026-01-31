"""
Example usage of Simple RDP client for automation.

This example demonstrates:
- Connecting to a remote Windows machine
- Moving the mouse
- Capturing a screenshot
- Pressing the Windows key
- Typing text
"""

import asyncio
import logging

from rich.logging import RichHandler

from simple_rdp import RDPClient


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler()])
    async with RDPClient(
        host="192.168.1.243",
        username="abja",
        password="changeme",
    ) as client:
        # Move mouse to center of screen
        client.input.move_mouse(500, 400)

        # Capture a screenshot
        frame = client.screen.capture()
        if frame:
            print(f"Captured frame: {frame.width}x{frame.height}")

        # Move mouse to a different position
        client.input.move_mouse(100, 100)

        # Press Windows key (to open Start menu)
        client.input.key_press(0x5B)  # VK_LWIN

        # Type "hello world!"
        client.input.type_text("hello world!")


if __name__ == "__main__":
    asyncio.run(main())
