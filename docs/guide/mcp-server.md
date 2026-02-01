# MCP Server

Simple RDP includes an MCP (Model Context Protocol) server that exposes RDP client capabilities as tools for LLM agents.

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) is an open protocol that enables seamless integration between LLM applications and external data sources and tools. With the Simple RDP MCP server, AI agents can interact with remote Windows desktops.

## Installation

=== "PyPI (Recommended)"

    Install Simple RDP with the MCP extra from PyPI:

    ```bash
    pip install simple-rdp[mcp]
    ```

    Or with pipx for isolated installation:

    ```bash
    pipx install simple-rdp[mcp]
    ```

=== "From Source"

    Clone and install from source:

    ```bash
    git clone https://github.com/abi-jey/simple-rdp.git
    cd simple-rdp
    pip install -e .[mcp]
    ```

    Or with poetry:

    ```bash
    git clone https://github.com/abi-jey/simple-rdp.git
    cd simple-rdp
    poetry install --extras mcp
    ```

## Running the Server

The MCP server connects to an RDP server on startup. You can provide connection parameters via **CLI arguments** or **environment variables**.

### Using CLI Arguments

Pass RDP connection parameters directly as command line arguments:

```bash
simple-rdp-mcp --host 192.168.1.100 --user admin --password secret
```

All available options:

| Argument | Description | Default |
|----------|-------------|---------|
| `--host` | RDP server hostname or IP | Required |
| `--user`, `--username` | Username for authentication | - |
| `--password`, `--pass` | Password for authentication | - |
| `--domain` | Windows domain | - |
| `--port` | RDP port | 3389 |
| `--width` | Desktop width in pixels | 1920 |
| `--height` | Desktop height in pixels | 1080 |
| `--record`, `--record-session` | Path to save session recording | - |

Example with all options:

```bash
simple-rdp-mcp \
    --host 192.168.1.100 \
    --user admin \
    --password secret \
    --domain MYDOMAIN \
    --port 3389 \
    --width 1920 \
    --height 1080 \
    --record /tmp/session.mp4
```

### Using Environment Variables

Environment variables are used as fallbacks when CLI arguments are not provided:

```bash
export RDP_HOST=192.168.1.100    # Required: RDP server hostname
export RDP_USER=your_username    # Username for authentication
export RDP_PASS=your_password    # Password for authentication
export RDP_DOMAIN=MYDOMAIN       # Optional: Windows domain
export RDP_PORT=3389             # Optional: default 3389
export RDP_WIDTH=1920            # Optional: default 1920
export RDP_HEIGHT=1080           # Optional: default 1080
export RDP_RECORD_SESSION=/path/to/recording.mp4  # Optional: session recording

# Then simply run:
simple-rdp-mcp
```

### Using FastMCP CLI

When using the FastMCP CLI, pass arguments after `--`:

```bash
# With HTTP transport
fastmcp run simple_rdp_mcp.server:mcp --transport http --port 8000 -- \
    --host 192.168.1.100 --user admin --password secret

# With auto-reload for development
fastmcp run simple_rdp_mcp.server:mcp --reload -- \
    --host 192.168.1.100 --user admin --password secret
```

## Available Tools

### `rdp_screenshot`

Capture a screenshot of the remote desktop.

**Returns:** PNG image of the current screen.

### `rdp_status`

Get the current RDP connection status.

**Returns:** Connection status, host, desktop dimensions, and recording status.

### `rdp_mouse_move`

Move the mouse cursor to a specific position.

**Parameters:**

- `x`: X coordinate (pixels from left edge)
- `y`: Y coordinate (pixels from top edge)

### `rdp_mouse_click`

Click the mouse at a specific position.

**Parameters:**

- `x`: X coordinate
- `y`: Y coordinate
- `button`: Mouse button - "left", "right", or "middle" (default: "left")
- `double_click`: Whether to double-click (default: false)

### `rdp_mouse_drag`

Drag the mouse from one position to another.

**Parameters:**

- `start_x`: Starting X coordinate
- `start_y`: Starting Y coordinate
- `end_x`: Ending X coordinate
- `end_y`: Ending Y coordinate
- `button`: Mouse button to hold (default: "left")

### `rdp_mouse_wheel`

