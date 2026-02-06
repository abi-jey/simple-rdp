"""Simple RDP MCP Server.

Exposes RDP client capabilities as MCP tools for LLM agents.

This module provides both:
1. An MCP server (`mcp`) for use with MCP-compatible LLM clients
2. Core async functions for direct use in Python code

MCP Server Usage:
    # Run via CLI
    simple-rdp-mcp

    # Or programmatically
    from simple_rdp_mcp import mcp
    mcp.run()

Direct Function Usage:
    import asyncio
    from simple_rdp_mcp import connect, screenshot, mouse_click, disconnect

    async def main():
        await connect("192.168.1.100", "user", "pass")
        img = await screenshot()
        await mouse_click(100, 200)
        await disconnect()

    asyncio.run(main())
"""

from simple_rdp_mcp.server import connect
from simple_rdp_mcp.server import disconnect
from simple_rdp_mcp.server import mcp
from simple_rdp_mcp.server import mouse_click
from simple_rdp_mcp.server import mouse_drag
from simple_rdp_mcp.server import mouse_move
from simple_rdp_mcp.server import mouse_wheel
from simple_rdp_mcp.server import run_server
from simple_rdp_mcp.server import screenshot
from simple_rdp_mcp.server import send_key
from simple_rdp_mcp.server import start_recording
from simple_rdp_mcp.server import status
from simple_rdp_mcp.server import stop_recording
from simple_rdp_mcp.server import type_text

__all__ = [
    "mcp",
    "run_server",
    # Connection management
    "connect",
    "disconnect",
    # Core functions
    "screenshot",
    "mouse_move",
    "mouse_click",
    "mouse_drag",
    "mouse_wheel",
    "type_text",
    "send_key",
    "status",
    "start_recording",
    "stop_recording",
]
