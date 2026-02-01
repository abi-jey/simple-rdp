# Simple RDP

A Python RDP client library designed for automation purposes.

[![CI](https://github.com/abi-jey/simple-rdp/actions/workflows/ci.yml/badge.svg)](https://github.com/abi-jey/simple-rdp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/abi-jey/simple-rdp/branch/main/graph/badge.svg)](https://codecov.io/gh/abi-jey/simple-rdp)
[![PyPI](https://img.shields.io/pypi/v/simple-rdp)](https://pypi.org/project/simple-rdp/)
[![Python](https://img.shields.io/pypi/pyversions/simple-rdp)](https://pypi.org/project/simple-rdp/)

## Overview

Unlike traditional RDP clients, Simple RDP does not provide an interactive session. Instead, it exposes screen capture and input transmission capabilities for building automation workflows.

## Features

<div class="grid cards" markdown>

-   :material-camera:{ .lg .middle } **Screen Capture**

    ---

    Capture the remote desktop screen as PIL Images with up to 30 FPS performance

    [:octicons-arrow-right-24: Learn more](guide/screen-capture.md)

-   :material-mouse:{ .lg .middle } **Mouse Input**

    ---

    Send mouse movements, clicks, drags, and wheel scrolling with precise control

    [:octicons-arrow-right-24: Learn more](guide/mouse-input.md)

-   :material-keyboard:{ .lg .middle } **Keyboard Input**

    ---

    Send keyboard keys, type text, and execute key combinations

    [:octicons-arrow-right-24: Learn more](guide/keyboard-input.md)

-   :material-lock:{ .lg .middle } **NLA/CredSSP Authentication**

    ---

    Full support for Network Level Authentication with NTLM

    [:octicons-arrow-right-24: Quick start](getting-started/quickstart.md)

-   :material-lightning-bolt:{ .lg .middle } **Async Support**

    ---

    Built with asyncio for non-blocking operations and high concurrency

    [:octicons-arrow-right-24: API Reference](api/client.md)

-   :material-rocket-launch:{ .lg .middle } **High Performance**

    ---

    Native Rust extension for fast RLE bitmap decompression

    [:octicons-arrow-right-24: Performance](development/performance.md)

</div>

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
        img = await client.screenshot()  # (1)!
        img.save("desktop.png")
        
        # Click somewhere
        await client.mouse_click(500, 300)  # (2)!
        
        # Type some text
        await client.send_text("Hello, World!")  # (3)!


asyncio.run(main())
```

1.  :material-image: Returns a PIL `Image` object that can be saved, processed, or analyzed
2.  :material-mouse: Coordinates are relative to the top-left corner of the desktop
3.  :material-keyboard: Sends each character as a Unicode key event

## Requirements

!!! info "System Requirements"
    - **Python 3.11+** — Required for modern async features
    - **Windows RDP Server** — Must have NLA (Network Level Authentication) enabled

!!! warning "Security Notice"
    This library does **NOT** validate TLS certificates when connecting to RDP servers.
    Only use in trusted network environments.

## Next Steps

<div class="grid cards" markdown>

-   [:material-download: **Installation**](getting-started/installation.md)
    
    Get Simple RDP installed with pip

-   [:material-rocket-launch: **Quick Start**](getting-started/quickstart.md)
    
    Connect to your first RDP server

-   [:material-api: **API Reference**](api/client.md)
    
    Full API documentation

</div>
