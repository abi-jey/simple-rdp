# MCP Server

Simple RDP includes an MCP (Model Context Protocol) server that exposes RDP client capabilities as tools for LLM agents.

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) is an open protocol that enables seamless integration between LLM applications and external data sources and tools. With the Simple RDP MCP server, AI agents can interact with remote Windows desktops.

## Installation

Install Simple RDP with the MCP extra:

```bash
pip install simple-rdp[mcp]
# or with poetry
poetry install --extras mcp
```

## Running the Server

### Using the CLI

```bash
# Run with stdio transport (default)
simple-rdp-mcp

# Or using fastmcp CLI
fastmcp run simple_rdp_mcp.server:mcp

# Run with HTTP transport
fastmcp run simple_rdp_mcp.server:mcp --transport http --port 8000
```

### As a Python Module

```python
from simple_rdp_mcp import mcp

if __name__ == "__main__":
    mcp.run()
```

## Configuration

The MCP server uses environment variables for default RDP connection settings:

```bash
export RDP_HOST=192.168.1.100
export RDP_USER=your_username
export RDP_PASS=your_password
export RDP_DOMAIN=MYDOMAIN  # optional
```

You can also provide credentials directly when calling `rdp_connect()`.

## Available Tools

### `rdp_connect`

Connect to a Windows RDP server.

**Parameters:**

- `host` (optional): RDP server hostname. Uses `RDP_HOST` env var if not provided.
- `username` (optional): Username. Uses `RDP_USER` env var if not provided.
- `password` (optional): Password. Uses `RDP_PASS` env var if not provided.
- `domain` (optional): Windows domain. Uses `RDP_DOMAIN` env var if not provided.
- `port`: RDP port (default: 3389)
- `width`: Desktop width in pixels (default: 1920)
- `height`: Desktop height in pixels (default: 1080)

### `rdp_disconnect`

Disconnect from the current RDP session.

### `rdp_status`

Get the current RDP connection status.

**Returns:** Connection status, host, and desktop dimensions.

### `rdp_screenshot`

Capture a screenshot of the remote desktop.

**Returns:** PNG image of the current screen.

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

**Examples:**

```python
# Send Enter key
await rdp_send_key("enter")

# Copy (Ctrl+C)
await rdp_send_key("c", modifiers=["ctrl"])

# Alt+Tab
await rdp_send_key("tab", modifiers=["alt"])

# Ctrl+Alt+Delete
await rdp_send_key("delete", modifiers=["ctrl", "alt"])
```

## Usage with Claude Desktop

Add the MCP server to your Claude Desktop configuration:

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

## Example Agent Workflow

Here's how an LLM agent might use the RDP tools:

1. **Connect**: `rdp_connect(host="192.168.1.100", username="admin", password="****")`
2. **Take screenshot**: `rdp_screenshot()` - to see the current desktop state
3. **Click on Start menu**: `rdp_mouse_click(x=30, y=1060)`
4. **Take screenshot**: to see the Start menu opened
5. **Type search**: `rdp_type_text("notepad")`
6. **Press Enter**: `rdp_send_key("enter")`
7. **Take screenshot**: to verify Notepad opened
8. **Type content**: `rdp_type_text("Hello from AI!")`
9. **Save file**: `rdp_send_key("s", modifiers=["ctrl"])`
10. **Disconnect**: `rdp_disconnect()`

## Security Considerations

!!! warning "Security Warning"
    
    - RDP credentials are passed through the MCP protocol
    - The server maintains a single active RDP connection
    - This library does NOT validate TLS certificates
    - Only use in trusted environments
