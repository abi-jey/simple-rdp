# Simple RDP

[![CI](https://github.com/abi-jey/simple-rdp/actions/workflows/ci.yml/badge.svg)](https://github.com/abi-jey/simple-rdp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/abi-jey/simple-rdp/branch/main/graph/badge.svg)](https://codecov.io/gh/abi-jey/simple-rdp)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://abi-jey.github.io/simple-rdp/)

A Python RDP client library designed for automation purposes. Unlike traditional RDP clients, Simple RDP does not provide an interactive session. Instead, it exposes screen capture and input transmission capabilities for building automation workflows.

> [!CAUTION]
> **Security Warning: No TLS Certificate Validation**
> 
> This library does **NOT** validate TLS certificates when connecting to RDP servers. This means:
> - Connections are vulnerable to man-in-the-middle (MITM) attacks
> - Server identity is not verified
> - **Do not use in production environments or over untrusted networks**
> 
> This limitation is known and will be addressed in a future release. For now, only use this library in trusted network environments (e.g., local development, isolated lab networks).

## Features

- **Screen Capture**: Capture the remote desktop screen as PIL Images
- **Input Transmission**: Send mouse movements, clicks, and keyboard input
- **NLA/CredSSP Authentication**: Full support for Network Level Authentication
- **Automation-Focused**: Built specifically for automation, not interactive use
- **Async Support**: Built with asyncio for non-blocking operations

## Requirements

- Python 3.11+
- Windows RDP server with NLA enabled

## Installation

```bash
poetry install
```

## Configuration

Create a `.env` file in the project root with your RDP connection settings:

```bash
cp .env.example .env
# Edit .env with your settings
```

```
RDP_HOST=192.168.1.100
RDP_USER=your_username
RDP_PASS=your_password
```

## Usage

### Basic Connection and Screenshot

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
        width=1920,
        height=1080,
    ) as client:
        # Wait for screen to fully render
        await asyncio.sleep(2)
        
        # Capture and save screenshot
        await client.save_screenshot("desktop.png")
        
        # Or get PIL Image directly
        img = await client.screenshot()
        print(f"Captured: {img.size}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Sending Input

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
        
        # Mouse operations
        await client.mouse_move(100, 200)
        await client.mouse_click(100, 200)  # Left click
        await client.mouse_click(100, 200, button=2)  # Right click
        await client.mouse_click(100, 200, double_click=True)  # Double click
        await client.mouse_drag(100, 100, 300, 300)  # Drag from (100,100) to (300,300)
        
        # Keyboard operations
        await client.send_text("Hello, World!")  # Type text
        await client.send_key(0x1C)  # Send Enter key (scancode)
        await client.send_key("a")  # Send 'a' as unicode


if __name__ == "__main__":
    asyncio.run(main())
```

### Manual Connection Management

```python
import asyncio
import os

from dotenv import load_dotenv

from simple_rdp import RDPClient

load_dotenv()


async def main():
    client = RDPClient(
        host=os.environ["RDP_HOST"],
        username=os.environ["RDP_USER"],
        password=os.environ["RDP_PASS"],
        domain="MYDOMAIN",  # Optional domain
    )
    
    try:
        await client.connect()
        print(f"Connected: {client.width}x{client.height}")
        
        await asyncio.sleep(2)
        await client.save_screenshot("screenshot.png")
        
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

## API Reference

### RDPClient

#### Constructor

```python
RDPClient(
    host: str,
    port: int = 3389,
    username: str | None = None,
    password: str | None = None,
    domain: str | None = None,
    width: int = 1920,
    height: int = 1080,
    color_depth: int = 32,
)
```

#### Properties

- `host` - The RDP server hostname
- `port` - The RDP server port
- `is_connected` - Whether the client is connected
- `width` - Desktop width in pixels
- `height` - Desktop height in pixels

#### Methods

- `connect()` - Establish connection to the RDP server
- `disconnect()` - Disconnect from the server
- `screenshot()` - Capture the current screen as a PIL Image
- `save_screenshot(path)` - Save a screenshot to a file
- `send_key(key, is_press=True, is_release=True)` - Send a keyboard key
- `send_text(text)` - Type a text string
- `mouse_move(x, y)` - Move the mouse to a position
- `mouse_click(x, y, button=1, double_click=False)` - Click at a position
- `mouse_drag(x1, y1, x2, y2, button=1)` - Drag from one position to another

## Development

### Setup

```bash
poetry install

# Optional: Install Rust RLE acceleration (100x faster)
cd rle-fast && maturin develop --release && cd ..
```

### Running Tests

```bash
# Unit tests (no RDP connection needed)
poetry run pytest tests/ --ignore=tests/e2e

# E2E tests (requires RDP server)
cp .env.example .env  # Edit with your credentials
poetry run pytest tests/e2e/

# With coverage
poetry run pytest tests/ --ignore=tests/e2e --cov=src/simple_rdp
```

### Linting and Type Checking

```bash
poetry run ruff check src/
poetry run mypy src/
```

### Pre-commit Hooks

```bash
poetry run pre-commit install
poetry run pre-commit run --all-files
```

## Project Structure

```
simple-rdp/
├── src/
│   └── simple_rdp/
│       ├── __init__.py      # Package exports
│       ├── client.py        # Main RDPClient class
│       ├── capabilities.py  # RDP capability sets
│       ├── credssp.py       # CredSSP/NLA authentication
│       ├── mcs.py           # MCS/T.125 layer
│       ├── pdu.py           # RDP PDU layer
│       ├── rle.py           # RLE bitmap decompression
│       ├── screen.py        # Display class for video encoding
│       └── input.py         # Input handling utilities
├── tests/
│   ├── test_client.py       # Client unit tests
│   ├── test_screen.py       # Display unit tests
│   ├── test_input.py        # Input unit tests
│   └── e2e/                  # End-to-end tests (need real RDP)
│       ├── test_basic_connection.py
│       ├── test_video_recording.py
│       ├── test_performance.py
│       └── test_display.py
├── agents/
│   └── tools/
│       └── analyze_image.py  # AI image analysis tool
├── rle-fast/                 # Rust RLE acceleration (optional)
│   ├── Cargo.toml
│   ├── pyproject.toml
│   └── src/lib.rs
├── .env.example              # Environment template
├── pyproject.toml
└── README.md
```

## Performance

The library includes optional Rust acceleration for RLE bitmap decompression:

| Mode | Screenshot FPS | Event Loop Usage |
|------|---------------|------------------|
| Pure Python | ~15 FPS | ~50% |
| Rust + GIL release | ~30 FPS | ~10% |

Install Rust acceleration with:
```bash
cd rle-fast && maturin develop --release
```

The library automatically uses Rust when available, falling back to pure Python.

## Protocol Support

- X.224 Connection Sequence
- TLS/SSL encryption
- CredSSP v6 (NLA authentication with NTLM)
- MCS Connect/Channel Join
- RDP capability exchange
- Fast-Path output (bitmap updates)
- Interleaved RLE bitmap decompression
- Slow-path input (keyboard/mouse)

## License

MIT
