import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route
from starlette.responses import JSONResponse
from dotenv import load_dotenv

# Carrega variáveis
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

# --- SERVIDOR MCP ---
mcp = FastMCP("amigo-scheduler")

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """Busca paciente por nome ou CPF na base de dados da Amigo."""
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN ausente."
    
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {}
    
    if nome:
        params['name'] = nome
    if cpf:
        params['cpf'] = cpf
    
    if not params:
        return "Erro: Forneça nome ou CPF para buscar."

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{AMIGO_API_URL}/patients",
                params=params,
                headers=headers,
                timeout=30.0
            )
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Erro ao buscar paciente: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    """Consulta horários disponíveis para agendamento."""
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN ausente."
    
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {
        "date": data,
        "event_id": CONFIG["EVENT_ID"],
        "place_id": CONFIG["PLACE_ID"],
        "insurance_id": CONFIG["INSURANCE_ID"]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{AMIGO_API_URL}/calendar",
                params=params,
                headers=headers,
                timeout=30.0
            )
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Erro ao consultar horários: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    """Realiza o agendamento de uma consulta."""
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN ausente."
    
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    body = {
        "insurance_id": CONFIG["INSURANCE_ID"],
        "event_id": CONFIG["EVENT_ID"],
        "place_id": CONFIG["PLACE_ID"],
        "start_date": start_date,
        "patient_id": patient_id,
        "account_id": CONFIG["ACCOUNT_ID"],
        "user_id": CONFIG["USER_ID"],
        "chat_id": "doublex_integration",
        "scheduler_phone": telefone,
        "is_dependent_schedule": False
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{AMIGO_API_URL}/attendances",
                json=body,
                headers=headers,
                timeout=30.0
            )
            return f"Status: {resp.status_code}. Resposta: {str(resp.json())}"
        except Exception as e:
            return f"Erro ao agendar consulta: {str(e)}"

# --- ENDPOINT DE HEALTH CHECK ---
async def health_check(request):
    """Endpoint simples para verificar se o servidor está online"""
    return JSONResponse({
        "status": "online",
        "server": "amigo-mcp-server",
        "mode": "MCP Protocol",
        "tools": ["buscar_paciente", "consultar_horarios", "agendar_consulta"],
        "sse_endpoint": "https://amigo-mcp-server.onrender.com/sse"
    })

# --- ENDPOINT DE DESCOBERTA (O "CRACHÁ" PARA O DOUBLE X) ---
# O Double X está procurando a lista de ferramentas nestes endereços.
# Vamos entregar o JSON descritivo para ele parar de dar erro 404.
async def handle_tools_discovery(request):
    tools_list = [
        {
            "name": "buscar_paciente",
            "description": "Busca paciente por nome ou CPF na base de dados da Amigo.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Nome do paciente"},
                    "cpf": {"type": "string", "description": "CPF apenas números"}
                }
            }
        },
        {
            "name": "consultar_horarios",
            "description": "Consulta horários disponíveis em uma data.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "Data YYYY-MM-DD"}
                },
                "required": ["data"]
            }
        },
        {
            "name": "agendar_consulta",
            "description": "Agenda uma consulta.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Data ISO ex: 2024-12-20T14:30:00"},
                    "patient_id": {"type": "integer", "description": "ID do paciente"},
                    "telefone": {"type": "string", "description": "Telefone de contato"}
                },
                "required": ["start_date", "patient_id", "telefone"]
            }
        }
    ]
    return JSONResponse({"tools": tools_list})

# --- MIDDLEWARE DE HOST (Mantém o servidor seguro e acessível) ---
class FixHostHeaderMiddleware:
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            headers = dict(scope['headers'])
            headers[b'host'] = b'127.0.0.1'
            scope['headers'] = list(headers.items())
        await self.app(scope, receive, send)

# --- CONFIGURAÇÃO FINAL ---

# 1. App original do MCP
starlette_app = mcp.sse_app()

# 2. Middleware de Host (PRIMEIRO)
starlette_app.add_middleware(FixHostHeaderMiddleware)

# 3. Middleware de CORS
starlette_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# 4. Rota Health Check
starlette_app.add_route("/health", health_check, methods=["GET"])

# 5. ROTAS DE COMPATIBILIDADE PARA O DOUBLE X (Resolve os erros 404)
# Registramos todas as URLs que ele tentou acessar nos logs
debug_paths = [
    "/tools", 
    "/tools/list", 
    "/api/tools", 
    "/api/tools/list", 
    "/mcp/tools/list"
]

for path in debug_paths:
    starlette_app.add_route(path, handle_tools_discovery, methods=["GET", "POST"])
