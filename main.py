import os
import httpx
import inspect
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# --- CONFIGURAÇÕES DE AMBIENTE E FALLBACKS ---
# Usamos os valores da sua imagem como padrão caso o ENV falhe
def get_config(key, default):
    val = os.getenv(key)
    if val and val.strip(): # Garante que não é vazio
        return val
    return default

AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN") # O Token DEVE estar no Render

# Seus IDs (Baseados nas imagens enviadas)
CONFIG = {
    "PLACE_ID": int(get_config("PLACE_ID", 6955)),
    "EVENT_ID": int(get_config("EVENT_ID", 526436)),
    "ACCOUNT_ID": int(get_config("ACCOUNT_ID", 74698)),
    "USER_ID": int(get_config("USER_ID", 28904)),
    "INSURANCE_ID": int(get_config("INSURANCE_ID", 1))
}

# --- SERVIDOR MCP ---
mcp = FastMCP("amigo-scheduler")

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """Busca um paciente pelo nome ou CPF."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {"name": nome, "cpf": cpf}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AMIGO_API_URL}/patients", params=params, headers=headers)
            # Retorna erro amigável se o token falhar
            if response.status_code == 401:
                return "Erro: Token de API inválido ou expirado."
            return str(response.json())
        except Exception as e:
            return f"Erro ao buscar paciente: {str(e)}"

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
            return f"Erro ao consultar agenda: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    """Realiza o agendamento de uma consulta."""
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
            return f"Agendamento realizado com sucesso! Detalhes: {str(response.json())}"
        except Exception as e:
            return f"Erro ao agendar: {str(e)}"

# --- ADAPTADOR UNIVERSAL (A Correção Definitiva) ---

# 1. Obtemos o app Starlette oficial
print("Iniciando configuração do servidor...")
starlette_app = mcp.sse_app()

# 2. Encontramos quem é o responsável por processar mensagens (/messages)
messages_endpoint = None
for route in starlette_app.routes:
    if getattr(route, "path", "") == "/messages":
        messages_endpoint = route.endpoint
        print("Endpoint de mensagens encontrado e capturado.")
        break

if not messages_endpoint:
    print("ALERTA CRÍTICO: Não foi possível encontrar o endpoint /messages original.")

# 3. Lista de caminhos que o Double X tentou acessar (segundo seus logs)
# Vamos redirecionar TODOS eles para o processador de mensagens
rotas_de_resgate = [
    "/sse",             # O Double X tenta POST aqui frequentemente
    "/tools/list",      # Tentativa comum de descoberta
    "/api/tools/list",  # Outra tentativa comum
    "/mcp/tools/list",  # Outra variação
    "/tools",           # Variação REST
    "/api/tools"        # Variação REST
]

# 4. Registramos o processador oficial em todas essas rotas "erradas"
if messages_endpoint:
    for path in rotas_de_resgate:
        # Aceitamos POST nessas rotas e entregamos para o MCP processar
        starlette_app.add_route(path, messages_endpoint, methods=["POST"])
        print(f"Rota de compatibilidade criada: POST {path} -> MCP Handler")

# 5. Rota de Health Check (Para parar os 404 de monitoramento)
async def health_check(request):
    return JSONResponse({
        "status": "online", 
        "mode": "compatibility_layer_active",
        "config_check": {"place_id": CONFIG["PLACE_ID"]}
    })

starlette_app.add_route("/health", health_check, methods=["GET"])
starlette_app.add_route("/", health_check, methods=["GET", "POST"]) # Raiz também responde

print("Servidor pronto para deploy.")
