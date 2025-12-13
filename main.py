import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request

# --- CONFIGURAÇÕES ---
AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

CONFIG = {
    "PLACE_ID": os.getenv("PLACE_ID"),
    "EVENT_ID": os.getenv("EVENT_ID"),
    "ACCOUNT_ID": os.getenv("ACCOUNT_ID"),
    "USER_ID": os.getenv("USER_ID"),
    "INSURANCE_ID": os.getenv("INSURANCE_ID", "1")
}

# --- DEFINIÇÃO DAS FERRAMENTAS MCP ---
mcp = FastMCP("amigo-scheduler")

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """Busca um paciente pelo nome ou CPF."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {"name": nome, "cpf": cpf}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AMIGO_API_URL}/patients", params=params, headers=headers)
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
        "insurance_id": int(CONFIG["INSURANCE_ID"]),
        "event_id": int(CONFIG["EVENT_ID"]),
        "user_id": int(CONFIG["USER_ID"]),
        "place_id": int(CONFIG["PLACE_ID"]),
        "start_date": start_date,
        "patient_id": patient_id,
        "account_id": int(CONFIG["ACCOUNT_ID"]),
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

# --- ESTRATÉGIA DO ENVELOPE (CORREÇÃO DO ERRO) ---

# Pegamos o app original (que é uma função e não deixa adicionar rotas)
mcp_asgi_app = mcp.sse_app

async def handle_hack_post(request: Request):
    """
    Recebe o POST errado no /sse, muda o caminho para /messages
    e repassa para o app original do MCP.
    """
    scope = request.scope
    scope["path"] = "/messages"  # Engana o app original
    # Chama o app original com o caminho corrigido
    await mcp_asgi_app(scope, request.receive, request.send)

# Criamos um app Starlette NOVO que nós controlamos
starlette_app = Starlette(routes=[
    # 1. Prioridade: Se for POST em /sse, usa nosso hack
    Route("/sse", handle_hack_post, methods=["POST"]),
    
    # 2. Todo o resto (GET /sse, POST /messages, etc) vai para o MCP original
    Mount("/", app=mcp_asgi_app)
])
