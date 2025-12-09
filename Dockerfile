# Usa a imagem pronta da comunidade
FROM ghcr.io/ckanthony/openapi-mcp:latest

# Define a porta padrão
ENV PORT=8080

# Expõe a porta para o Render
EXPOSE 8080
