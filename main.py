import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

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

# --- SERVIDOR MCP (Ferramentas) ---
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

# --- MIDDLEWARE (O Porteiro Mágico) ---

class DoubleXRewriterMiddleware:
    """
    Intercepta as chamadas 'erradas' do Double X e as corrige antes
    que o servidor perceba o erro.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            method = scope.get("method", "GET")
            
            # SE DETECTAR O ERRO DO DOUBLE X:
            # (Tentativa de POST em /sse ou qualquer rota de tools)
            if method == "POST" and (path == "/sse" or "tools" in path):
                print(f"DEBUG: Corrigindo rota {path} -> /messages para o Double X")
                scope["path"] = "/messages" # A mágica acontece aqui!
        
        await self.app(scope, receive, send)

# --- MONTAGEM DO APP FINAL ---

# 1. Pegamos o app MCP
mcp_asgi_app = mcp.sse_app()

# 2. Rota de Health Check
async def health_check(request):
    return JSONResponse({"status": "online", "mcp_mode": "active"})

routes = [
    Route("/health", health_check),
    # Montamos o MCP na raiz. O Middleware acima vai garantir que os pedidos cheguem certos.
    Mount("/", app=mcp_asgi_app)
]

# 3. Definição da Pilha de Middlewares (A ordem importa!)
# O CORS vem primeiro (libera a entrada), depois o Rewriter (corrige o endereço)
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    ),
    Middleware(DoubleXRewriterMiddleware)
]

# 4. App Final
starlette_app = Starlette(routes=routes, middleware=middleware)
