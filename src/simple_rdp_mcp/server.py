"""
Simple RDP MCP Server.

This module provides an MCP server that exposes RDP client capabilities
as tools for LLM agents to interact with remote Windows desktops.
"""

import base64
import io
import os
from typing import Annotated

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.utilities.types import Image as MCPImage
from pydantic import Field

from simple_rdp import RDPClient

load_dotenv()

# Create the MCP server
mcp = FastMCP(
    name="Simple RDP",
    instructions="""
    This MCP server provides tools to interact with a remote Windows desktop via RDP.
    
    You can:
    - Connect to an RDP server and take screenshots
    - Move and click the mouse at specific coordinates
    - Type text and send keyboard keys
    - Drag the mouse from one position to another
    
    Typical workflow:
    1. Connect to the RDP server using rdp_connect()
    2. Take a screenshot to see the current state with rdp_screenshot()
    3. Interact using mouse and keyboard tools
    4. Take screenshots to verify your actions
    5. Disconnect when done with rdp_disconnect()
    """,
)

# Global RDP client instance
_rdp_client: RDPClient | None = None


def _get_client() -> RDPClient:
    """Get the current RDP client, raising an error if not connected."""
    if _rdp_client is None or not _rdp_client.is_connected:
        raise RuntimeError(
            "Not connected to RDP server. Use rdp_connect() first."
        )
    return _rdp_client


@mcp.tool(
    annotations={
        "title": "Connect to RDP Server",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    }
)
async def rdp_connect(
    host: Annotated[str | None, "RDP server hostname or IP. Uses RDP_HOST env var if not provided."] = None,
    username: Annotated[str | None, "Username for authentication. Uses RDP_USER env var if not provided."] = None,
    password: Annotated[str | None, "Password for authentication. Uses RDP_PASS env var if not provided."] = None,
    domain: Annotated[str | None, "Windows domain (optional). Uses RDP_DOMAIN env var if not provided."] = None,
    port: Annotated[int, "RDP server port"] = 3389,
    width: Annotated[int, "Desktop width in pixels"] = 1920,
    height: Annotated[int, "Desktop height in pixels"] = 1080,
) -> dict[str, str | int | bool]:
    """
    Connect to a Windows RDP server.
    
    Establishes an RDP connection using the provided credentials or environment variables.
    Environment variables used as fallbacks: RDP_HOST, RDP_USER, RDP_PASS, RDP_DOMAIN.
    
    Returns connection status and desktop dimensions.
    """
    global _rdp_client
    
    # Use environment variables as fallbacks
    host = host or os.getenv("RDP_HOST")
    username = username or os.getenv("RDP_USER")
    password = password or os.getenv("RDP_PASS")
    domain = domain or os.getenv("RDP_DOMAIN")
    
    if not host:
        raise ValueError("Host is required. Provide it as parameter or set RDP_HOST environment variable.")
    
    # Disconnect existing connection if any
    if _rdp_client is not None and _rdp_client.is_connected:
        await _rdp_client.disconnect()
    
    # Create and connect
    _rdp_client = RDPClient(
        host=host,
        port=port,
        username=username,
        password=password,
        domain=domain,
        width=width,
        height=height,
    )
    
    await _rdp_client.connect()
    
    return {
        "status": "connected",
        "host": host,
        "width": _rdp_client.width,
        "height": _rdp_client.height,
        "connected": True,
    }


@mcp.tool(
    annotations={
        "title": "Disconnect from RDP Server",
        "readOnlyHint": False,
        "destructiveHint": False,
    }
)
async def rdp_disconnect() -> dict[str, str | bool]:
    """
    Disconnect from the current RDP session.
    
    Cleanly closes the RDP connection. Safe to call even if not connected.
    """
    global _rdp_client
    
    if _rdp_client is not None:
        if _rdp_client.is_connected:
            await _rdp_client.disconnect()
        _rdp_client = None
    
    return {
        "status": "disconnected",
        "connected": False,
    }


@mcp.tool(
    annotations={
        "title": "Get Connection Status",
        "readOnlyHint": True,
    }
)
async def rdp_status() -> dict[str, str | int | bool | None]:
    """
    Get the current RDP connection status.
    
    Returns whether connected and desktop dimensions if available.
    """
    if _rdp_client is None:
        return {
            "connected": False,
            "host": None,
            "width": None,
            "height": None,
        }
    
    return {
        "connected": _rdp_client.is_connected,
        "host": _rdp_client.host,
        "width": _rdp_client.width if _rdp_client.is_connected else None,
        "height": _rdp_client.height if _rdp_client.is_connected else None,
    }


