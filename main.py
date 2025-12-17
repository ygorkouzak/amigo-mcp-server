import os
import httpx
import logging
from mcp.server.fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
load_dotenv()

# --- CONFIGURAÇÕES ---
AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

CONFIG = {
    "PLACE_ID": int(os.getenv("PLACE_ID", 6955)),
    "EVENT_ID": int(os.getenv("EVENT_ID", 526436)),
    "ACCOUNT_ID": int(os.getenv("ACCOUNT_ID", 74698)),
    "USER_ID": int(os.getenv("USER_ID", 28904)),
    "INSURANCE_ID": int(os.getenv("INSURANCE_ID", 1))
}

# Rotas de compatibilidade
COMPATIBILITY_ROUTES = [
    "/tools", "/tools/list", 
    "/api/tools", "/api/tools/list", 
    "/mcp/tools/list",
    "/sse/tools", "/sse/tools/list",
    "/sse/api/tools", "/sse/api/tools/list",
    "/sse/mcp/tools/list"
]

# --- SERVIDOR MCP ---
# Instanciação padrão
mcp = FastMCP("amigo-scheduler", dependencies=["httpx"])

# --- DEFINIÇÃO DAS TOOLS ---

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    if not API_TOKEN: return "Erro: Token ausente."
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {}
    if nome: params['name'] = nome
    if cpf: params['cpf'] = cpf
    if not params: return "Erro: Forneça nome ou CPF."

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AMIGO_API_URL}/patients", params=params, headers=headers, timeout=30.0)
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Erro ao buscar paciente: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    if not API_TOKEN: return "Erro: Token ausente."
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {"date": data, "event_id": CONFIG["EVENT_ID"], "place_id": CONFIG["PLACE_ID"], "insurance_id": CONFIG["INSURANCE_ID"]}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AMIGO_API_URL}/calendar", params=params, headers=headers, timeout=30.0)
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Erro ao consultar horários: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    if not API_TOKEN: return "Erro: Token ausente."
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    body = {
        "insurance_id": CONFIG["INSURANCE_ID"], "event_id": CONFIG["EVENT_ID"], "place_id": CONFIG["PLACE_ID"],
        "start_date": start_date, "patient_id": patient_id, "account_id": CONFIG["ACCOUNT_ID"],
        "user_id": CONFIG["USER_ID"], "chat_id": "doublex_integration", "scheduler_phone": telefone, "is_dependent_schedule": False
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{AMIGO_API_URL}/attendances", json=body, headers=headers, timeout=30.0)
            return f"Status: {resp.status_code}. Resposta: {str(resp.json())}"
        except Exception as e:
            return f"Erro ao agendar: {str(e)}"

# --- HANDLERS AUXILIARES ---

async def health_check(request):
    return JSONResponse({"status": "online", "mode": "Production Unlocked"})

async def handle_tools_discovery(request):
    tools_schema = {
        "tools": [
            {"name": "buscar_paciente", "description": "Busca paciente.", "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}, "cpf": {"type": "string"}}}},
            {"name": "consultar_horarios", "description": "Consulta horários.", "input_schema": {"type": "object", "properties": {"data": {"type": "string"}}, "required": ["data"]}},
            {"name": "agendar_consulta", "description": "Agenda.", "input_schema": {"type": "object", "properties": {"start_date": {"type": "string"}, "patient_id": {"type": "integer"}, "telefone": {"type": "string"}}, "required": ["start_date", "patient_id", "telefone"]}}
        ]
    }
    return JSONResponse(tools_schema)

async def redirect_to_messages(request):
    return RedirectResponse(url="/messages/", status_code=307)

async def handle_root(request):
    if request.method == "POST": return await redirect_to_messages(request)
    return JSONResponse({"status": "online", "message": "Amigo MCP Server Running"})

# --- MONTAGEM E LIMPEZA DA APP ---

# 1. Gera o app com os padrões do FastMCP (que incluem a segurança bloqueadora)
app = mcp.sse_app()

# 2. OPERAÇÃO LIMPEZA: Removemos middlewares de segurança
# Acessamos a lista de middlewares configurados e removemos qualquer coisa relacionada a "TrustedHost"
if hasattr(app, 'user_middleware'):
    # Filtramos a lista mantendo apenas o que NÃO É segurança de host
    app.user_middleware = [
        m for m in app.user_middleware 
        if "TrustedHostMiddleware" not in str(m.cls)
    ]
    # Forçamos o Starlette a esquecer a stack antiga
    app.middleware_stack = None 
    print("✅ Camada de segurança TrustedHostMiddleware removida manualmente.")

# 3. Adiciona CORS (Permite tudo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# 4. Rotas Manuais
app.add_route("/health", health_check, methods=["GET"])
app.add_route("/", handle_root, methods=["GET", "POST", "HEAD"])
app.add_route("/sse", redirect_to_messages, methods=["POST"])

for path in COMPATIBILITY_ROUTES:
    app.add_route(path, handle_tools_discovery, methods=["GET", "POST"])
