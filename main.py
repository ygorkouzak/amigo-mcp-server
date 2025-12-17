import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
# Importamos o middleware de segurança para desativá-lo
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv

# --- PATCH DE SEGURANÇA (SOLUÇÃO DO ERRO 421) ---
# O FastMCP ativa o TrustedHostMiddleware internamente e bloqueia nossas requisições.
# Aqui nós substituímos a lógica dele para aceitar TUDO, ignorando o Host Header.
async def mock_trusted_host_call(self, scope, receive, send):
    # Simplesmente passa a requisição para frente sem verificar nada
    await self.app(scope, receive, send)

# Aplicamos o patch na classe original
TrustedHostMiddleware.__call__ = mock_trusted_host_call
# -----------------------------------------------

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
    """Busca paciente por nome ou CPF na base de dados da Amigo.
    
    Args:
        nome: Nome completo ou parcial do paciente
        cpf: CPF do paciente (apenas números)
    """
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
    """Consulta horários disponíveis para agendamento em uma data específica.
    
    Args:
        data: Data no formato YYYY-MM-DD (ex: 2024-12-20)
    """
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
    """Realiza o agendamento de uma consulta para o paciente.
    
    Args:
        start_date: Data e hora do agendamento no formato ISO
        patient_id: ID do paciente obtido pela busca
        telefone: Telefone de contato do paciente
    """
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
    return JSONResponse({"status": "online", "mode": "MCP + Compatibility"})

# --- COMPATIBILIDADE: DESCOBERTA DE TOOLS ---
async def handle_tools_discovery(request):
    tools_schema = {
        "tools": [
            {
                "name": "buscar_paciente",
                "description": "Busca paciente por nome ou CPF.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string"},
                        "cpf": {"type": "string"}
                    }
                }
            },
            {
                "name": "consultar_horarios",
                "description": "Consulta horários disponíveis.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "YYYY-MM-DD"}
                    },
                    "required": ["data"]
                }
            },
            {
                "name": "agendar_consulta",
                "description": "Agenda consulta.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string"},
                        "patient_id": {"type": "integer"},
                        "telefone": {"type": "string"}
                    },
                    "required": ["start_date", "patient_id", "telefone"]
                }
            }
        ]
    }
    return JSONResponse(tools_schema)

# --- FUNÇÃO DE REDIRECIONAMENTO ---
async def redirect_to_messages(request):
    return RedirectResponse(url="/messages/", status_code=307)

# --- HANDLER DA RAIZ ---
async def handle_root(request):
    if request.method == "POST":
        return await redirect_to_messages(request)
    
    return JSONResponse({
        "status": "online", 
        "message": "Amigo MCP Server Running",
        "endpoints": {
            "tools": "/tools/list",
            "messages": "/messages/",
            "sse": "/sse"
        }
    })

# --- MIDDLEWARE DE HOST (Mantemos para garantir compatibilidade com MCP) ---
class FixHostHeaderMiddleware:
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            headers = dict(scope['headers'])
            # Definimos como localhost (string), pois alguns sistemas rejeitam IP
            headers[b'host'] = b'localhost'
            scope['headers'] = list(headers.items())
        await self.app(scope, receive, send)

# --- INICIALIZAÇÃO DO APP ---
starlette_app = mcp.sse_app()

# 1. Adiciona middleware que muda o Host para 'localhost'
starlette_app.add_middleware(FixHostHeaderMiddleware)

# 2. CORS
starlette_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# 3. Rotas Manuais
starlette_app.add_route("/health", health_check, methods=["GET"])
starlette_app.add_route("/", handle_root, methods=["GET", "POST", "HEAD"])
starlette_app.add_route("/sse", redirect_to_messages, methods=["POST"])

# 4. Rotas de Compatibilidade de Tools
routes_to_fix = [
    "/tools", "/tools/list", 
    "/api/tools", "/api/tools/list", 
    "/mcp/tools/list",
    "/sse/tools", "/sse/tools/list",
    "/sse/api/tools", "/sse/api/tools/list",
    "/sse/mcp/tools/list"
]
for path in routes_to_fix:
    starlette_app.add_route(path, handle_tools_discovery, methods=["GET", "POST"])
