import os
from fastmcp import FastMCP

# Criação do servidor com configurações explícitas
mcp = FastMCP(
    "MeuServidorRender",
    description="Servidor MCP otimizado para nuvem",
    # settings é um dicionário que passa kwargs para a configuração do servidor
    settings={
        "host": "0.0.0.0",
        "port": int(os.environ.get("PORT", 8000)),
        "allowed_hosts": ["*"]  # Instrução direta para o middleware
    }
)

@mcp.tool()
def verificar_status() -> str:
    """Ferramenta simples para verificar a saúde do servidor."""
    return "Servidor Operacional no Render"

# Ponto de entrada condicional
if __name__ == "__main__":
    # O transporte SSE é obrigatório para compatibilidade web
    # Captura a porta do ambiente (Render injeta PORT)
    port = int(os.environ.get("PORT", 8000))
    
    # Execução manual
    mcp.run(transport="sse", host="0.0.0.0", port=port)