@mcp.tool(
    annotations={
        "title": "Take Screenshot",
        "readOnlyHint": True,
    }
)
async def rdp_screenshot() -> MCPImage:
    """
    Capture a screenshot of the remote desktop.
    
    Returns the current screen as an image. Use this to see what's on
    the remote desktop before and after performing actions.
    """
    client = _get_client()
    img = await client.screenshot()
    
    # Convert PIL Image to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()
    
    return MCPImage(data=image_bytes, format="png")


@mcp.tool(
    annotations={
        "title": "Move Mouse",
        "readOnlyHint": False,
    }
)
async def rdp_mouse_move(
    x: Annotated[int, Field(description="X coordinate (pixels from left edge)", ge=0)],
    y: Annotated[int, Field(description="Y coordinate (pixels from top edge)", ge=0)],
) -> dict[str, str | int]:
    """
    Move the mouse cursor to a specific position.
    
    Coordinates are in pixels from the top-left corner of the desktop.
    """
    client = _get_client()
    await client.mouse_move(x, y)
    
    return {
        "action": "mouse_move",
        "x": x,
        "y": y,
    }


@mcp.tool(
    annotations={
        "title": "Mouse Click",
        "readOnlyHint": False,
    }
)
async def rdp_mouse_click(
    x: Annotated[int, Field(description="X coordinate for the click", ge=0)],
    y: Annotated[int, Field(description="Y coordinate for the click", ge=0)],
    button: Annotated[str, "Mouse button: 'left', 'right', or 'middle'"] = "left",
    double_click: Annotated[bool, "Whether to perform a double-click"] = False,
) -> dict[str, str | int | bool]:
    """
    Click the mouse at a specific position.
    
    Moves to the position and performs a click with the specified button.
    Use double_click=True for double-clicking (e.g., to open files).
    """
    client = _get_client()
    
    # Convert button name to number
    button_map = {"left": 1, "right": 2, "middle": 3}
    button_num = button_map.get(button.lower(), 1)
    
    await client.mouse_click(x, y, button=button_num, double_click=double_click)
    
    return {
        "action": "double_click" if double_click else "click",
        "x": x,
        "y": y,
        "button": button,
    }


@mcp.tool(
    annotations={
        "title": "Mouse Drag",
        "readOnlyHint": False,
    }
)
async def rdp_mouse_drag(
    start_x: Annotated[int, Field(description="Starting X coordinate", ge=0)],
    start_y: Annotated[int, Field(description="Starting Y coordinate", ge=0)],
    end_x: Annotated[int, Field(description="Ending X coordinate", ge=0)],
    end_y: Annotated[int, Field(description="Ending Y coordinate", ge=0)],
    button: Annotated[str, "Mouse button to hold: 'left', 'right', or 'middle'"] = "left",
) -> dict[str, str | int]:
    """
    Drag the mouse from one position to another.
    
    Useful for:
    - Dragging files or windows
    - Selecting text
    - Drawing in applications
    - Resizing windows
    """
    client = _get_client()
    
    button_map = {"left": 1, "right": 2, "middle": 3}
    button_num = button_map.get(button.lower(), 1)
    
    await client.mouse_drag(start_x, start_y, end_x, end_y, button=button_num)
    
    return {
        "action": "drag",
        "start_x": start_x,
        "start_y": start_y,
        "end_x": end_x,
        "end_y": end_y,
        "button": button,
    }


@mcp.tool(
    annotations={
        "title": "Mouse Wheel",
        "readOnlyHint": False,
    }
)
async def rdp_mouse_wheel(
    x: Annotated[int, Field(description="X coordinate for the scroll", ge=0)],
    y: Annotated[int, Field(description="Y coordinate for the scroll", ge=0)],
    delta: Annotated[int, "Scroll amount: positive=up, negative=down. Each unit is ~3 lines."],
) -> dict[str, str | int]:
    """
    Scroll the mouse wheel at a specific position.
    
    Positive delta scrolls up, negative scrolls down.
    A delta of 120 is approximately one notch on a standard mouse wheel.
    """
    client = _get_client()
    await client.mouse_wheel(x, y, delta)
    
    return {
        "action": "wheel",
        "x": x,
        "y": y,
        "delta": delta,
    }


@mcp.tool(
    annotations={
        "title": "Type Text",
        "readOnlyHint": False,
    }
)
async def rdp_type_text(
    text: Annotated[str, "Text to type. Supports Unicode characters."],
) -> dict[str, str | int]:
    """
    Type text on the remote desktop.
    
    Sends the text as keyboard input. Supports all Unicode characters.
    For special keys like Enter or Tab, use rdp_send_key() instead.
    """
    client = _get_client()
    await client.send_text(text)
    
    return {
        "action": "type",
        "text": text,
        "length": len(text),
    }


