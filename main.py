import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

# --- 1. CONFIGURAÇÕES ---
AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

CONFIG = {
    "PLACE_ID": int(os.getenv("PLACE_ID", 6955)),
    "EVENT_ID": int(os.getenv("EVENT_ID", 526436)),
    "ACCOUNT_ID": int(os.getenv("ACCOUNT_ID", 74698)),
    "USER_ID": int(os.getenv("USER_ID", 28904)),
    "INSURANCE_ID": int(os.getenv("INSURANCE_ID", 1))
}

# --- 2. SERVIDOR MCP ---
mcp = FastMCP("amigo-scheduler")

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """Busca paciente. Nome ou CPF obrigatórios."""
    if not API_TOKEN: return "Erro: Token não configurado no .env"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    if not nome and not cpf: return "Erro: Forneça Nome ou CPF."
    params = {}
    if nome: params['name'] = nome
    if cpf: params['cpf'] = cpf
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AMIGO_API_URL}/patients", params=params, headers=headers)
            return str(response.json())
        except Exception as e: return f"Erro: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    """Verifica disponibilidade (YYYY-MM-DD)."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {"date": data, "event_id": CONFIG["EVENT_ID"], "place_id": CONFIG["PLACE_ID"], "insurance_id": CONFIG["INSURANCE_ID"]}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AMIGO_API_URL}/calendar", params=params, headers=headers)
            return str(response.json())
        except Exception as e: return f"Erro: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    """Agendar consulta (start_date: YYYY-MM-DD HH:MM:SS)."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    body = {
        "insurance_id": CONFIG["INSURANCE_ID"], "event_id": CONFIG["EVENT_ID"], "place_id": CONFIG["PLACE_ID"],
        "start_date": start_date, "patient_id": patient_id, "account_id": CONFIG["ACCOUNT_ID"],
        "user_id": CONFIG["USER_ID"], "chat_id": "whatsapp_integration", "scheduler_phone": telefone, "is_dependent_schedule": False
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{AMIGO_API_URL}/attendances", json=body, headers=headers)
            return f"Status: {response.status_code}. Resp: {str(response.json())}"
        except Exception as e: return f"Erro: {str(e)}"

# --- 3. MIDDLEWARE CORRETOR ---
class DoubleXFixMiddleware:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            method = scope.get("method", "GET")
            
            # IMPRIME NO TERMINAL QUEM ESTÁ CHAMANDO
            # print(f"👀 ROTA CHAMADA: {method} {path}")

            if method == "POST" and (path == "/sse" or path == "/messages"):
                scope["path"] = "/messages/" 
        await self.app(scope, receive, send)

# --- 4. APP FINAL ---
mcp_asgi = mcp.sse_app()
async def health_check(request): return JSONResponse({"status": "online"})

routes = [Route("/", health_check), Route("/health", health_check), Mount("/", app=mcp_asgi)]
middleware = [
    Middleware(TrustedHostMiddleware, allowed_hosts=["*"]),
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    Middleware(DoubleXFixMiddleware)
]
starlette_app = Starlette(routes=routes, middleware=middleware)
