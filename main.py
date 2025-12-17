import os
import sys
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from dotenv import load_dotenv

# ============================================
# SOLUÇÃO NUCLEAR - DESATIVA TODAS VERIFICAÇÕES DE HOST
# ============================================

# 1. Monkey patch ULTRA agressivo antes de qualquer import
import starlette.middleware.trustedhost

# Substitui completamente o TrustedHostMiddleware por uma classe que não faz NADA
class NoOpTrustedHostMiddleware:
    def __init__(self, app, allowed_hosts=None, www_redirect=True):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        # Simplesmente passa a requisição para frente SEM NENHUMA VERIFICAÇÃO
        await self.app(scope, receive, send)

# Aplica o patch em TODOS os lugares possíveis
starlette.middleware.trustedhost.TrustedHostMiddleware = NoOpTrustedHostMiddleware
sys.modules['starlette.middleware.trustedhost'].TrustedHostMiddleware = NoOpTrustedHostMiddleware

# 2. Configura variáveis de ambiente para forçar comportamento permissivo
os.environ['UVICORN_ALLOWED_HOSTS'] = '*'
os.environ['ALLOWED_HOSTS'] = '*'
os.environ['FORWARDED_ALLOW_IPS'] = '*'

# ============================================
# CONFIGURAÇÕES
# ============================================

load_dotenv()

AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
API_TOKEN = os.getenv("AMIGO_API_TOKEN")

if not API_TOKEN:
    print("⚠️  AVISO: AMIGO_API_TOKEN não encontrado no .env")
    print("ℹ️  Certifique-se de que o arquivo .env existe e contém:")
    print("   AMIGO_API_TOKEN=seu_token_aqui")
    print("   PLACE_ID=6955")
    print("   EVENT_ID=526436")
    print("   ACCOUNT_ID=74698")
    print("   USER_ID=28904")
    print("   INSURANCE_ID=1")

CONFIG = {
    "PLACE_ID": int(os.getenv("PLACE_ID", "6955")),
    "EVENT_ID": int(os.getenv("EVENT_ID", "526436")),
    "ACCOUNT_ID": int(os.getenv("ACCOUNT_ID", "74698")),
    "USER_ID": int(os.getenv("USER_ID", "28904")),
    "INSURANCE_ID": int(os.getenv("INSURANCE_ID", "1"))
}

# ============================================
# MIDDLEWARE PERSONALIZADO - IMPEDE QUALQUER BLOQUEIO
# ============================================

class AbsoluteHostFreedomMiddleware:
    """Middleware que intercepta e MODIFICA qualquer verificação de host"""
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        # Se for uma requisição HTTP
        if scope['type'] == 'http':
            # Modifica os headers para forçar aceitação
            headers = dict(scope.get('headers', []))
            
            # Remove qualquer header problemático
            headers_to_remove = []
            for key in headers:
                if key.lower() in [b'host', b'x-forwarded-host', b'x-original-host']:
                    headers_to_remove.append(key)
            
            for key in headers_to_remove:
                del headers[key]
            
            # Adiciona um header Host genérico
            headers[b'host'] = b'amigo-mcp-server.onrender.com'
            
            # Atualiza os headers no scope
            scope['headers'] = [(k, v) for k, v in headers.items()]
        
        # Passa para o próximo middleware/app
        await self.app(scope, receive, send)

# ============================================
# SERVIDOR MCP
# ============================================

# Cria o MCP server SEM configurar allowed_hosts (deixamos nosso middleware cuidar disso)
mcp = FastMCP(
    "amigo-scheduler",
    # Desabilita qualquer middleware padrão do FastMCP
    middleware=[]
)

# ============================================
# FERRAMENTAS (TOOLS)
# ============================================

@mcp.tool()
async def buscar_paciente(nome: str = None, cpf: str = None) -> str:
    """Busca paciente por nome ou CPF na base de dados da Amigo.
    
    Args:
        nome: Nome completo ou parcial do paciente
        cpf: CPF do paciente (apenas números)
    """
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
    """Consulta horários disponíveis para agendamento em uma data específica.
    
    Args:
        data: Data no formato YYYY-MM-DD (ex: 2024-12-20)
    """
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
    """Realiza o agendamento de uma consulta para o paciente.
    
    Args:
        start_date: Data e hora do agendamento no formato ISO
        patient_id: ID do paciente obtido pela busca
        telefone: Telefone de contato do paciente
    """
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
# ENDPOINTS ADICIONAIS
# ============================================

async def health_check(request):
    """Endpoint de health check"""
    return JSONResponse({
        "status": "online",
        "service": "Amigo MCP Server",
        "version": "1.0.0",
        "features": ["buscar_paciente", "consultar_horarios", "agendar_consulta"]
    })