@mcp.tool(
    annotations={
        "title": "Send Key",
        "readOnlyHint": False,
    }
)
async def rdp_send_key(
    key: Annotated[str, """Key to send. Can be:
- A single character (e.g., 'a', 'A', '1')
- A key name: 'enter', 'tab', 'escape', 'backspace', 'delete',
  'up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown',
  'f1'-'f12', 'insert', 'space', 'capslock', 'numlock', 'scrolllock',
  'printscreen', 'pause', 'win', 'lwin', 'rwin', 'apps', 'menu'
- A hex scancode (e.g., '0x1C' for Enter)"""],
    modifiers: Annotated[list[str] | None, "Modifier keys to hold: 'ctrl', 'alt', 'shift', 'win'"] = None,
) -> dict[str, str | list[str] | None]:
    """
    Send a keyboard key press.
    
    For typing regular text, use rdp_type_text() instead.
    This is for special keys and key combinations like Ctrl+C.
    
    Examples:
    - Send Enter: rdp_send_key("enter")
    - Copy (Ctrl+C): rdp_send_key("c", modifiers=["ctrl"])
    - Alt+Tab: rdp_send_key("tab", modifiers=["alt"])
    - Ctrl+Alt+Delete: rdp_send_key("delete", modifiers=["ctrl", "alt"])
    """
    client = _get_client()
    
    # Key name to scancode mapping
    key_map: dict[str, int] = {
        "escape": 0x01, "esc": 0x01,
        "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
        "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
        "minus": 0x0C, "equals": 0x0D,
        "backspace": 0x0E, "bs": 0x0E,
        "tab": 0x0F,
        "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14,
        "y": 0x15, "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19,
        "enter": 0x1C, "return": 0x1C,
        "ctrl": 0x1D, "lctrl": 0x1D,
        "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22,
        "h": 0x23, "j": 0x24, "k": 0x25, "l": 0x26,
        "shift": 0x2A, "lshift": 0x2A,
        "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F, "b": 0x30,
        "n": 0x31, "m": 0x32,
        "rshift": 0x36,
        "alt": 0x38, "lalt": 0x38,
        "space": 0x39,
        "capslock": 0x3A, "caps": 0x3A,
        "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F,
        "f6": 0x40, "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44,
        "numlock": 0x45,
        "scrolllock": 0x46,
        "home": 0x47, "up": 0x48, "pageup": 0x49, "pgup": 0x49,
        "left": 0x4B, "right": 0x4D,
        "end": 0x4F, "down": 0x50, "pagedown": 0x51, "pgdn": 0x51,
        "insert": 0x52, "ins": 0x52,
        "delete": 0x53, "del": 0x53,
        "f11": 0x57, "f12": 0x58,
        "win": 0xE05B, "lwin": 0xE05B, "rwin": 0xE05C,
        "apps": 0xE05D, "menu": 0xE05D,
        "rctrl": 0xE01D,
        "ralt": 0xE038,
        "printscreen": 0xE037, "prtsc": 0xE037,
        "pause": 0xE11D,
    }
    
    modifier_map: dict[str, int] = {
        "ctrl": 0x1D,
        "alt": 0x38,
        "shift": 0x2A,
        "win": 0xE05B,
    }
    
    # Determine the key to send
    key_lower = key.lower()
    
    if key_lower.startswith("0x"):
        # Hex scancode
        scancode = int(key_lower, 16)
    elif key_lower in key_map:
        scancode = key_map[key_lower]
    elif len(key) == 1:
        # Single character - send as unicode
        # Press modifiers first
        if modifiers:
            for mod in modifiers:
                mod_scancode = modifier_map.get(mod.lower())
                if mod_scancode:
                    await client.send_key(mod_scancode, is_press=True, is_release=False)
        
        # Send the character
        await client.send_key(key, is_press=True, is_release=True)
        
        # Release modifiers
        if modifiers:
            for mod in reversed(modifiers):
                mod_scancode = modifier_map.get(mod.lower())
                if mod_scancode:
                    await client.send_key(mod_scancode, is_press=False, is_release=True)
        
        return {
            "action": "key",
            "key": key,
            "modifiers": modifiers,
        }
    else:
        raise ValueError(f"Unknown key: {key}. Use a key name, single character, or hex scancode.")
    
    # Press modifiers
    if modifiers:
        for mod in modifiers:
            mod_scancode = modifier_map.get(mod.lower())
            if mod_scancode:
                await client.send_key(mod_scancode, is_press=True, is_release=False)
    
    # Send the key
    await client.send_key(scancode, is_press=True, is_release=True)
    
    # Release modifiers
    if modifiers:
        for mod in reversed(modifiers):
            mod_scancode = modifier_map.get(mod.lower())
            if mod_scancode:
                await client.send_key(mod_scancode, is_press=False, is_release=True)
    
    return {
        "action": "key",
        "key": key,
        "modifiers": modifiers,
    }


# Entry point for running the server directly
if __name__ == "__main__":
    mcp.run()
