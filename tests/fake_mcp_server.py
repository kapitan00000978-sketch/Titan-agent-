"""A minimal fake MCP server (JSON-RPC 2.0 over stdio) used by the tests.

It speaks just enough of the Model Context Protocol to be driven by
titan_agent.mcp_client.MCPServerConnection:
  - initialize          → protocolVersion + capabilities + serverInfo
  - notifications/*     → ignored (no reply expected)
  - tools/list          → a small fixed tool catalog
  - tools/call          → echo / read_stuff / add results, tagged with the
                          server's own name so tests can prove correct routing

Passed the server name as argv[1]; it is embedded in every tool result.

Each request is handled in its own asyncio task, and some tools sleep a little,
so the client can prove that calls actually run in PARALLEL (both across
servers and within a single server).

Windows note: asyncio pipe transports (connect_read_pipe / connect_write_pipe)
are unreliable under the Proactor loop, so stdio is read/written from a plain
worker thread instead — this is also how the real reference servers behave.
"""
import asyncio
import json
import sys
import threading

SERVER_NAME = sys.argv[1] if len(sys.argv) > 1 else "fake"

# Deliberate per-call delays (seconds) so parallelism is measurable.
ECHO_DELAY = 0.15
ADD_DELAY = 0.25
READ_DELAY = 0.05

_write_lock = threading.Lock()


def _tools():
    return [
        {
            "name": "echo",
            "description": "Echoes text back to the caller.",
            "inputSchema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
        {
            "name": "read_stuff",
            "description": "Returns a fake directory listing.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "add",
            "description": "Adds two integers together.",
            "inputSchema": {
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        },
    ]


def _text(content_text: str) -> dict:
    return {"content": [{"type": "text", "text": content_text}]}


async def handle_request(msg: dict) -> dict | None:
    method = msg.get("method")
    params = msg.get("params") or {}
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": "1.0.0"},
        }
    if method == "tools/list":
        return {"tools": _tools()}
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        if name == "echo":
            await asyncio.sleep(ECHO_DELAY)
            return _text(f"{SERVER_NAME}:echo:{args.get('text', '')}")
        if name == "read_stuff":
            await asyncio.sleep(READ_DELAY)
            return _text(f"{SERVER_NAME}:read_stuff:file1.txt\nfile2.txt")
        if name == "add":
            await asyncio.sleep(ADD_DELAY)
            a = int(args.get("a", 0))
            b = int(args.get("b", 0))
            return _text(f"{SERVER_NAME}:add:{a + b}")
        return _text(f"{SERVER_NAME}:unknown:{name}")
    return None


def _write_blocking(data: bytes):
    with _write_lock:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


async def main():
    loop = asyncio.get_running_loop()
    tasks = []
    shutdown = asyncio.Event()

    def _schedule(msg: dict):
        tasks.append(asyncio.create_task(_respond(msg)))

    async def _respond(msg: dict):
        msg_id = msg.get("id")
        if msg_id is None:
            return  # notification — no reply
        result = await handle_request(msg)
        if result is None:
            return
        reply = {"jsonrpc": "2.0", "id": msg_id, "result": result}
        data = (json.dumps(reply) + "\n").encode("utf-8")
        await loop.run_in_executor(None, _write_blocking, data)

    def _reader():
        try:
            while True:
                line = sys.stdin.buffer.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                loop.call_soon_threadsafe(_schedule, msg)
        finally:
            loop.call_soon_threadsafe(shutdown.set)

    threading.Thread(target=_reader, daemon=True).start()
    await shutdown.wait()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass