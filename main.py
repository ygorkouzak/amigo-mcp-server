from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route
import uvicorn

mcp = FastMCP("amigo-scheduler")

@mcp.tool()
async def buscar_paciente(nome: str) -> str:
    return f"Resultado para {nome}"

# 🔑 MCP exposto exatamente em /sse (sem redirect)
app = Starlette(
    routes=[
        Route("/sse", endpoint=mcp.sse_app())
    ]
)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
