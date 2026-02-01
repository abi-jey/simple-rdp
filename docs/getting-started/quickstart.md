# Quick Start

This guide will help you connect to an RDP server and capture your first screenshot.

## Basic Connection

The simplest way to connect is using the async context manager:

```python
import asyncio
from simple_rdp import RDPClient


async def main():
    async with RDPClient(
        host="192.168.1.100",
        username="your_username",
        password="your_password",
    ) as client:
        # Wait for screen to fully render
        await asyncio.sleep(2)
        
        # Capture screenshot
        img = await client.screenshot()
        print(f"Captured: {img.size}")
        
        # Save to file
        img.save("screenshot.png")


asyncio.run(main())
```

## Connection Parameters

```python
client = RDPClient(
    host="192.168.1.100",     # RDP server hostname or IP
    port=3389,                 # RDP port (default: 3389)
    username="admin",          # Username
    password="secret",         # Password
    domain="MYDOMAIN",         # Optional domain
    width=1920,                # Desktop width (default: 1920)
    height=1080,               # Desktop height (default: 1080)
    color_depth=32,            # Color depth: 16, 24, or 32 (default: 32)
    show_wallpaper=False,      # Disable wallpaper for better performance
)
```

## Manual Connection Management

For more control, you can manage the connection manually:

```python
import asyncio
from simple_rdp import RDPClient


async def main():
    client = RDPClient(
        host="192.168.1.100",
        username="admin",
        password="secret",
    )
    
    try:
        await client.connect()
        print(f"Connected: {client.width}x{client.height}")
        
        await asyncio.sleep(2)
        await client.save_screenshot("desktop.png")
        
    finally:
        await client.disconnect()


asyncio.run(main())
```

## Using Environment Variables

For security, store credentials in environment variables:

```bash
# .env file
RDP_HOST=192.168.1.100
RDP_USER=admin
RDP_PASS=secret
```

```python
import asyncio
import os
from dotenv import load_dotenv
from simple_rdp import RDPClient

load_dotenv()


async def main():
    async with RDPClient(
        host=os.environ["RDP_HOST"],
        username=os.environ["RDP_USER"],
        password=os.environ["RDP_PASS"],
    ) as client:
        await asyncio.sleep(2)
        await client.save_screenshot("desktop.png")


asyncio.run(main())
```

## Checking Connection Status

```python
async with RDPClient(...) as client:
    print(f"Connected: {client.is_connected}")
    print(f"Resolution: {client.width}x{client.height}")
    print(f"Host: {client.host}:{client.port}")
```

## Next Steps

- [Screen Capture](../guide/screen-capture.md) - Learn about capturing screenshots
- [Mouse Input](../guide/mouse-input.md) - Send mouse events
- [Keyboard Input](../guide/keyboard-input.md) - Send keyboard input
