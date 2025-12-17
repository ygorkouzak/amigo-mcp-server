import os
import json
import asyncio
from starlette.applications import Starlette
from starlette.responses import StreamingResponse, JSONResponse
from starlette.routing import Route
from mcp.server.fastmcp import FastMCP

# ======================
# MCP CONFIG
# ======================

mcp = FastMCP(name="amigo-scheduler")

@mcp.tool()
def ping() -> str:
    return "pong"

@mcp.tool()
def schedule_task(task: str) -> str:
    return f"Tarefa '{task}' agendada com sucesso"

# ======================
# SSE HANDLER
# ======================

async def sse_endpoint(request):
    async def event_generator():
        # evento inicial (handshake)
        yield "event: ready\ndata: MCP conectado\n\n"

        # loop simples (pode evoluir depois)
        while True:
            await asyncio.sleep(15)
            yield "event: heartbeat\ndata: alive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # IMPORTANTE p/ proxy
        },
    )

# ======================
# MCP TOOL INVOCATION
# ======================

async def call_tool(request):
    payload = await request.json()

    result = await mcp.run(
        payload["tool"],
        payload.get("arguments", {})
    )

    return JSONResponse(result)

# ======================
# STARLETTE APP
# ======================

routes = [
    Route("/sse", sse_endpoint, methods=["GET"]),
    Route("/call", call_tool, methods=["POST"]),
]

starlette_app = Starlette(routes=routes)
