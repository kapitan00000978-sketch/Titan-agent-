import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


class MCPServerConnection:
    def __init__(self, name: str, command: str, args: list[str], env: dict[str, str] | None = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.process: asyncio.subprocess.Process | None = None
        self.tools: list[dict[str, Any]] = []
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._read_task: asyncio.Task | None = None
        self.is_connected = False

    async def start(self) -> bool:
        try:
            full_env = os.environ.copy()
            full_env.update(self.env)
            # Ensure windows shell support if npx/npm/cmd
            cmd = self.command
            args = self.args
            
            # Windows executable resolution
            if sys.platform == "win32" and cmd in ("npx", "npm"):
                cmd = f"{cmd}.cmd"

            self.process = await asyncio.create_subprocess_exec(
                cmd,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env
            )
            self._read_task = asyncio.create_task(self._listen_stdout())
            self.is_connected = True

            # Send initialize handshake
            _ = await self.send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "TitanAgent",
                    "version": "1.0.0"
                }
            })

            # Send initialized notification
            await self.send_notification("notifications/initialized", {})

            # Fetch available tools
            tools_res = await self.send_request("tools/list", {})
            self.tools = tools_res.get("tools", [])
            return True
        except Exception as e:
            print(f"[MCP] Failed to start server '{self.name}': {e}")
            self.is_connected = False
            await self.stop()
            return False

    async def _listen_stdout(self):
        try:
            while self.process and self.process.stdout:
                try:
                    line = await self.process.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode('utf-8', errors='ignore').strip()
                    if not decoded:
                        continue
                    try:
                        data = json.loads(decoded)
                        req_id = data.get("id")
                        if req_id is not None and req_id in self._pending_requests:
                            future = self._pending_requests.pop(req_id)
                            if not future.done():
                                if "error" in data:
                                    future.set_exception(RuntimeError(data["error"]))
                                else:
                                    future.set_result(data.get("result", {}))
                    except json.JSONDecodeError:
                        pass
                except Exception:
                    break
        finally:
            self.is_connected = False

    async def send_request(self, method: str, params: dict[str, Any], timeout: float = 30.0) -> Any:
        if not self.process or not self.process.stdin:
            raise RuntimeError(f"MCP server '{self.name}' is not running.")
        self._request_id += 1
        req_id = self._request_id
        req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[req_id] = future

        msg = json.dumps(req) + "\n"
        self.process.stdin.write(msg.encode('utf-8'))
        await self.process.stdin.drain()

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"MCP request '{method}' to server '{self.name}' timed out after {timeout}s"
            ) from None

    async def send_notification(self, method: str, params: dict[str, Any]):
        if not self.process or not self.process.stdin:
            return
        notif = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        msg = json.dumps(notif) + "\n"
        self.process.stdin.write(msg.encode('utf-8'))
        await self.process.stdin.drain()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        res = await self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        # Extract content
        contents = res.get("content", [])
        text_outputs = []
        for c in contents:
            if isinstance(c, dict) and c.get("type") == "text":
                text_outputs.append(c.get("text", ""))
        return "\n".join(text_outputs) if text_outputs else json.dumps(res)

    async def stop(self):
        if self._read_task:
            self._read_task.cancel()
            try:
                await asyncio.wait_for(self._read_task, timeout=3.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception:
                pass
            self._read_task = None

        proc = self.process
        self.process = None
        if proc:
            try:
                if proc.returncode is None:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        proc.kill()
            except Exception:
                pass
            # Close pipes to avoid "unclosed transport" ResourceWarnings on Windows
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if pipe is not None:
                        pipe.close()
                except Exception:
                    pass
        self.is_connected = False

class MCPManager:
    def __init__(self, config_file: Path | None = None):
        self.config_file = config_file
        self.servers: dict[str, MCPServerConnection] = {}

    def load_config(self) -> dict[str, Any]:
        if not self.config_file or not self.config_file.exists():
            return {"mcpServers": {}}
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"mcpServers": {}}

    async def start_all(self):
        from .config import WORKSPACE_DIR
        cfg = self.load_config()
        servers = cfg.get("mcpServers", {})
        for name, details in servers.items():
            cmd = details.get("command", "")
            args = details.get("args", [])
            env = details.get("env", {})
            # Placeholder substitution (portable config)
            args = [str(a).replace("{WORKSPACE}", str(WORKSPACE_DIR)).replace("{BASE_DIR}", str(WORKSPACE_DIR.parent)) for a in args]
            cmd = str(cmd).replace("{WORKSPACE}", str(WORKSPACE_DIR)).replace("{BASE_DIR}", str(WORKSPACE_DIR.parent))
            if cmd:
                conn = MCPServerConnection(name, cmd, args, env)
                ok = await conn.start()
                if ok:
                    self.servers[name] = conn
                    print(f"[MCP] Connected to '{name}' ({len(conn.tools)} tools available)")

    def get_all_tools(self) -> list[dict[str, Any]]:
        """Returns tools formatted for OpenAI LLM function calling"""
        formatted = []
        for s_name, conn in self.servers.items():
            if not conn.is_connected:
                continue
            for tool in conn.tools:
                orig_name = tool.get("name", "")
                full_name = f"mcp_{s_name}_{orig_name}"
                formatted.append({
                    "type": "function",
                    "function": {
                        "name": full_name,
                        "description": f"[MCP: {s_name}] {tool.get('description', '')}",
                        "parameters": tool.get("inputSchema", {
                            "type": "object",
                            "properties": {},
                            "required": []
                        })
                    }
                })
        return formatted

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if not name.startswith("mcp_"):
            return f"Error: '{name}' is not an MCP tool."
        parts = name.split("_", 2)
        if len(parts) < 3:
            return f"Error: Invalid MCP tool name format '{name}'."
        s_name = parts[1]
        orig_name = parts[2]
        if s_name not in self.servers or not self.servers[s_name].is_connected:
            return f"Error: MCP Server '{s_name}' is not connected."
        try:
            return await self.servers[s_name].call_tool(orig_name, arguments)
        except Exception as e:
            return f"Error executing MCP tool '{orig_name}' on '{s_name}': {e!s}"

    async def stop_all(self):
        for conn in self.servers.values():
            await conn.stop()
        self.servers.clear()
