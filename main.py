import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse

# --- CONFIGURAÇÕES DE AMBIENTE ---
def get_config(key, default):
    val = os.getenv(key)
    if val and val.strip():
        return val
    return default

AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

# IDs configurados (com fallback para os valores da sua imagem)
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
            if response.status_code == 401:
                return "Erro: Token inválido."
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
            return f"Sucesso: {str(response.json())}"
        except Exception as e:
            return f"Erro: {str(e)}"

# --- CORREÇÃO FINAL (Estratégia: Envelope Cego) ---

# 1. Pegamos o app original (chamando a função fábrica corretamente)
mcp_asgi_app = mcp.sse_app()

# 2. Handler de redirecionamento
# (Simplesmente muda o destino para /messages e repassa para o app original)
async def handle_compatibility_post(request: Request):
    scope = request.scope
    scope["path"] = "/messages"  # Truque de mágica: muda o destino
    await mcp_asgi_app(scope, request.receive, request.send)

# 3. Lista de rotas problemáticas (Baseado nos seus logs)
bad_routes = [
    "/sse",
    "/tools/list",
    "/api/tools/list",
    "/mcp/tools/list",
    "/tools",
    "/api/tools"
]

# 4. Construção manual das rotas do Envelope
routes = []

# Adiciona o redirecionamento para cada rota ruim (apenas POST)
for path in bad_routes:
    routes.append(Route(path, handle_compatibility_post, methods=["POST"]))

# Adiciona Health Check
async def health_check(request):
    return JSONResponse({"status": "online", "mode": "envelope_active"})
routes.append(Route("/health", health_check))
routes.append(Route("/", health_check))

# 5. IMPORTANTE: Monta o app original na raiz para tratar todo o resto
# (Isso garante que o GET /sse continue funcionando para abrir a conexão)
routes.append(Mount("/", app=mcp_asgi_app))

# 6. Cria o app final que o Uvicorn vai rodar
starlette_app = Starlette(routes=routes)
