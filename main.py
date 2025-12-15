import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware  # <--- IMPORTANTE
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

# --- 1. CONFIGURAÇÕES ---
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

# --- 2. SERVIDOR MCP ---
mcp = FastMCP("amigo-scheduler")

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """
    Busca o cadastro de um paciente na base de dados.
    É obrigatório fornecer pelo menos um dos argumentos (nome ou cpf).
    Args:
        nome: Nome completo ou parcial do paciente.
        cpf: CPF do paciente (apenas números ou com pontuação).
    """
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    if not nome and not cpf:
        return "Erro: Forneça Nome ou CPF."
    params = {}
    if nome: params['name'] = nome
    if cpf: params['cpf'] = cpf

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AMIGO_API_URL}/patients", params=params, headers=headers)
            if response.status_code == 401: return "Erro: Token inválido."
            return str(response.json())
        except Exception as e:
            return f"Erro: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    """
    Verifica a disponibilidade de agenda (YYYY-MM-DD).
    Args:
        data: Data no formato ISO 'YYYY-MM-DD'.
    """
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
    """
    Finaliza o agendamento.
    Args:
        start_date: Data/hora 'YYYY-MM-DD HH:MM:SS'.
        patient_id: ID do paciente.
        telefone: Telefone de contato.
    """
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
            return f"Status: {response.status_code}. Resp: {str(response.json())}"
        except Exception as e:
            return f"Erro: {str(e)}"

# --- 3. MIDDLEWARE DE CORREÇÃO ---

class DoubleXRewriterMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            method = scope.get("method", "GET")
            
            # LOG DEBUG PARA O RENDER
            print(f"👀 ROTA: {method} {path}")

            # CORREÇÃO CRÍTICA:
            # 1. Detecta POST errado em /sse ou /tools
            # 2. Redireciona para /messages/ (COM A BARRA NO FINAL para evitar erro 307)
            if method == "POST" and (path == "/sse" or "tools" in path or path == "/messages"):
                print(f"✨ REWRITING: {path} -> /messages/")
                scope["path"] = "/messages/" 
        
        await self.app(scope, receive, send)

# --- 4. APP FINAL ---

mcp_asgi_app = mcp.sse_app()

async def health_check(request):
    return JSONResponse({"status": "online"})

routes = [
    Route("/health", health_check),
    Mount("/", app=mcp_asgi_app)
]

# PILHA DE MIDDLEWARE (A ORDEM IMPORTA MUITO)
middleware = [
    # 1. Permite que o Render acesse (Corrige o "Invalid Host Header")
    Middleware(TrustedHostMiddleware, allowed_hosts=["*"]),
    
    # 2. Permite CORS (Corrige bloqueios de navegador/cross-origin)
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    ),
    
    # 3. Corrige as rotas do Double X
    Middleware(DoubleXRewriterMiddleware)
]

starlette_app = Starlette(routes=routes, middleware=middleware)
