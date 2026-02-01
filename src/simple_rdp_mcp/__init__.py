"""
Simple RDP MCP Server.

Exposes RDP client capabilities as MCP tools for LLM agents.
"""

from simple_rdp_mcp.server import mcp

__all__ = ["mcp"]
