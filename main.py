import os
import sys
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from dotenv import load_dotenv

# ============================================
# SOLUÇÃO DIRETA E SIMPLES
# ============================================

# 1. DESATIVA VERIFICAÇÃO DE HOST ANTES DE QUALQUER COISA
import starlette.middleware.trustedhost

# Substitui o TrustedHostMiddleware por um que não faz nada
class NoOpTrustedHostMiddleware:
    def __init__(self, app, allowed_hosts=None, www_redirect=True):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

starlette.middleware.trustedhost.TrustedHostMiddleware = NoOpTrustedHostMiddleware

# 2. Configura variáveis de ambiente
load_dotenv()

AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

CONFIG = {
    "PLACE_ID": int(os.getenv("PLACE_ID", "6955")),
    "EVENT_ID": int(os.getenv("EVENT_ID", "526436")),
    "ACCOUNT_ID": int(os.getenv("ACCOUNT_ID", "74698")),
    "USER_ID": int(os.getenv("USER_ID", "28904")),
    "INSURANCE_ID": int(os.getenv("INSURANCE_ID", "1"))
}

# ============================================
# SERVIDOR MCP SIMPLES
# ============================================

# Cria o servidor MCP da maneira mais simples possível
mcp = FastMCP("amigo-scheduler")

# ============================================
# FERRAMENTAS (TOOLS)
# ============================================

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """Busca paciente por nome ou CPF na base de dados da Amigo."""
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN ausente."
    
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {}
    
    if nome:
        params['name'] = nome
    if cpf:
        params['cpf'] = cpf
    
    if not params:
        return "Erro: Forneça nome ou CPF para buscar."

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{AMIGO_API_URL}/patients",
                params=params,
                headers=headers,
                timeout=30.0
            )
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Erro ao buscar paciente: {str(e)}"

@mcp.tool()
async def consultar_horarios(data: str) -> str:
    """Consulta horários disponíveis para agendamento em uma data específica."""
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN ausente."
    
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
                f"{AMIGO_API_URL}/calendar",
                params=params,
                headers=headers,
                timeout=30.0
            )
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Erro ao consultar horários: {str(e)}"

@mcp.tool()
async def agendar_consulta(start_date: str, patient_id: int, telefone: str) -> str:
    """Realiza o agendamento de uma consulta para o paciente."""
    if not API_TOKEN:
        return "Erro: AMIGO_API_TOKEN ausente."
    
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
                f"{AMIGO_API_URL}/attendances",
                json=body,
                headers=headers,
                timeout=30.0
            )
            return f"Status: {resp.status_code}. Resposta: {str(resp.json())}"
        except Exception as e:
            return f"Erro ao agendar consulta: {str(e)}"

# ============================================
# CONFIGURAÇÃO DO APP
# ============================================

# Obtém o app do MCP
app = mcp.sse_app

# Adiciona CORS - PERMITE TUDO
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
    expose_headers=["*"]
)

# Health check endpoint
@app.route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "online", "service": "Amigo MCP Server"})

@app.route("/", methods=["GET"])
async def root(request):
    return JSONResponse({
        "message": "Amigo MCP Server está online!",
        "endpoints": ["/health", "/tools"],
        "docs": "Integração com API do Amigo para agendamentos"
    })

# Endpoint para listar tools (compatibilidade)
@app.route("/tools", methods=["GET"])
async def list_tools(request):
    tools = [
        {
            "name": "buscar_paciente",
            "description": "Busca paciente por nome ou CPF",
            "parameters": {
                "nome": {"type": "string", "optional": True},
                "cpf": {"type": "string", "optional": True}
            }
        },
        {
            "name": "consultar_horarios",
            "description": "Consulta horários disponíveis",
            "parameters": {
                "data": {"type": "string", "required": True, "format": "YYYY-MM-DD"}
            }
        },
        {
            "name": "agendar_consulta",
            "description": "Agenda consulta",
            "parameters": {
                "start_date": {"type": "string", "required": True, "format": "ISO"},
                "patient_id": {"type": "integer", "required": True},
                "telefone": {"type": "string", "required": True}
            }
        }
    ]
    return JSONResponse({"tools": tools})

# ============================================
# MIDDLEWARE FINAL PARA GARANTIR FUNCIONAMENTO
# ============================================

# Middleware que força aceitação de qualquer host
class ForceAcceptHostMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            # Remove qualquer verificação de host
            pass
        await self.app(scope, receive, send)

# Adiciona nosso middleware de força como o PRIMEIRO middleware
# Precisamos fazer isso manualmente reconstruindo a pilha

# 1. Remove todos os middlewares atuais
original_middleware = getattr(app, 'user_middleware', [])

# 2. Cria nova lista começando com nosso middleware
new_middleware = [
    {"cls": ForceAcceptHostMiddleware, "options": {}},
    *original_middleware
]

# 3. Aplica os novos middlewares
app.user_middleware.clear()
for mw in new_middleware:
    app.add_middleware(mw["cls"], **mw.get("options", {}))

# 4. Força reconstrução
try:
    app.middleware_stack = None
    app.build_middleware_stack()
except:
    pass  # Se falhar, o app vai reconstruir quando necessário

# ============================================
# EXECUÇÃO
# ============================================

# Para Render, exportamos o app diretamente
# O Render vai executar: uvicorn main:app --host 0.0.0.0 --port $PORT

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Iniciando Amigo MCP Server...")
    print(f"📊 Configurações: PLACE_ID={CONFIG['PLACE_ID']}, EVENT_ID={CONFIG['EVENT_ID']}")
    print("🔓 Modo de segurança: ACEITA QUALQUER HOST")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000")),
        # Configurações cruciais para evitar erro 421
        proxy_headers=True,
        forwarded_allow_ips="*",
        # Timeouts generosos
        timeout_keep_alive=30,
        # Logs para debug
        log_level="info"
    )