async def tools_list(request):
    """Endpoint de compatibilidade para listar tools"""
    tools_schema = {
        "tools": [
            {
                "name": "buscar_paciente",
                "description": "Busca paciente por nome ou CPF na base de dados da Amigo.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string", "description": "Nome completo ou parcial do paciente"},
                        "cpf": {"type": "string", "description": "CPF do paciente (apenas números)"}
                    },
                    "anyOf": [
                        {"required": ["nome"]},
                        {"required": ["cpf"]}
                    ]
                }
            },
            {
                "name": "consultar_horarios",
                "description": "Consulta horários disponíveis para agendamento em uma data específica.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "Data no formato YYYY-MM-DD (ex: 2024-12-20)"}
                    },
                    "required": ["data"]
                }
            },
            {
                "name": "agendar_consulta",
                "description": "Realiza o agendamento de uma consulta para o paciente.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Data e hora do agendamento no formato ISO"},
                        "patient_id": {"type": "integer", "description": "ID do paciente obtido pela busca"},
                        "telefone": {"type": "string", "description": "Telefone de contato do paciente"}
                    },
                    "required": ["start_date", "patient_id", "telefone"]
                }
            }
        ]
    }
    return JSONResponse(tools_schema)

async def root(request):
    """Endpoint raiz"""
    return JSONResponse({
        "message": "Amigo MCP Server está online!",
        "endpoints": {
            "/health": "GET - Health check",
            "/tools": "GET - Lista de ferramentas disponíveis",
            "/sse": "POST - Conexão SSE para MCP"
        },
        "docs": "Este servidor fornece integração com a API do Amigo para agendamento de consultas."
    })

# ============================================
# CONFIGURAÇÃO DO APP STARLETTE
# ============================================

# Obtém o app do MCP
app = mcp.sse_app

# Verifica e remove QUALQUER TrustedHostMiddleware existente
if hasattr(app, 'user_middleware'):
    # Filtra qualquer middleware que contenha 'TrustedHost' no nome
    app.user_middleware = [
        mw for mw in app.user_middleware 
        if 'trustedhost' not in str(mw.cls).lower() and 'TrustedHost' not in str(mw.cls)
    ]
    # Reconstroi o stack de middleware
    app.middleware_stack = None

# Adiciona nosso middleware de liberdade de host PRIMEIRO
app.add_middleware(AbsoluteHostFreedomMiddleware)

# Adiciona CORS - PERMITE TUDO
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas as origens
    allow_methods=["*"],  # Permite todos os métodos
    allow_headers=["*"],  # Permite todos os headers
    allow_credentials=True,
    expose_headers=["*"]
)

# Adiciona endpoints manuais
app.add_route("/health", health_check, methods=["GET"])
app.add_route("/", root, methods=["GET", "POST", "HEAD", "OPTIONS"])
app.add_route("/tools", tools_list, methods=["GET", "POST", "OPTIONS"])
app.add_route("/tools/list", tools_list, methods=["GET", "POST", "OPTIONS"])
app.add_route("/api/tools", tools_list, methods=["GET", "POST", "OPTIONS"])
app.add_route("/mcp/tools", tools_list, methods=["GET", "POST", "OPTIONS"])

# Força a reconstrução do middleware stack
try:
    app.build_middleware_stack()
except:
    pass  # Ignora erros, o app vai reconstruir quando necessário

# ============================================
# CONFIGURAÇÃO UVICORN PERSONALIZADA
# ============================================

class PermissiveUvicornConfig:
    """Configuração do Uvicorn que desativa TODAS as verificações de segurança"""
    
    @staticmethod
    def create_app():
        """Cria e configura o app para execução"""
        # Imprime informações de diagnóstico
        print("=" * 60)
        print("🚀 AMIGO MCP SERVER - STARTING")
        print("=" * 60)
        print(f"📊 Configurações carregadas:")
        print(f"   PLACE_ID: {CONFIG['PLACE_ID']}")
        print(f"   EVENT_ID: {CONFIG['EVENT_ID']}")
        print(f"   ACCOUNT_ID: {CONFIG['ACCOUNT_ID']}")
        print(f"   USER_ID: {CONFIG['USER_ID']}")
        print(f"   INSURANCE_ID: {CONFIG['INSURANCE_ID']}")
        print(f"🔓 Modo de segurança: DESATIVADO (aceita qualquer host)")
        print("=" * 60)
        
        return app

# ============================================
# EXECUÇÃO
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    # Configuração ULTRA permissiva do Uvicorn
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000")),
        # Desativa TODAS as verificações de segurança
        proxy_headers=True,
        forwarded_allow_ips="*",
        # Configurações para evitar timeouts
        timeout_keep_alive=30,
        timeout_graceful_shutdown=10,
        # Logs detalhados para debug
        log_level="info",
        # Headers adicionais
        headers=[("Server", "Amigo-MCP-Server")]
    )
    
    # Sobrescreve qualquer configuração de allowed_hosts
    config.allowed_hosts = ["*"]
    
    server = uvicorn.Server(config)
    
    print(f"🌐 Servidor iniciando em: http://0.0.0.0:{config.port}")
    print(f"📡 Aguardando conexões...")
    print(f"⚠️  AVISO: Modo de desenvolvimento - verificação de hosts desativada")
    
    server.run()
else:
    # Para execução no Render/Gunicorn
    app = PermissiveUvicornConfig.create_app()
