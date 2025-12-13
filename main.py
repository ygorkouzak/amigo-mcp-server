import os
import httpx
from mcp.server.fastmcp import FastMCP

# Configurações via Variáveis de Ambiente
AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

# IDs da Clínica
CONFIG = {
    "PLACE_ID": os.getenv("PLACE_ID"),
    "EVENT_ID": os.getenv("EVENT_ID"),
    "ACCOUNT_ID": os.getenv("ACCOUNT_ID"),
    "USER_ID": os.getenv("USER_ID"),
    "INSURANCE_ID": os.getenv("INSURANCE_ID", "1")
}

# Inicializa o FastMCP
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

# --- A CORREÇÃO ESTÁ AQUI EMBAIXO ---
# Isso extrai o servidor web real de dentro do gerenciador mcp
starlette_app = mcp.sse_app
