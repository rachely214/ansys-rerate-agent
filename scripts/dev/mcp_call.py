"""Developer harness: call V2 MCP tools over real stdio (same transport as Hermes), one call per invocation.

  python scripts/dev/mcp_call.py <server> <tool> '<json args>'

The server process is kept alive between calls in a background broker so app sessions (Fluent, Mechanical,
Discovery) persist: `python scripts/dev/mcp_call.py --broker` starts it (writes work/broker.port next to machine.config.yaml).
Run it with the install-home venv Python; it uses the same machine.config.yaml as the agent.
This is a test aid for validation runs without an LLM; it is not used by the agent.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "plugins" / "ansys-mcp" / "src"))  # falls back to the repo copy if the runtime is not installed
from rerate_mcp_v2 import config  # noqa: E402

PORT_FILE = config.config_dir() / "work" / "broker.port"  # install home (or the folder of RERATE_CONFIG)
SERVERS = ["case_v2", "vista_v2", "geometry_v2", "turbogrid_v2", "fluent_v2", "mechanical_v2"]


async def broker():
    from fastmcp import Client
    from fastmcp.client.transports import PythonStdioTransport
    env = dict(os.environ, RERATE_CONFIG=str(config.config_path()))
    clients = {}

    async def get(name):
        if name not in clients:
            mod = f"rerate_mcp_v2.servers.{name.replace('_v2', '')}_server"
            t = PythonStdioTransport(script_path=str(ROOT / "scripts" / "setup" / "_run_module.py"), args=[mod],
                                     python_cmd=sys.executable, env=env, keep_alive=True)
            c = Client(t, timeout=120)  # no V2 tool may block longer; a hit here is a bug to report
            await c.__aenter__()
            clients[name] = c
        return clients[name]

    async def handle(reader, writer):
        req = json.loads((await reader.readline()).decode())
        try:
            c = await get(req["server"])
            r = await c.call_tool(req["tool"], req.get("args") or {}, raise_on_error=False)
            txt = "".join(getattr(b, "text", "") for b in r.content)
            out = {"ok": True, "result": txt}
        except Exception as e:
            out = {"ok": False, "error": repr(e)}
        writer.write((json.dumps(out) + "\n").encode())
        await writer.drain()
        writer.close()

    srv = await asyncio.start_server(handle, "127.0.0.1", 0, limit=2 ** 24)
    PORT_FILE.write_text(str(srv.sockets[0].getsockname()[1]))
    print("broker on", PORT_FILE.read_text(), flush=True)
    async with srv:
        await srv.serve_forever()


def call(server, tool, args):
    port = int(PORT_FILE.read_text())
    with socket.create_connection(("127.0.0.1", port)) as s:
        s.sendall((json.dumps({"server": server, "tool": tool, "args": args}) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf.decode())


if __name__ == "__main__":
    if sys.argv[1] == "--broker":
        asyncio.run(broker())
    else:
        r = call(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {})
        print(r["result"] if r.get("ok") else r)
