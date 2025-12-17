import os
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env (crie esse arquivo se não tiver)
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
# Simples, sem hacks. O ngrok vai lidar com a conexão externa.
mcp = FastMCP("amigo-scheduler", dependencies=["httpx"])

# --- TOOLS ---

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """Busca paciente por nome ou CPF."""
    if not API_TOKEN: return "Erro: Token ausente no .env"
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
            return f"Erro ao buscar: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    """Consulta horários (YYYY-MM-DD)."""
    if not API_TOKEN: return "Erro: Token ausente."
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {"date": data, "event_id": CONFIG["EVENT_ID"], "place_id": CONFIG["PLACE_ID"], "insurance_id": CONFIG["INSURANCE_ID"]}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AMIGO_API_URL}/calendar", params=params, headers=headers, timeout=30.0)
            return str(resp.json())
        except Exception as e:
            return f"Erro ao consultar: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    """Realiza agendamento."""
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
            return f"Status: {resp.status_code} - {str(resp.json())}"
        except Exception as e:
            return f"Erro ao agendar: {str(e)}"

# --- EXPORTA O APP PARA O UVICORN ---
# O ngrok precisa acessar o endpoint /sse e /messages
app = mcp.sse_app()
