"""Example usage of Simple RDP client for automation.

This example demonstrates:
- Connecting to a remote Windows machine
- Moving the mouse
- Capturing screenshots
- Keyboard input (Windows key + typing)
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from rich.logging import RichHandler

from simple_rdp import RDPClient

load_dotenv()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler()])

    host = os.environ.get("RDP_HOST", "")
    username = os.environ.get("RDP_USER", "")
    password = os.environ.get("RDP_PASS", "")

    if not host or not username or not password:
        print("ERROR: Set RDP_HOST, RDP_USER, RDP_PASS environment variables (or use .env file)")
        return

    async with RDPClient(host=host, username=username, password=password, show_wallpaper=True) as client:
        print("Connected!")

        # Move mouse to center and click to bring focus
        await client.mouse_move(960, 540)
        await asyncio.sleep(0.2)
        await client.mouse_click(960, 540)
        await asyncio.sleep(2)

        # Take screenshot before keyboard input
        img1 = await client.screenshot()
        img1.save("screenshot_before.png")
        print(f"Screenshot before: {img1.width}x{img1.height}")

        # Press Windows key to open Start menu (scancode 0x5B = left Windows key)
        print("Pressing Windows key...")
        await client.send_key(0x5B)  # VK_LWIN scancode
        await asyncio.sleep(1.5)

        # Type some text
        print("Typing 'notepad'...")
        await client.send_text("notepad")
        await asyncio.sleep(1)

        # Take screenshot after keyboard input
        img2 = await client.screenshot()
        img2.save("screenshot_after.png")
        print(f"Screenshot after: {img2.width}x{img2.height}")

        # Press Escape to close Start menu (scancode 0x01)
        await client.send_key(0x01)
        await asyncio.sleep(0.5)

        print("Done! Check screenshot_before.png and screenshot_after.png")


if __name__ == "__main__":
    asyncio.run(main())
