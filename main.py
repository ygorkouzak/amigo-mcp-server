import os
import httpx
import logging
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse

# --- LOGGING (Para vermos o que está acontecendo) ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

# --- CONFIGURAÇÕES ---
def get_config(key, default):
    val = os.getenv(key)
    if val and val.strip():
        return val
    return default

AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

CONFIG = {
    "PLACE_ID": int(get_config("PLACE_ID", 6955)),
    "EVENT_ID": int(get_config("EVENT_ID", 526436)),
    "ACCOUNT_ID": int(get_config("ACCOUNT_ID", 74698)),
    "USER_ID": int(get_config("USER_ID", 28904)),
    "INSURANCE_ID": int(get_config("INSURANCE_ID", 1))
}

# --- LISTA MANUAL DE FERRAMENTAS (O "Cardápio") ---
# Isso serve para entregar ao Double X via GET se ele não fizer o handshake JSON-RPC
TOOLS_SCHEMA = [
    {
        "name": "buscar_paciente",
        "description": "Busca um paciente pelo nome ou CPF para encontrar seu ID interno.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome do paciente"},
                "cpf": {"type": "string", "description": "CPF do paciente"}
            }
        }
    },
    {
        "name": "consultar_horarios",
        "description": "Consulta horários disponíveis na agenda.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Data no formato YYYY-MM-DD"}
            },
            "required": ["data"]
        }
    },
    {
        "name": "agendar_consulta",
        "description": "Realiza o agendamento final de uma consulta.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Data e hora exata (YYYY-MM-DD HH:mm)"},
                "patient_id": {"type": "integer", "description": "ID do paciente"},
                "telefone": {"type": "string", "description": "Telefone de contato"}
            },
            "required": ["start_date", "patient_id", "telefone"]
        }
    }
]

# --- SERVIDOR MCP ---
mcp = FastMCP("amigo-scheduler")

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """Busca um paciente pelo nome ou CPF."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {"name": nome, "cpf": cpf}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AMIGO_API_URL}/patients", params=params, headers=headers)
            if response.status_code == 401: return "Erro: Token inválido."
            return str(response.json())
        except Exception as e:
            return f"Erro: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    """Consulta horários disponíveis (YYYY-MM-DD)."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {
        "date": data,
        "event_id": CONFIG["EVENT_ID"],
        "place_id": CONFIG["PLACE_ID"],
        "insurance_id": CONFIG["INSURANCE_ID"]
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AMIGO_API_URL}/calendar", params=params, headers=headers)
            return str(response.json())
        except Exception as e:
            return f"Erro: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    """Realiza o agendamento."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    body = {
        "insurance_id": CONFIG["INSURANCE_ID"],
        "event_id": CONFIG["EVENT_ID"],
        "place_id": CONFIG["PLACE_ID"],
        "start_date": start_date,
        "patient_id": patient_id,
        "account_id": CONFIG["ACCOUNT_ID"],
        "user_id": CONFIG["USER_ID"],
        "chat_id": "whatsapp_integration",
        "scheduler_phone": telefone,
        "is_dependent_schedule": False
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{AMIGO_API_URL}/attendances", json=body, headers=headers)
            return f"Sucesso: {str(response.json())}"
        except Exception as e:
            return f"Erro: {str(e)}"

# --- ROTEAMENTO INTELIGENTE ---

mcp_asgi_app = mcp.sse_app()

async def handle_post_compatibility(request: Request):
    """Redireciona POSTs perdidos para /messages"""
    scope = request.scope
    scope["path"] = "/messages"
    await mcp_asgi_app(scope, request.receive, request.send)

async def handle_get_tools(request: Request):
    """Entrega o cardápio (lista de ferramentas) via GET"""
    return JSONResponse({
        "tools": TOOLS_SCHEMA,
        "_meta": "Manually exposed for compatibility"
    })

# Lista de rotas para interceptar
routes = []

# 1. Rotas de POST (Compatibilidade JSON-RPC)
post_paths = ["/sse", "/tools/list", "/api/tools/list"]
for path in post_paths:
    routes.append(Route(path, handle_post_compatibility, methods=["POST"]))

# 2. Rotas de GET (Descoberta REST)
get_paths = ["/tools", "/api/tools", "/tools/list"]
for path in get_paths:
    routes.append(Route(path, handle_get_tools, methods=["GET"]))

# 3. Health Check
async def health_check(request):
    return JSONResponse({"status": "online", "tools": len(TOOLS_SCHEMA)})
routes.append(Route("/health", health_check))
routes.append(Route("/", health_check))

# 4. Mount final para o app oficial
routes.append(Mount("/", app=mcp_asgi_app))

starlette_app = Starlette(routes=routes)