Scroll the mouse wheel at a specific position.

**Parameters:**

- `x`: X coordinate
- `y`: Y coordinate
- `delta`: Scroll amount (positive=up, negative=down)

### `rdp_type_text`

Type text on the remote desktop.

**Parameters:**

- `text`: Text to type (supports Unicode)

### `rdp_send_key`

Send a keyboard key press.

**Parameters:**

- `key`: Key to send. Can be:
    - A single character (e.g., "a", "A", "1")
    - A key name: "enter", "tab", "escape", "backspace", "delete", arrow keys, F1-F12, etc.
    - A hex scancode (e.g., "0x1C" for Enter)
- `modifiers`: List of modifier keys to hold: "ctrl", "alt", "shift", "win"

### `rdp_start_recording`

Start recording the session to video. Use this to record specific actions.

### `rdp_stop_recording`

Stop recording and save to file.

**Parameters:**

- `save_path`: Path to save the recording (e.g., '/tmp/session.mp4')

## Usage with Claude Desktop

Add the MCP server to your Claude Desktop configuration (`~/.config/claude/claude_desktop_config.json`):

=== "With Arguments"

    ```json
    {
      "mcpServers": {
        "simple-rdp": {
          "command": "simple-rdp-mcp",
          "args": [
            "--host", "192.168.1.100",
            "--user", "your_username",
            "--password", "your_password"
          ]
        }
      }
    }
    ```

=== "With Environment Variables"

    ```json
    {
      "mcpServers": {
        "simple-rdp": {
          "command": "simple-rdp-mcp",
          "env": {
            "RDP_HOST": "192.168.1.100",
            "RDP_USER": "your_username",
            "RDP_PASS": "your_password"
          }
        }
      }
    }
    ```

=== "With Session Recording"

    ```json
    {
      "mcpServers": {
        "simple-rdp": {
          "command": "simple-rdp-mcp",
          "args": [
            "--host", "192.168.1.100",
            "--user", "your_username",
            "--password", "your_password",
            "--record", "/tmp/rdp_session.mp4"
          ]
        }
      }
    }
    ```

## Programmatic Usage (without MCP)

The same functions are available for direct Python use without the MCP server:

```python
import asyncio
from simple_rdp_mcp import (
    connect,
    disconnect,
    screenshot,
    mouse_click,
    type_text,
    send_key,
)

async def automate_rdp():
    # Connect to RDP server
    await connect(
        host="192.168.1.100",
        username="admin",
        password="password",
        record_session="/tmp/session.mp4",  # Optional recording
    )
    
    # Take a screenshot
    img = await screenshot()
    img.save("desktop.png")
    
    # Click on something
    await mouse_click(100, 200)
    
    # Type some text
    await type_text("Hello, World!")
    
    # Press Enter
    await send_key("enter")
    
    # Use keyboard shortcuts
    await send_key("s", modifiers=["ctrl"])  # Ctrl+S
    
    # Disconnect (saves recording if enabled)
    await disconnect()

asyncio.run(automate_rdp())
```

### Using with Your Own Async Loop

```python
import asyncio
from simple_rdp_mcp import connect, screenshot, mouse_click, disconnect

async def main():
    await connect("192.168.1.100", "user", "pass")
    
    # Run your automation
    for i in range(10):
        img = await screenshot()
        print(f"Frame {i}: {img.size}")
        await asyncio.sleep(1)
    
    await disconnect()

# Run in existing event loop
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```

## Key Differences from MCP Mode

| Feature | MCP Server Mode | Programmatic Mode |
|---------|----------------|-------------------|
| Connection | Auto-connect on startup via args/env | Manual `connect()` call |
| Recording | Via `--record` arg or `RDP_RECORD_SESSION` | Via `record_session` parameter |
| Cleanup | Auto-disconnect on shutdown | Manual `disconnect()` call |
| Tools | MCP tool wrappers | Direct async functions |

## Security Considerations

!!! warning "Security Warning"
    
    - RDP credentials can be passed via CLI arguments or environment variables
    - Environment variables are preferred for sensitive credentials in production
    - The server maintains a single active RDP connection
    - This library does NOT validate TLS certificates
    - Only use in trusted environments
    - No artifacts are saved unless explicitly requested (recording)
