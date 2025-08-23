from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Dict, Optional
import logging


class NotUsingMCPError(RuntimeError):
    pass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _server_command() -> str:
    return os.getenv("MCP_SERVER_CMD", "python -m app.mcp.server")


async def _spawn_process(cmd: str) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_shell(
        cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


async def _rpc_call(proc: asyncio.subprocess.Process, method: str, params: Dict[str, Any]) -> Any:
    start = time.time()
    req = {"jsonrpc": "2.0", "id": int(time.time() * 1000) % 1_000_000, "method": method, "params": params}
    line = json.dumps(req) + "\n"
    assert proc.stdin and proc.stdout
    proc.stdin.write(line.encode("utf-8"))
    await proc.stdin.drain()
    raw = await proc.stdout.readline()
    if not raw:
        stderr = await proc.stderr.read() if proc.stderr else b""
        raise RuntimeError(f"MCP server closed pipe. stderr={stderr.decode(errors='ignore')}")
    resp = json.loads(raw.decode("utf-8"))
    if "error" in resp:
        raise RuntimeError(str(resp["error"]))
    return resp.get("result")


class MCPClient:
    def __init__(self) -> None:
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._logger = logging.getLogger(__name__)
        self._initialized: bool = False

    async def _ensure(self) -> None:
        if self._proc is not None and self._initialized:
            return
        cmd = _server_command()
        self._proc = await _spawn_process(cmd)
        # Minimal MCP handshake
        init_params = {
            "clientInfo": {"name": "whatsapp-bot", "version": "0.1"},
            "capabilities": {},
        }
        await _rpc_call(self._proc, "initialize", init_params)
        self._initialized = True

    async def invoke_tool(self, name: str, params: Dict[str, Any]) -> Any:
        if not _env_bool("USE_MCP", False):
            raise NotUsingMCPError("USE_MCP is false")
        await self._ensure()
        # Structured log (redact values, show keys and simple scalars)
        args_summary = {
            k: (v if isinstance(v, (int, float, bool)) else (str(v)[:64] if isinstance(v, str) else type(v).__name__))
            for k, v in params.items()
        }
        self._logger.info("tool_call_start", extra={"tool_name": name, "tool_args": args_summary})
        try:
            t0 = time.time()
            result = await _rpc_call(self._proc, "tools/call", {"name": name, "arguments": params})
            duration_ms = int((time.time() - t0) * 1000)
            res_summary = (
                result if isinstance(result, (int, float, bool)) else (str(result)[:120] if isinstance(result, str) else type(result).__name__)
            )
            self._logger.info("tool_call_end", extra={"tool_name": name, "duration_ms": duration_ms, "result": res_summary})
            return result
        except Exception as e:
            self._logger.error("tool_call_error", extra={"tool_name": name, "error": str(e)[:200]})
            raise


_shared_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = MCPClient()
    return _shared_client