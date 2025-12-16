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

# Tenta carregar .env local (não afeta o Render que usa variáveis de ambiente)
load_dotenv()

# --- 1. CONFIGURAÇÕES ---
AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
# No Render, ele pegará das Environment Variables. Localmente, pega do .env
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

CONFIG = {
    "PLACE_ID": int(os.getenv("PLACE_ID", 6955)),
    "EVENT_ID": int(os.getenv("EVENT_ID", 526436)),
    "ACCOUNT_ID": int(os.getenv("ACCOUNT_ID", 74698)),
    "USER_ID": int(os.getenv("USER_ID", 28904)),
    "INSURANCE_ID": int(os.getenv("INSURANCE_ID", 1))
}

# --- 2. SERVIDOR MCP (Ferramentas) ---
mcp = FastMCP("amigo-scheduler")

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """
    Busca o cadastro de um paciente na base de dados.
    É obrigatório fornecer pelo menos um argumento: 'nome' ou 'cpf'.
    
    Args:
        nome: Nome completo ou parcial do paciente.
        cpf: CPF do paciente (apenas números ou formatado).
    """
    if not API_TOKEN: return "Erro: AMIGO_API_TOKEN não configurado."
    
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    if not nome and not cpf:
        return "Erro: Você precisa fornecer um Nome ou um CPF para buscar."
        
    params = {}
    if nome: params['name'] = nome
    if cpf: params['cpf'] = cpf

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AMIGO_API_URL}/patients", params=params, headers=headers)
            if response.status_code == 401: return "Erro: Token de API inválido ou expirado."
            return str(response.json())
        except Exception as e:
            return f"Erro na conexão com API: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    """
    Verifica a disponibilidade de agenda para uma data específica.
    Args:
        data: A data desejada no formato ISO 'YYYY-MM-DD' (Ex: '2025-12-25').
    """
    if not API_TOKEN: return "Erro: AMIGO_API_TOKEN não configurado."

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
            return f"Erro ao consultar agenda: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    """
    Finaliza e confirma o agendamento de uma consulta no sistema.
    Args:
        start_date: Data e hora do início. Formato: 'YYYY-MM-DD HH:MM:SS'.
        patient_id: O ID numérico do paciente (obtido via buscar_paciente).
        telefone: Telefone de contato para o agendamento.
    """
    if not API_TOKEN: return "Erro: AMIGO_API_TOKEN não configurado
