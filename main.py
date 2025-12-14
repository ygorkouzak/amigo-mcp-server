import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# --- CONFIGURAÇÕES E IDs ---
# Usamos os valores das suas imagens como padrão (fallback)
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
    """Realiza o agendamento de uma consulta."""
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
            return f"Agendamento realizado: {str(response.json())}"
        except Exception as e:
            return f"Erro: {str(e)}"

# --- MONTAGEM DO SERVIDOR COM CORS ---

# 1. Pegamos o app MCP (com os parenteses corretos!)
mcp_asgi_app = mcp.sse_app()

# 2. Configuração de CORS (Permite que a Double X acesse seu servidor sem bloqueio)
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Libera geral para a Double X conseguir ler
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

# 3. Handler para redirecionar POSTs perdidos no /sse para /messages
async def handle_compatibility_post(request: Request):
    scope = request.scope
    scope["path"] = "/messages"  # Redireciona para o endpoint correto
    await mcp_asgi_app(scope, request.receive, request.send)

# 4. Rota de Health Check
async def health_check(request):
    return JSONResponse({"status": "online", "mcp_mode": "active"})

# 5. Definição das Rotas
routes = [
    Route("/health", health_check),
    Route("/", health_check),
    # Captura o POST no /sse (que a Double X faz errado) e corrige
    Route("/sse", handle_compatibility_post, methods=["POST"]),
    # Monta o servidor oficial do MCP na raiz (para lidar com o GET /sse e o POST /messages)
    Mount("/", app=mcp_asgi_app)
]

# 6. Criação do App Final
starlette_app = Starlette(routes=routes, middleware=middleware)
