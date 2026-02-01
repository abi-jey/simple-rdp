# Simple RDP

A Python RDP client library designed for automation purposes.

[![CI](https://github.com/abi-jey/simple-rdp/actions/workflows/ci.yml/badge.svg)](https://github.com/abi-jey/simple-rdp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/abi-jey/simple-rdp/branch/main/graph/badge.svg)](https://codecov.io/gh/abi-jey/simple-rdp)

## Overview

Unlike traditional RDP clients, Simple RDP does not provide an interactive session. Instead, it exposes screen capture and input transmission capabilities for building automation workflows.

## Features

- :camera: **Screen Capture** - Capture the remote desktop screen as PIL Images
- :mouse: **Mouse Input** - Send mouse movements, clicks, drags, and wheel scrolling
- :keyboard: **Keyboard Input** - Send keyboard keys and type text
- :lock: **NLA/CredSSP Authentication** - Full support for Network Level Authentication
- :zap: **Async Support** - Built with asyncio for non-blocking operations
- :rocket: **Optional Rust Acceleration** - 100x faster RLE decompression with optional Rust extension

## Quick Example

```python
import asyncio
from simple_rdp import RDPClient


async def main():
    async with RDPClient(
        host="192.168.1.100",
        username="admin",
        password="secret",
        width=1920,
        height=1080,
    ) as client:
        # Wait for screen to render
        await asyncio.sleep(2)
        
        # Capture screenshot
        img = await client.screenshot()
        img.save("desktop.png")
        
        # Click somewhere
        await client.mouse_click(500, 300)
        
        # Type some text
        await client.send_text("Hello, World!")


asyncio.run(main())
```

## Requirements

- Python 3.11+
- Windows RDP server with NLA enabled

!!! warning "Security Notice"
    This library does **NOT** validate TLS certificates when connecting to RDP servers.
    Only use in trusted network environments.

## Next Steps

- [Installation](getting-started/installation.md) - Get Simple RDP installed
- [Quick Start](getting-started/quickstart.md) - Connect to your first RDP server
- [API Reference](api/client.md) - Full API documentation
