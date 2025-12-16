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

# Carrega variáveis
load_dotenv()

# --- 1. CONFIGURAÇÕES ---
AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

# 👇 LISTA DE DOMÍNIOS PERMITIDOS (A FORMA CORRETA)
# Aqui dizemos explicitamente quem pode acessar este servidor.
ALLOWED_HOSTS = [
    "amigo-mcp-server.onrender.com",  # Seu domínio no Render
    "localhost",                      # Para testes locais
    "127.0.0.1",                      # Para testes locais
    "0.0.0.0"                         # Para o container interno
]

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
    """Busca paciente por nome ou CPF."""
    if not API_TOKEN: return "Erro: AMIGO_API_TOKEN ausente."
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {}
    if nome: params['name'] = nome
    if cpf: params['cpf'] = cpf
    if not params: return "Erro: Forneça nome ou CPF."

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AMIGO_API_URL}/patients", params=params, headers=headers)
            return str(resp.json())
        except Exception as e:
            return f"Erro API: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    """Consulta horários para YYYY-MM-DD."""
    if not API_TOKEN: return "Erro: AMIGO_API_TOKEN ausente."
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {
        "date": data, "event_id": CONFIG["EVENT_ID"],
        "place_id": CONFIG["PLACE_ID"], "insurance_id": CONFIG["INSURANCE_ID"]
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AMIGO_API_URL}/calendar", params=params, headers=headers)
            return str(resp.json())
        except Exception as e:
            return f"Erro API: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    """Realiza o agendamento."""
    if not API_TOKEN: return "Erro: AMIGO_API_TOKEN ausente."
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    body = {
        "insurance_id": CONFIG["INSURANCE_ID"], "event_id": CONFIG["EVENT_ID"],
        "place_id": CONFIG["PLACE_ID"], "start_date": start_date,
        "patient_id": patient_id, "account_id": CONFIG["ACCOUNT_ID"],
        "user_id": CONFIG["USER_ID"], "chat_id": "whatsapp_integration",
        "scheduler_phone": telefone, "is_dependent_schedule": False
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{AMIGO_API_URL}/attendances", json=body, headers=headers)
            return f"Status: {resp.status_code}. Resp: {str(resp.json())}"
        except Exception as e:
            return f"Erro API: {str(e)}"

# --- 3. CONFIGURAÇÃO OFICIAL DE SEGURANÇA ---
# Criamos o app SSE do MCP
mcp_asgi_app = mcp.sse_app()

async def health_check(request):
    return JSONResponse({"status": "online", "mode": "Production Secure"})

routes = [
    Route("/", health_check),
    Route("/health", health_check),
    Mount("/", app=mcp_asgi_app)
]

# MIDDLEWARES: AQUI ESTÁ A CORREÇÃO REAL
middleware = [
    # 1. Segurança de Host: Permite APENAS os domínios listados em ALLOWED_HOSTS
    Middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS),
    
    # 2. CORS: Permite que o Double X (navegador/servidor externo) acesse nossa API
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
]

# Montamos o app final com as regras oficiais
starlette_app = Starlette(routes=routes, middleware=middleware)
