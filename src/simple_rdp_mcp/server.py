"""
Simple RDP MCP Server.

This module provides an MCP server that exposes RDP client capabilities
as tools for LLM agents to interact with remote Windows desktops.

The server connects to an RDP server on startup and provides tools for:
- Taking screenshots
- Mouse movement, clicks, and drags
- Keyboard input (typing and key presses)
- Session recording (optional)

Usage:
    # With CLI arguments (recommended)
    simple-rdp-mcp --host 192.168.1.100 --user username --password password

    # With environment variables (fallback)
    export RDP_HOST=192.168.1.100
    export RDP_USER=username
    export RDP_PASS=password
    simple-rdp-mcp

    # With FastMCP CLI (pass args after --)
    fastmcp run simple_rdp_mcp.server:mcp -- --host 192.168.1.100 --user admin

    # With session recording
    simple-rdp-mcp --host 192.168.1.100 --user admin --record /path/to/recording.mp4
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from dataclasses import field
from typing import Annotated

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.utilities.types import Image as MCPImage
from PIL import Image
from pydantic import Field

from simple_rdp import RDPClient
from simple_rdp.display import Display

load_dotenv()


# =============================================================================
# CLI Argument Parser
# =============================================================================

# Global to store CLI args parsed at startup
_cli_args: argparse.Namespace | None = None


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for RDP connection."""
    parser = argparse.ArgumentParser(
        description="Simple RDP MCP Server - Expose RDP client as MCP tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Connect with CLI arguments
  simple-rdp-mcp --host 192.168.1.100 --user admin --password secret

  # Using environment variables (fallback)
  export RDP_HOST=192.168.1.100
  export RDP_USER=admin
  export RDP_PASS=secret
  simple-rdp-mcp

  # Using fastmcp CLI with arguments
  fastmcp run simple_rdp_mcp.server:mcp -- --host 192.168.1.100 --user admin
""",
    )

    parser.add_argument(
        "--host",
        help="RDP server hostname or IP (env: RDP_HOST)",
        default=os.getenv("RDP_HOST"),
    )
    parser.add_argument(
        "--user",
        "--username",
        dest="username",
        help="Username for authentication (env: RDP_USER)",
        default=os.getenv("RDP_USER"),
    )
    parser.add_argument(
        "--password",
        "--pass",
        dest="password",
        help="Password for authentication (env: RDP_PASS)",
        default=os.getenv("RDP_PASS"),
    )
    parser.add_argument(
        "--domain",
        help="Windows domain (env: RDP_DOMAIN)",
        default=os.getenv("RDP_DOMAIN"),
    )
    parser.add_argument(
        "--port",
        type=int,
        help="RDP port (default: 3389, env: RDP_PORT)",
        default=int(os.getenv("RDP_PORT", "3389")),
    )
    parser.add_argument(
        "--width",
        type=int,
        help="Desktop width in pixels (default: 1920, env: RDP_WIDTH)",
        default=int(os.getenv("RDP_WIDTH", "1920")),
    )
    parser.add_argument(
        "--height",
        type=int,
        help="Desktop height in pixels (default: 1080, env: RDP_HEIGHT)",
        default=int(os.getenv("RDP_HEIGHT", "1080")),
    )
    parser.add_argument(
        "--record",
        "--record-session",
        dest="record_session",
        help="Path to save session recording (env: RDP_RECORD_SESSION)",
        default=os.getenv("RDP_RECORD_SESSION"),
    )

    return parser.parse_args()


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class RDPConfig:
    """RDP connection configuration."""

    host: str
    username: str | None = None
    password: str | None = None
    domain: str | None = None
    port: int = 3389
    width: int = 1920
    height: int = 1080
    record_session: str | None = None  # Path to save session recording

    @classmethod
    def from_args(cls, args: argparse.Namespace | None = None) -> RDPConfig:
        """Create config from CLI arguments (with env var fallbacks)."""
        args = args or _cli_args

        # Use CLI args if available, otherwise fall back to env vars
        host = args.host if args else os.getenv("RDP_HOST")
        if not host:
            raise ValueError("RDP host is required. Use --host argument or set RDP_HOST environment variable.")

        return cls(
            host=host,
            username=args.username if args else os.getenv("RDP_USER"),
            password=args.password if args else os.getenv("RDP_PASS"),
            domain=args.domain if args else os.getenv("RDP_DOMAIN"),
            port=args.port if args else int(os.getenv("RDP_PORT", "3389")),
            width=args.width if args else int(os.getenv("RDP_WIDTH", "1920")),
            height=args.height if args else int(os.getenv("RDP_HEIGHT", "1080")),
            record_session=args.record_session if args else os.getenv("RDP_RECORD_SESSION"),
        )


# =============================================================================
# RDP Session Manager
# =============================================================================


@dataclass
class RDPSession:
    """Manages an active RDP session with optional recording."""

    client: RDPClient
    config: RDPConfig
    display: Display | None = None
    _recording: bool = field(default=False, init=False)
    _frame_task: asyncio.Task | None = field(default=None, init=False)

    @property
    def is_connected(self) -> bool:
        return self.client.is_connected

    @property
    def is_recording(self) -> bool:
        return self._recording

    async def start_recording(self) -> None:
        """Start recording the session."""
        if self._recording:
            return

        self.display = Display(
            width=self.config.width,
            height=self.config.height,
            fps=30,
        )
        await self.display.start_streaming()
        self._recording = True

        # Start background task to capture frames
        self._frame_task = asyncio.create_task(self._capture_frames())

    async def stop_recording(self, save_path: str | None = None) -> str | None:
        """Stop recording and optionally save to file."""
        if not self._recording:
            return None

        self._recording = False

        # Cancel frame capture task
        if self._frame_task:
            self._frame_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._frame_task
            self._frame_task = None

        # Stop streaming
        if self.display:
            await self.display.stop_streaming(record_to=save_path)
            self.display = None
            if save_path:
                return save_path

        return None

    async def _capture_frames(self) -> None:
        """Background task to capture frames for recording."""
        while self._recording and self.display:
            try:
                if self.client.is_connected:
                    img = await self.client.screenshot()
                    await self.display.add_frame(img)
                await asyncio.sleep(1 / 30)  # 30 fps
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.1)


# Global session
_session: RDPSession | None = None


def get_session() -> RDPSession:
    """Get the current session, raising an error if not connected."""
    if _session is None or not _session.is_connected:
        raise RuntimeError("Not connected to RDP server.")
    return _session


# =============================================================================
# Programmatic Connection (for direct use without MCP)
# =============================================================================


async def connect(
    host: str,
    username: str | None = None,
    password: str | None = None,
    domain: str | None = None,
    port: int = 3389,
    width: int = 1920,
    height: int = 1080,
    record_session: str | None = None,
) -> dict[str, str | int | bool]:
    """
    Connect to an RDP server programmatically.

    This is for direct Python usage, not through MCP.
    For MCP, the connection is established via environment variables on startup.

    Args:
        host: RDP server hostname or IP.
        username: Username for authentication.
        password: Password for authentication.
        domain: Windows domain (optional).
        port: RDP port (default: 3389).
        width: Desktop width in pixels.
        height: Desktop height in pixels.
        record_session: Path to save session recording (optional).

    Returns:
        Connection status and desktop dimensions.
    """
    global _session

    # Disconnect existing connection if any
    if _session is not None and _session.is_connected:
        await _session.client.disconnect()

    config = RDPConfig(
        host=host,
        username=username,
        password=password,
        domain=domain,
        port=port,
        width=width,
        height=height,
        record_session=record_session,
    )

    client = RDPClient(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        domain=config.domain,
        width=config.width,
        height=config.height,
    )

    await client.connect()

    _session = RDPSession(client=client, config=config)

    # Start recording if requested
    if record_session:
        await _session.start_recording()

    return {
        "status": "connected",
        "host": host,
        "width": client.width,
        "height": client.height,
        "connected": True,
        "recording": record_session is not None,
    }


async def disconnect() -> dict[str, str | bool | None]:
    """
    Disconnect from the current RDP session.

    Also stops and saves any active recording.

    Returns:
        Disconnection status.
    """
    global _session

    saved_path = None

    if _session is not None:
        # Stop recording if active
        if _session.is_recording and _session.config.record_session:
            saved_path = await _session.stop_recording(_session.config.record_session)

        # Disconnect
        if _session.is_connected:
            await _session.client.disconnect()

        _session = None

    return {
        "status": "disconnected",
        "connected": False,
        "saved_recording": saved_path,
    }


# =============================================================================
# Core Functions (usable without MCP)
# =============================================================================


async def screenshot() -> Image.Image:
    """
    Capture a screenshot of the remote desktop.

    Returns:
        PIL Image of the current screen.

    Raises:
        RuntimeError: If not connected to RDP server.
    """
    session = get_session()
    return await session.client.screenshot()


async def mouse_move(x: int, y: int) -> dict[str, str | int]:
    """
    Move the mouse cursor to a specific position.

    Args:
        x: X coordinate (pixels from left edge).
        y: Y coordinate (pixels from top edge).

    Returns:
        Action confirmation with coordinates.
    """
    session = get_session()
    await session.client.mouse_move(x, y)
    return {"action": "mouse_move", "x": x, "y": y}


async def mouse_click(
    x: int,
    y: int,
    button: str = "left",
    double_click: bool = False,
) -> dict[str, str | int | bool]:
    """
    Click the mouse at a specific position.

    Args:
        x: X coordinate for the click.
        y: Y coordinate for the click.
        button: Mouse button - "left", "right", or "middle".
        double_click: Whether to double-click.

    Returns:
        Action confirmation with coordinates and button.
    """
    session = get_session()
    button_map = {"left": 1, "right": 2, "middle": 3}
    button_num = button_map.get(button.lower(), 1)
    await session.client.mouse_click(x, y, button=button_num, double_click=double_click)
    return {
        "action": "double_click" if double_click else "click",
        "x": x,
        "y": y,
        "button": button,
    }


async def mouse_drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    button: str = "left",
) -> dict[str, str | int]:
    """
    Drag the mouse from one position to another.

    Args:
        start_x: Starting X coordinate.
        start_y: Starting Y coordinate.
        end_x: Ending X coordinate.
        end_y: Ending Y coordinate.
        button: Mouse button to hold.

    Returns:
        Action confirmation with coordinates.
    """
    session = get_session()
    button_map = {"left": 1, "right": 2, "middle": 3}
    button_num = button_map.get(button.lower(), 1)
    await session.client.mouse_drag(start_x, start_y, end_x, end_y, button=button_num)
    return {
        "action": "drag",
        "start_x": start_x,
        "start_y": start_y,
        "end_x": end_x,
        "end_y": end_y,
        "button": button,
    }


async def mouse_wheel(x: int, y: int, delta: int) -> dict[str, str | int]:
    """
    Scroll the mouse wheel at a specific position.

    Args:
        x: X coordinate for the scroll.
        y: Y coordinate for the scroll.
        delta: Scroll amount (positive=up, negative=down).

    Returns:
        Action confirmation.
    """
    session = get_session()
    await session.client.mouse_wheel(x, y, delta)
    return {"action": "wheel", "x": x, "y": y, "delta": delta}


async def type_text(text: str) -> dict[str, str | int]:
    """
    Type text on the remote desktop.

    Args:
        text: Text to type (supports Unicode).

    Returns:
        Action confirmation with text length.
    """
    session = get_session()
    await session.client.send_text(text)
    return {"action": "type", "text": text, "length": len(text)}


# Key name to scancode mapping
KEY_MAP: dict[str, int] = {
    "escape": 0x01,
    "esc": 0x01,
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "7": 0x08,
    "8": 0x09,
    "9": 0x0A,
    "0": 0x0B,
    "minus": 0x0C,
    "equals": 0x0D,
    "backspace": 0x0E,
    "bs": 0x0E,
    "tab": 0x0F,
    "q": 0x10,
    "w": 0x11,
    "e": 0x12,
    "r": 0x13,
    "t": 0x14,
    "y": 0x15,
    "u": 0x16,
    "i": 0x17,
    "o": 0x18,
    "p": 0x19,
    "enter": 0x1C,
    "return": 0x1C,
    "ctrl": 0x1D,
    "lctrl": 0x1D,
    "a": 0x1E,
    "s": 0x1F,
    "d": 0x20,
    "f": 0x21,
    "g": 0x22,
    "h": 0x23,
    "j": 0x24,
    "k": 0x25,
    "l": 0x26,
    "shift": 0x2A,
    "lshift": 0x2A,
    "z": 0x2C,
    "x": 0x2D,
    "c": 0x2E,
    "v": 0x2F,
    "b": 0x30,
    "n": 0x31,
    "m": 0x32,
    "rshift": 0x36,
    "alt": 0x38,
    "lalt": 0x38,
    "space": 0x39,
    "capslock": 0x3A,
    "caps": 0x3A,
    "f1": 0x3B,
    "f2": 0x3C,
    "f3": 0x3D,
    "f4": 0x3E,
    "f5": 0x3F,
    "f6": 0x40,
    "f7": 0x41,
    "f8": 0x42,
    "f9": 0x43,
    "f10": 0x44,
    "numlock": 0x45,
    "scrolllock": 0x46,
    "home": 0x47,
    "up": 0x48,
    "pageup": 0x49,
    "pgup": 0x49,
    "left": 0x4B,
    "right": 0x4D,
    "end": 0x4F,
    "down": 0x50,
    "pagedown": 0x51,
    "pgdn": 0x51,
    "insert": 0x52,
    "ins": 0x52,
    "delete": 0x53,
    "del": 0x53,
    "f11": 0x57,
    "f12": 0x58,
    "win": 0xE05B,
    "lwin": 0xE05B,
    "rwin": 0xE05C,
    "apps": 0xE05D,
    "menu": 0xE05D,
    "rctrl": 0xE01D,
    "ralt": 0xE038,
    "printscreen": 0xE037,
    "prtsc": 0xE037,
    "pause": 0xE11D,
}

MODIFIER_MAP: dict[str, int] = {
    "ctrl": 0x1D,
    "alt": 0x38,
    "shift": 0x2A,
    "win": 0xE05B,
}


async def send_key(
    key: str,
    modifiers: list[str] | None = None,
) -> dict[str, str | list[str] | None]:
    """
    Send a keyboard key press.

    Args:
        key: Key to send. Can be a single character, key name, or hex scancode.
        modifiers: Modifier keys to hold ("ctrl", "alt", "shift", "win").

    Returns:
        Action confirmation.
    """
    session = get_session()
    client = session.client

    key_lower = key.lower()

    if key_lower.startswith("0x"):
        scancode = int(key_lower, 16)
    elif key_lower in KEY_MAP:
        scancode = KEY_MAP[key_lower]
    elif len(key) == 1:
        # Single character - send as unicode with modifiers
        if modifiers:
            for mod in modifiers:
                mod_scancode = MODIFIER_MAP.get(mod.lower())
                if mod_scancode:
                    await client.send_key(mod_scancode, is_press=True, is_release=False)

        await client.send_key(key, is_press=True, is_release=True)

        if modifiers:
            for mod in reversed(modifiers):
                mod_scancode = MODIFIER_MAP.get(mod.lower())
                if mod_scancode:
                    await client.send_key(mod_scancode, is_press=False, is_release=True)

        return {"action": "key", "key": key, "modifiers": modifiers}
    else:
        raise ValueError(f"Unknown key: {key}")

    # Press modifiers
    if modifiers:
        for mod in modifiers:
            mod_scancode = MODIFIER_MAP.get(mod.lower())
            if mod_scancode:
                await client.send_key(mod_scancode, is_press=True, is_release=False)

    # Send the key
    await client.send_key(scancode, is_press=True, is_release=True)

    # Release modifiers
    if modifiers:
        for mod in reversed(modifiers):
            mod_scancode = MODIFIER_MAP.get(mod.lower())
            if mod_scancode:
                await client.send_key(mod_scancode, is_press=False, is_release=True)

    return {"action": "key", "key": key, "modifiers": modifiers}


async def status() -> dict[str, str | int | bool | None]:
    """
    Get the current RDP connection status.

    Returns:
        Connection status and desktop dimensions.
    """
    if _session is None:
        return {
            "connected": False,
            "host": None,
            "width": None,
            "height": None,
            "recording": False,
        }

    return {
        "connected": _session.is_connected,
        "host": _session.client.host,
        "width": _session.client.width if _session.is_connected else None,
        "height": _session.client.height if _session.is_connected else None,
        "recording": _session.is_recording,
    }


async def start_recording() -> dict[str, str | bool]:
    """
    Start recording the session.

    Returns:
        Status confirmation.
    """
    session = get_session()
    await session.start_recording()
    return {"action": "start_recording", "recording": True}


async def stop_recording(save_path: str) -> dict[str, str | bool | None]:
    """
    Stop recording and save to file.

    Args:
        save_path: Path to save the recording.

    Returns:
        Status confirmation with saved path.
    """
    session = get_session()
    saved = await session.stop_recording(save_path)
    return {
        "action": "stop_recording",
        "recording": False,
        "saved_path": saved,
    }


# =============================================================================
# MCP Server Setup
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncGenerator[None, None]:
    """Connect to RDP on startup and disconnect on shutdown."""
    global _session

    # Load config from CLI arguments (with env var fallbacks)
    config = RDPConfig.from_args()

    # Create and connect
    client = RDPClient(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        domain=config.domain,
        width=config.width,
        height=config.height,
    )

    await client.connect()

    _session = RDPSession(client=client, config=config)

    # Start recording if configured
    if config.record_session:
        await _session.start_recording()

    try:
        yield
    finally:
        # Stop recording and save if configured
        if _session and _session.is_recording and config.record_session:
            await _session.stop_recording(config.record_session)

        # Disconnect
        if _session and _session.is_connected:
            await _session.client.disconnect()

        _session = None


# Create the MCP server with lifespan
mcp = FastMCP(
    name="Simple RDP",
    instructions="""
    This MCP server is connected to a Windows desktop via RDP.
    
    The connection was established on startup using environment variables.
    You can interact with the desktop using these tools:
    
    - rdp_screenshot: See the current screen
    - rdp_mouse_move/click/drag/wheel: Mouse operations
    - rdp_type_text: Type text
    - rdp_send_key: Send special keys and key combinations
    - rdp_status: Check connection status
    - rdp_start_recording/stop_recording: Record session to video
    
    Typical workflow:
    1. Take a screenshot to see the current state
    2. Interact using mouse and keyboard
    3. Take screenshots to verify your actions
    """,
    lifespan=lifespan,
)


# =============================================================================
# MCP Tool Wrappers (thin wrappers around core functions)
# =============================================================================


@mcp.tool(annotations={"title": "Take Screenshot", "readOnlyHint": True})
async def rdp_screenshot() -> MCPImage:
    """
    Capture a screenshot of the remote desktop.

    Returns the current screen as an image.
    """
    img = await screenshot()
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return MCPImage(data=buffer.getvalue(), format="png")


@mcp.tool(annotations={"title": "Get Status", "readOnlyHint": True})
async def rdp_status() -> dict[str, str | int | bool | None]:
    """Get the current RDP connection status."""
    return await status()


@mcp.tool(annotations={"title": "Move Mouse", "readOnlyHint": False})
async def rdp_mouse_move(
    x: Annotated[int, Field(description="X coordinate (pixels from left)", ge=0)],
    y: Annotated[int, Field(description="Y coordinate (pixels from top)", ge=0)],
) -> dict[str, str | int]:
    """Move the mouse cursor to a specific position."""
    return await mouse_move(x, y)


@mcp.tool(annotations={"title": "Mouse Click", "readOnlyHint": False})
async def rdp_mouse_click(
    x: Annotated[int, Field(description="X coordinate", ge=0)],
    y: Annotated[int, Field(description="Y coordinate", ge=0)],
    button: Annotated[str, "Mouse button: 'left', 'right', or 'middle'"] = "left",
    double_click: Annotated[bool, "Whether to double-click"] = False,
) -> dict[str, str | int | bool]:
    """Click the mouse at a specific position."""
    return await mouse_click(x, y, button, double_click)


@mcp.tool(annotations={"title": "Mouse Drag", "readOnlyHint": False})
async def rdp_mouse_drag(
    start_x: Annotated[int, Field(description="Starting X coordinate", ge=0)],
    start_y: Annotated[int, Field(description="Starting Y coordinate", ge=0)],
    end_x: Annotated[int, Field(description="Ending X coordinate", ge=0)],
    end_y: Annotated[int, Field(description="Ending Y coordinate", ge=0)],
    button: Annotated[str, "Mouse button to hold"] = "left",
) -> dict[str, str | int]:
    """Drag the mouse from one position to another."""
    return await mouse_drag(start_x, start_y, end_x, end_y, button)


@mcp.tool(annotations={"title": "Mouse Wheel", "readOnlyHint": False})
async def rdp_mouse_wheel(
    x: Annotated[int, Field(description="X coordinate", ge=0)],
    y: Annotated[int, Field(description="Y coordinate", ge=0)],
    delta: Annotated[int, "Scroll amount (positive=up, negative=down)"],
) -> dict[str, str | int]:
    """Scroll the mouse wheel at a specific position."""
    return await mouse_wheel(x, y, delta)


@mcp.tool(annotations={"title": "Type Text", "readOnlyHint": False})
async def rdp_type_text(
    text: Annotated[str, "Text to type (supports Unicode)"],
) -> dict[str, str | int]:
    """Type text on the remote desktop."""
    return await type_text(text)


@mcp.tool(annotations={"title": "Send Key", "readOnlyHint": False})
async def rdp_send_key(
    key: Annotated[
        str,
        """Key to send. Can be:
- A single character (e.g., 'a', 'A', '1')
- A key name: 'enter', 'tab', 'escape', 'backspace', 'delete',
  'up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown',
  'f1'-'f12', 'insert', 'space', 'capslock', 'numlock'
- A hex scancode (e.g., '0x1C' for Enter)""",
    ],
    modifiers: Annotated[list[str] | None, "Modifier keys: 'ctrl', 'alt', 'shift', 'win'"] = None,
) -> dict[str, str | list[str] | None]:
    """
    Send a keyboard key press.

    Examples:
    - Send Enter: rdp_send_key("enter")
    - Copy: rdp_send_key("c", modifiers=["ctrl"])
    - Alt+Tab: rdp_send_key("tab", modifiers=["alt"])
    """
    return await send_key(key, modifiers)


@mcp.tool(annotations={"title": "Start Recording", "readOnlyHint": False})
async def rdp_start_recording() -> dict[str, str | bool]:
    """Start recording the session to video."""
    return await start_recording()


@mcp.tool(annotations={"title": "Stop Recording", "readOnlyHint": False})
async def rdp_stop_recording(
    save_path: Annotated[str, "Path to save the recording (e.g., '/tmp/session.mp4')"],
) -> dict[str, str | bool | None]:
    """Stop recording and save to file."""
    return await stop_recording(save_path)


# =============================================================================
# Entry Points
# =============================================================================


def run_server() -> None:
    """Run the MCP server (entry point for CLI)."""
    global _cli_args
    _cli_args = parse_args()
    mcp.run()


if __name__ == "__main__":
    run_server()
