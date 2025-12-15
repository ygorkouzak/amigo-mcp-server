import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

# --- CONFIGURAÇÕES ---
def get_config(key, default):
    val = os.getenv(key)
    if val and val.strip():
        return val
    return default

AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

CONFIG = {
    "PLACE_ID": int(get_config("PLACE_ID", 6955)),
    "EVENT_ID": int(get_config("EVENT_ID", 526436)),
    "ACCOUNT_ID": int(get_config("ACCOUNT_ID", 74698)),
    "USER_ID": int(get_config("USER_ID", 28904)),
    "INSURANCE_ID": int(get_config("INSURANCE_ID", 1))
}

# --- SERVIDOR MCP (Ferramentas) ---
mcp = FastMCP("amigo-scheduler")

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """
    Busca o cadastro de um paciente na base de dados.
    
    É obrigatório fornecer pelo menos um dos argumentos (nome ou cpf).
    
    Args:
        nome: Nome completo ou parcial do paciente para busca.
        cpf: CPF do paciente (apenas números ou com pontuação).
    """
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    # Pequena melhoria: garantir que cpf ou nome existam
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
            return f"Erro na conexão: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    """
    Verifica a disponibilidade de agenda para uma data específica.
    Use esta ferramenta antes de tentar agendar qualquer consulta.
    
    Args:
        data: A data desejada no formato ISO 'YYYY-MM-DD' (Ex: '2025-12-25').
    """
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
            # Dica: Se a resposta for vazia, a IA saberá que não tem horário
            return str(response.json())
        except Exception as e:
            return f"Erro ao consultar agenda: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    """
    Finaliza e confirma o agendamento de uma consulta no sistema.
    
    ATENÇÃO: Só use esta ferramenta após o usuário confirmar explicitamente o horário.
    
    Args:
        start_date: A data e hora exata do início da consulta. Formato esperado: 'YYYY-MM-DD HH:MM:SS' (ou ISO 8601).
        patient_id: O ID numérico do paciente (obtido via buscar_paciente).
        telefone: O telefone de contato para este agendamento.
    """
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    body = {
        "insurance_id": CONFIG["INSURANCE_ID"],
        "event_id": CONFIG["EVENT_ID"],
        "place_id": CONFIG["PLACE_ID"],
        "start_date": start_date,
        "patient_id": patient_id,
        "account_id": CONFIG["ACCOUNT_ID"],
        "user_id": CONFIG["USER_ID"],
        "chat_id": "whatsapp_integration",
        "scheduler_phone": telefone,
        "is_dependent_schedule": False
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{AMIGO_API_URL}/attendances", json=body, headers=headers)
            if response.status_code in [200, 201]:
                return f"Agendamento realizado com sucesso! Detalhes: {str(response.json())}"
            else:
                return f"Falha ao agendar. Status: {response.status_code}. Resposta: {response.text}"
        except Exception as e:
            return f"Erro crítico ao agendar: {str(e)}"

# --- MONTAGEM DO APP FINAL ---

# 1. Pegamos o app MCP
mcp_asgi_app = mcp.sse_app()

# 2. Rota de Health Check
async def health_check(request):
    return JSONResponse({"status": "online", "mcp_mode": "active"})

routes = [
    Route("/health", health_check),
    # Montamos o MCP na raiz. O Middleware acima vai garantir que os pedidos cheguem certos.
    Mount("/", app=mcp_asgi_app)
]

# 3. Definição da Pilha de Middlewares (A ordem importa!)
# O CORS vem primeiro (libera a entrada), depois o Rewriter (corrige o endereço)
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    ),
    Middleware(DoubleXRewriterMiddleware)
]

# 4. App Final
starlette_app = Starlette(routes=routes, middleware=middleware)
