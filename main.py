import os
import httpx
from mcp.server.fastmcp import FastMCP
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

# --- INICIALIZAÇÃO DO SERVIDOR ---
# REMOVIDO: settings={"allowed_hosts": ["*"]} (Causava erro na versão instalada)
# A segurança será gerenciada pelas variáveis de ambiente do Render (MCP_ALLOWED_HOSTS=*)
mcp = FastMCP("amigo-scheduler", dependencies=["httpx"])

# --- DEFINIÇÃO DAS TOOLS ---

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """Busca paciente por nome ou CPF na base de dados da Amigo."""
    if not API_TOKEN: return "Erro: Token ausente."
    
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {}
    if nome: params['name'] = nome
    if cpf: params['cpf'] = cpf
    
    if not params: return "Erro: Forneça nome ou CPF."

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{AMIGO_API_URL}/patients", params=params, headers=headers, timeout=30.0
            )
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Erro ao buscar paciente: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    """Consulta horários disponíveis (Formato data: YYYY-MM-DD)."""
    if not API_TOKEN: return "Erro: Token ausente."
    
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
                f"{AMIGO_API_URL}/calendar", params=params, headers=headers, timeout=30.0
            )
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Erro ao consultar horários: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    """Realiza agendamento."""
    if not API_TOKEN: return "Erro: Token ausente."
    
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
                f"{AMIGO_API_URL}/attendances", json=body, headers=headers, timeout=30.0
            )
            return f"Status: {resp.status_code}. Resposta: {str(resp.json())}"
        except Exception as e:
            return f"Erro ao agendar: {str(e)}"

# --- PONTO DE ENTRADA ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # Inicia o servidor. A configuração de host deve vir do ambiente.
    mcp.run(transport="sse", host="0.0.0.0", port=port)
