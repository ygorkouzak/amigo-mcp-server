import os
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from dotenv import load_dotenv

# --- IMPORTS PARA CORREÇÃO DO ERRO DE HOST ---
import mcp.server.sse

# --- CORREÇÃO (MONKEY PATCH) ---
# A biblioteca MCP bloqueia hosts externos por segurança. 
# Esse patch força a aceitação do domínio do Render.
original_connect_sse = mcp.server.sse.connect_sse

async def patched_connect_sse(scope, receive, send, permitted_origins=None):
    # Lista de domínios permitidos (Render + Localhost)
    allowed_hosts = [
        "amigo-mcp-server.onrender.com", 
        "localhost", 
        "127.0.0.1"
    ]
    # Chama a função original forçando nossos hosts permitidos
    return await original_connect_sse(scope, receive, send, permitted_origins=allowed_hosts)

# Aplica a correção na biblioteca
mcp.server.sse.connect_sse = patched_connect_sse
# ---------------------------------------------

# Carrega variáveis
load_dotenv()

# --- CONFIGURAÇÕES ---
AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"
# ... (restante do código permanece IGUAL) ...
