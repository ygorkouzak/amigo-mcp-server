import express from 'express';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import SwaggerParser from 'swagger-parser';
import axios from 'axios';

const app = express();
const PORT = process.env.PORT || 8080;

// Configurações do Render
const OPENAPI_URL = process.env.OPENAPI_SPEC_URL;
const API_URL = process.env.API_URL; 
const API_KEY = process.env.API_KEY;

// Cria o servidor MCP
const server = new McpServer({
  name: "AmigoBot MCP",
  version: "1.0.0"
});

async function startServer() {
  try {
    if (!OPENAPI_URL) throw new Error("Faltou a variável OPENAPI_SPEC_URL no Render");

    console.log(`Lendo manual da API em: ${OPENAPI_URL}`);
    // Lê o Swagger (JSON)
    const apiSpec = await SwaggerParser.validate(OPENAPI_URL);
    
    // Cria as ferramentas automaticamente
    for (const [path, methods] of Object.entries(apiSpec.paths)) {
      for (const [method, operation] of Object.entries(methods)) {
        // Gera um nome simples para a ferramenta (ex: get_patients)
        const toolName = (operation.operationId || `${method}_${path}`)
          .replace(/[^a-zA-Z0-9_]/g, '_')
          .substring(0, 60);

        server.tool(toolName, operation.summary || "Sem descrição", {}, async (args) => {
          try {
            // Usa a URL real que você achou na imagem (image_919260.png)
            const baseUrl = API_URL || "https://grn-amigobot-api.amigoapp.com.br";
            const finalUrl = `${baseUrl}${path}`;
            
            console.log(`Executando: ${method.toUpperCase()} ${finalUrl}`);
            
            const response = await axios({
              method,
              url: finalUrl,
              headers: { 
                'Authorization': API_KEY, // Usa a chave que vamos corrigir
                'Content-Type': 'application/json'
              },
              params: method === 'get' ? args : undefined,
              data: method !== 'get' ? args : undefined
            });
            
            return { content: [{ type: "text", text: JSON.stringify(response.data) }] };
          } catch (error) {
            return { content: [{ type: "text", text: `Erro: ${error.message}` }], isError: true };
          }
        });
      }
    }

    // Rotas para o Double X conectar
    app.get('/sse', async (req, res) => {
      console.log("Double X conectou!");
      const transport = new SSEServerTransport('/messages', res);
      await server.connect(transport);
    });

    app.post('/messages', async (req, res) => {
      await server.handlePostMessage(req, res);
    });

    app.listen(PORT, () => {
      console.log(`✅ Servidor ONLINE na porta ${PORT}`);
    });

  } catch (err) {
    console.error("❌ Falha ao iniciar:", err);
  }
}

startServer();
