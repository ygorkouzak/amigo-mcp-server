import os
import httpx
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SSEServerTransport

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

# =====================
# ENV
# =====================
load_dotenv()

AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

CONFIG = {
    "PLACE_ID": int(os.getenv("PLACE_ID", 6955)),
    "EVENT_ID": int(os.getenv("EVENT_ID", 526436)),
    "ACCOUNT_ID": int(os.getenv("ACCOUNT_ID", 74698)),
    "USER_ID": int(os.getenv("USER_ID", 28904)),
    "INSURANCE_ID": int(os.getenv("INSURANCE_ID", 1)),
}

# =====================
# MCP SERVER
# =====================
mcp = FastMCP("amigo-scheduler")

# =====================
# TOOLS
# =====================
@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN não configurado."

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {}

    if nome:
        params["name"] = nome
    if cpf:
        params["cpf"] = cpf

    if not params:
        return "Informe nome ou CPF."

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{AMIGO_API_URL}/patients",
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.text


@mcp.tool()
async def consultar_horarios(data: str) -> str:
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN não configurado."

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {
        "date": data,
        "event_id": CONFIG["EVENT_ID"],
        "place_id": CONFIG["PLACE_ID"],
        "insurance_id": CONFIG["INSURANCE_ID"],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{AMIGO_API_URL}/calendar",
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.text


@mcp.tool()
async def agendar_consulta(
    start_date: str,
    patient_id: int,
    telefone: str,
) -> str:
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN não configurado."

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {
        "insurance_id": CONFIG["INSURANCE_ID"],
        "event_id": CONFIG["EVENT_ID"],
        "place_id": CONFIG["PLACE_ID"],
        "start_date": start_date,
        "patient_id": patient_id,
        "account_id": CONFIG["ACCOUNT_ID"],
        "user_id": CONFIG["USER_ID"],
        "chat_id": "doublex",
        "scheduler_phone": telefone,
        "is_dependent_schedule": False,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{AMIGO_API_URL}/attendances",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.text


# =====================
# SSE TRANSPORT
# =====================
transport = SSEServerTransport("/sse")

# =====================
# HEALTH CHECK
# =====================
async def health(request):
    return JSONResponse({
        "status": "online",
        "server": "amigo-mcp-server",
        "mode": "MCP Protocol (SSE)",
        "tools": [
            "buscar_paciente",
            "consultar_horarios",
            "agendar_consulta",
        ],
        "connect": "/sse",
    })

# =====================
# STARLETTE APP
# =====================
app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/sse", transport.handle, methods=["GET"]),
    ]
)

# =====================
# MOUNT MCP
# =====================
transport.mount(mcp)
