# --- Estágio 1: Builder ---
FROM python:3.11-slim-bookworm AS builder

# Instala o uv copiando o binário oficial (Best Practice)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copia arquivos de definição de dependência
COPY pyproject.toml uv.lock ./

# Instala dependências no ambiente do sistema (sem venv para simplicidade no container)
RUN uv pip install --system --no-cache -r pyproject.toml

# --- Estágio 2: Final (Runtime) ---
FROM python:3.11-slim-bookworm

WORKDIR /app

# Copia pacotes instalados e binários do estágio anterior
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copia o código da aplicação
COPY . .

# Variáveis de Ambiente Críticas (Default values)
ENV PYTHONUNBUFFERED=1
ENV MCP_ALLOWED_HOSTS="*"
ENV FASTMCP_HOST="0.0.0.0"
# O Render injeta a PORT automaticamente, mas definimos 8080 como fallback
ENV PORT=8080

# Comando de Execução:
# Usa a variável de ambiente PORT do shell ($PORT) para o bind correto
CMD uvicorn server:mcp --host 0.0.0.0 --port $PORT --workers 1
