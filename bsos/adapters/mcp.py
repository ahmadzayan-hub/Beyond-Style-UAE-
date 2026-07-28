"""MCP client layer.

External connectors register as tools that pass through the same kernel
guard as native skills. An MCP tool declares a required grant at
registration; the kernel rejects a call when the invoking agent's grant set
does not cover it — no MCP tool may hold a grant the calling agent lacks.

Transport: MCP over stdio (JSON-RPC 2.0), the minimal subset BSOS needs
(initialize, tools/list, tools/call).
"""

from __future__ import annotations

import json
import subprocess
import threading
from typing import Any


class MCPError(Exception):
    pass


class MCPServer:
    def __init__(self, name: str, command: list[str]):
        self.name = name
        self.command = command
        self._proc: subprocess.Popen | None = None
        self._id = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        self._proc = subprocess.Popen(
            self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self._request("initialize", {
            "protocolVersion": "2025-06-18",
            "clientInfo": {"name": "bsos", "version": "0.1.0"},
            "capabilities": {},
        })
        self._notify("notifications/initialized", {})

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._proc or self._proc.stdin is None or self._proc.stdout is None:
            raise MCPError(f"MCP server '{self.name}' not started")
        with self._lock:
            self._id += 1
            msg = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
            self._proc.stdin.write(json.dumps(msg) + "\n")
            self._proc.stdin.flush()
            while True:
                line = self._proc.stdout.readline()
                if not line:
                    raise MCPError(f"MCP server '{self.name}' closed the stream")
                try:
                    resp = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if resp.get("id") == self._id:
                    if "error" in resp:
                        raise MCPError(str(resp["error"]))
                    return resp.get("result", {})

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        if self._proc and self._proc.stdin:
            self._proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n")
            self._proc.stdin.flush()

    def list_tools(self) -> list[dict[str, Any]]:
        return self._request("tools/list", {}).get("tools", [])

    def call_tool(self, tool: str, arguments: dict[str, Any]) -> Any:
        return self._request("tools/call", {"name": tool, "arguments": arguments})

    def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            self._proc = None


class MCPRegistry:
    """Registers MCP tools into the kernel skill registry behind the guard."""

    def __init__(self) -> None:
        self.servers: dict[str, MCPServer] = {}

    def attach(self, server: MCPServer, skill_registry, required_grant_prefix: str = "mcp") -> list[str]:
        """Register every tool the server offers as `mcp.<server>.<tool>`.

        Each registered tool requires grant `mcp.<server>.<tool>` — an agent
        must be granted it explicitly; nothing inherits it.
        """
        server.start()
        self.servers[server.name] = server
        registered = []
        for tool in server.list_tools():
            tool_name = f"{required_grant_prefix}.{server.name}.{tool['name']}"

            def make_handler(srv: MCPServer, name: str):
                def handler(ctx, **kwargs):
                    return srv.call_tool(name, kwargs)
                handler.__doc__ = f"MCP tool {name} on server {srv.name}"
                return handler

            skill_registry.register(
                tool_name, required_grant=tool_name,
                tags=("mcp", "outbound_http"), side_effects="network",
                description=tool.get("description", ""),
            )(make_handler(server, tool["name"]))
            registered.append(tool_name)
        return registered
