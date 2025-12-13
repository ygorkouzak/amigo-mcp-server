import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import Response

# Configurações
AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

CONFIG = {
    "PLACE_ID": os.getenv("PLACE_ID"),
    "EVENT_ID": os.getenv("EVENT_ID"),
    "ACCOUNT_ID": os.getenv("ACCOUNT_ID"),
    "USER_ID": os.getenv("USER_ID"),
    "INSURANCE_ID": os.getenv("INSURANCE_ID", "1")
}

# Inicializa o FastMCP
mcp = FastMCP("amigo-scheduler")

# --- SUAS FERRAMENTAS (Mantidas Iguais) ---
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

# --- CORREÇÃO DE ROTA PARA CLIENTES CONFUSOS ---
starlette_app = mcp.sse_app

# Adiciona um redirecionamento manual: Se tentarem POST em /sse, joga para /messages
@starlette_app.post("/sse")
async def handle_sse_post(request: Request):
    # Redireciona internamente a requisição para a rota correta de mensagens
    from mcp.server.sse import messages_handler
    # Precisamos chamar o handler de mensagens manualmente
    return await messages_handler(request)

# Adiciona uma rota de verificação simples
@starlette_app.get("/health")
async def health_check():
    return {"status": "ok", "tools": len(mcp._tools)}
