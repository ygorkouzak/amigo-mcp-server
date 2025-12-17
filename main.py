import os
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware.cors import CORSMiddleware

load_dotenv()

# =====================
# CONFIG
# =====================
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
mcp = FastMCP(
    name="amigo-scheduler",
    trusted_origins=["*"],     # ESSENCIAL p/ Render + SSE
)

# =====================
# TOOLS
# =====================
@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN ausente."

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {}

    if nome:
        params["name"] = nome
    if cpf:
        params["cpf"] = cpf

    if not params:
        return "Erro: informe nome ou CPF."

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{AMIGO_API_URL}/patients", params=params, headers=headers)
        r.raise_for_status()
        return r.text


@mcp.tool()
async def consultar_horarios(data: str) -> str:
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN ausente."

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {
        "date": data,
        "event_id": CONFIG["EVENT_ID"],
        "place_id": CONFIG["PLACE_ID"],
        "insurance_id": CONFIG["INSURANCE_ID"],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{AMIGO_API_URL}/calendar", params=params, headers=headers)
        r.raise_for_status()
        return r.text


@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN ausente."

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
        r = await client.post(
            f"{AMIGO_API_URL}/attendances",
            json=payload,
            headers=headers,
        )
        r.raise_for_status()
        return r.text


# =====================
# HEALTH CHECK
# =====================
async def health(request):
    return JSONResponse(
        {
            "status": "online",
            "server": "amigo-mcp-server",
            "mode": "MCP Protocol (SSE)",
            "tools": [
                "buscar_paciente",
                "consultar_horarios",
                "agendar_consulta",
            ],
            "connect": "/sse",
        }
    )

# =====================
# APP EXPORT
# =====================
app = mcp.sse_app()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.routes.insert(0, Route("/health", health, methods=["GET"]))

starlette_app = app
