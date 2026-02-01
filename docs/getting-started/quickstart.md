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
    ) as client:  # (1)!
        # Wait for screen to fully render
        await asyncio.sleep(2)  # (2)!
        
        # Capture screenshot
        img = await client.screenshot()
        print(f"Captured: {img.size}")
        
        # Save to file
        img.save("screenshot.png")


asyncio.run(main())
```

1.  :material-connection: The context manager handles `connect()` and `disconnect()` automatically
2.  :material-clock-outline: Give the remote desktop time to render before capturing

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
    show_wallpaper=False,      # Disable wallpaper for better performance  # (1)!
)
```

1.  :material-speedometer: Disabling wallpaper significantly improves connection speed and reduces bandwidth

!!! tip "Performance Tip"
    Setting `show_wallpaper=False` (the default) reduces initial connection time and bandwidth usage.

## Manual Connection Management

??? example "For more control, manage the connection manually"

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
            await client.disconnect()  # (1)!


    asyncio.run(main())
    ```

    1.  :material-alert: Always disconnect in a `finally` block to ensure cleanup

## Using Environment Variables

!!! warning "Security Best Practice"
    Never hardcode credentials in your scripts. Use environment variables or a secrets manager.

=== ":material-file-document: .env file"

    ```bash
    RDP_HOST=192.168.1.100
    RDP_USER=admin
    RDP_PASS=secret
    ```

=== ":material-language-python: Python script"

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

<div class="grid cards" markdown>

-   :material-camera: [**Screen Capture**](../guide/screen-capture.md)
    
    Learn about capturing screenshots

-   :material-mouse: [**Mouse Input**](../guide/mouse-input.md)
    
    Send mouse events

-   :material-keyboard: [**Keyboard Input**](../guide/keyboard-input.md)
    
    Send keyboard input

</div>
