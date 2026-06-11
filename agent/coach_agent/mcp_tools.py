"""MongoDB MCP support for the Scout.AI Coach Agent (read-only by default).

Builds a Google ADK McpToolset that launches the official MongoDB MCP server
via npx. Degrades gracefully: if Node/npx, the mcp package, or the ADK MCP
imports are unavailable, returns None with a warning instead of crashing.
Writes stay in explicit PyMongo tools (tools.py / memory.py).
"""
import os
import shutil
import sys


def get_mongodb_mcp_toolset():
    """Return an ADK McpToolset for MongoDB (read-only), or None if unavailable."""
    if os.getenv("ENABLE_MONGODB_MCP", "false").lower() not in ("1", "true", "yes"):
        print("[mcp] ENABLE_MONGODB_MCP disabled; skipping MongoDB MCP.", file=sys.stderr)
        return None
    uri = os.getenv("MONGODB_URI", "")
    if not uri or "<db_password>" in uri:
        print("[mcp] MONGODB_URI missing/placeholder; skipping MongoDB MCP.", file=sys.stderr)
        return None
    if not (shutil.which("npx") or shutil.which("npx.cmd")):
        print("[mcp] npx (Node.js) not found; skipping MongoDB MCP. "
              "PyMongo tools remain available.", file=sys.stderr)
        return None
    try:
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
        try:  # ADK >= 1.x
            from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
            from mcp import StdioServerParameters
            conn = StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "mongodb-mcp-server@latest", "--readOnly"],
                    env={"MDB_MCP_CONNECTION_STRING": uri},
                )
            )
            return McpToolset(connection_params=conn)
        except ImportError:  # older ADK API
            from google.adk.tools.mcp_tool.mcp_toolset import StdioServerParameters as SSP
            return McpToolset(
                connection_params=SSP(
                    command="npx",
                    args=["-y", "mongodb-mcp-server@latest", "--readOnly"],
                    env={"MDB_MCP_CONNECTION_STRING": uri},
                )
            )
    except Exception as e:  # noqa: BLE001 - never let MCP break the agent
        print(f"[mcp] Could not build MongoDB MCP toolset ({e}). "
              "Falling back to PyMongo tools only.", file=sys.stderr)
        return None
