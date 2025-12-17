# main.py
import os
import uvicorn
from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

# 1. Configuração de Ambiente
# Em produção (Render), ALLOWED_HOSTS deve ser o domínio real (ex: app.onrender.com)
# O uso de '*' é aceitável APENAS se houver autenticação na camada de aplicação.
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# 2. Definição do Servidor FastMCP
mcp = FastMCP("Servidor-Producao")

@mcp.tool()
def ferramenta_exemplo(texto: str) -> str:
    return f"Processado: {texto}"

# 3. Definição da Pilha de Middleware
# A ordem é crítica. O TrustedHostMiddleware deve validar o cabeçalho Host
# antes que qualquer processamento pesado ocorra.
middleware_stack =,  # Necessário para clientes web (Cursor/Claude)
        allow_methods=["*"],
        allow_headers=["*"],
    ),
    Middleware(
        TrustedHostMiddleware,
        allowed_hosts=ALLOWED_HOSTS 
    )
]

# 4. Geração da Aplicação ASGI (Inversão de Controle)
# Ao passar 'middleware' aqui, instruímos o FastMCP a configurar a aplicação
# com nossas regras de segurança, substituindo padrões restritivos.
app = mcp.http_app(middleware=middleware_stack)

# 5. Ponto de Entrada de Execução
if __name__ == "__main__":
    # O Render injeta a porta na variável de ambiente PORT
    port = int(os.getenv("PORT", 8000))
    
    # Execução do Uvicorn com Configuração de Proxy
    # proxy_headers=True: Instrui o Uvicorn a confiar nos cabeçalhos X-Forwarded-*
    # forwarded_allow_ips="*": Confia no balanceador de carga do Render
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
