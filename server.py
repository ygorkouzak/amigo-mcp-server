import os
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# 1. Definição do Servidor
mcp = FastMCP("AmigoMCP")

# 2. Definição do Middleware de Autenticação
class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # A. PERMITIR HEALTH CHECK (Crucial para o Render não matar o app)
        # O Render geralmente faz GET no path configurado. 
        # Se seu health check path for /sse ou /health, libere-o aqui.
        if request.url.path in ["/sse", "/health", "/"]:
            return await call_next(request)

        # B. VERIFICAR TOKEN
        # O cliente deve enviar o header: "Authorization: Bearer SEU_TOKEN_AQUI"
        auth_header = request.headers.get("Authorization")
        expected_token = os.getenv("MCP_AUTH_TOKEN")
        
        # Se não houver token configurado no servidor, bloqueia por segurança (fail-closed)
        if not expected_token:
            return JSONResponse(
                status_code=500, 
                content={"error": "Erro de configuração: MCP_AUTH_TOKEN não definido no servidor"}
            )

        # Verifica formato "Bearer <token>" ou apenas o token direto
        token_received = auth_header.replace("Bearer ", "") if auth_header else ""

        if token_received != expected_token:
            return JSONResponse(
                status_code=403, 
                content={"error": "Acesso negado: Token inválido ou ausente"}
            )

        # C. Se passou, processa a requisição
        return await call_next(request)

# 3. Adicionar o Middleware ao app
# O FastMCP geralmente expõe o app subjacente (Starlette/FastAPI) ou permite adicionar middleware.
# Se 'mcp' for a instância da aplicação ASGI direta:
mcp.add_middleware(SecurityMiddleware)

# --- SUAS FERRAMENTAS ---

@mcp.tool()
def agendar_compromisso(data: str, descricao: str) -> str:
    """Agenda um compromisso no sistema Amigo."""
    # Sua lógica de conexão com a API do Amigo aqui
    return f"Compromisso agendado para {data}: {descricao}"

@mcp.tool()
def status_sistema() -> str:
    """Verifica se o sistema está online."""
    return "Sistema Amigo Operacional"

# --- EXECUÇÃO ---

# Garante que o uvicorn (Docker) controle a execução, e o run() manual seja ignorado
if __name__ == "__main__":
    mcp.run()
