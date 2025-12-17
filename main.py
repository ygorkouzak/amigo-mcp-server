import os
import httpx
import logging
from mcp.server.fastmcp import FastMCP
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

# --- SERVIDOR MCP ---
# Instanciamos LIMPO, sem 'settings', para não dar erro de versão
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

# --- ASGI WRAPPER (A SOLUÇÃO DO ERRO 421 E COMPATIBILIDADE) ---

# 1. Pegamos a aplicação original do MCP
original_app = mcp.sse_app()

# 2. Handler manual para descoberta de tools (Para o Double X)
async def handle_tools_discovery(scope, receive, send):
    tools_schema = {
        "tools": [
            {"name": "buscar_paciente", "description": "Busca paciente.", "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}, "cpf": {"type": "string"}}}},
            {"name": "consultar_horarios", "description": "Consulta horários.", "input_schema": {"type": "object", "properties": {"data": {"type": "string"}}, "required": ["data"]}},
            {"name": "agendar_consulta", "description": "Agenda.", "input_schema": {"type": "object", "properties": {"start_date": {"type": "string"}, "patient_id": {"type": "integer"}, "telefone": {"type": "string"}}, "required": ["start_date", "patient_id", "telefone"]}}
        ]
    }
    response = JSONResponse(tools_schema)
    await response(scope, receive, send)

# 3. APLICAÇÃO PRINCIPAL (Wrapper)
# Esta é a função que o Uvicorn vai rodar. Ela protege o FastMCP.
async def app(scope, receive, send):
    if scope['type'] == 'http':
        # --- PASSO CRÍTICO: REESCRITA DE HOST ---
        # Enganamos o FastMCP fazendo ele acreditar que é localhost
        headers = dict(scope.get('headers', []))
        headers[b'host'] = b'localhost'
        scope['headers'] = list(headers.items())

        path = scope['path']
        
        # Rotas Manuais (Interceptação)
        if path == '/health':
            response = JSONResponse({"status": "online", "mode": "ASGI Wrapper"})
            await response(scope, receive, send)
            return
            
        # Compatibilidade com Double X (Tools List em vários caminhos)
        if 'tools' in path and 'list' in path:
            await handle_tools_discovery(scope, receive, send)
            return

        # Redirecionamento Inteligente (POST / ou /sse -> /messages/)
        if (path == '/' or path == '/sse') and scope['method'] == 'POST':
            response = RedirectResponse(url="/messages/", status_code=307)
            await response(scope, receive, send)
            return

        # Raiz GET (Apenas visualização)
        if path == '/' and scope['method'] == 'GET':
             response = JSONResponse({"status": "online", "message": "Amigo MCP Running via Wrapper"})
             await response(scope, receive, send)
             return

    # Se não foi interceptado, entrega para o FastMCP (que agora está seguro)
    await original_app(scope, receive, send)
