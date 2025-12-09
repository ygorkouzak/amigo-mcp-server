import express from 'express';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import SwaggerParser from 'swagger-parser';
import axios from 'axios';

const app = express();
const PORT = process.env.PORT || 8080;

// Configurações vindas do Render
const OPENAPI_URL = process.env.OPENAPI_SPEC_URL;
const API_URL = process.env.API_URL; 
const API_KEY = process.env.API_KEY;

if (!OPENAPI_URL) {
  console.error("ERRO: Faltou configurar a variavel OPENAPI_SPEC_URL no Render.");
  process.exit(1);
}

// Cria o servidor MCP
const server = new McpServer({
  name: "AmigoBot MCP",
  version: "1.0.0"
});

async function startServer() {
  try {
    console.log(`Lendo Swagger de: ${OPENAPI_URL}`);
    const apiSpec = await SwaggerParser.validate(OPENAPI_URL);
    
    // Varre o Swagger e cria ferramentas para a IA
    for (const [path, methods] of Object.entries(apiSpec.paths)) {
      for (const [method, operation] of Object.entries(methods)) {
        const toolName = operation.operationId || `${method}_${path.replace(/\//g, '_')}`;
        const description = operation.summary || operation.description || "Sem descrição";

        server.tool(toolName, description, {}, async (args) => {
          try {
            // Monta a requisição real para o Amigo
            const url = `${API_URL || apiSpec.servers?.[0]?.url}${path}`;
            console.log(`Chamando API: ${method.toUpperCase()} ${url}`);
            
            const response = await axios({
              method,
              url,
              headers: { 
                'Authorization': API_KEY,
                'Content-Type': 'application/json'
              },
              params: method === 'get' ? args : undefined,
              data: method !== 'get' ? args : undefined
            });
            
            return { content: [{ type: "text", text: JSON.stringify(response.data) }] };
          } catch (error) {
            return { content: [{ type: "text", text: `Erro na API: ${error.message}` }], isError: true };
          }
        });
      }
    }

    console.log(`Ferramentas criadas! Iniciando servidor HTTP...`);

    // Configura rota SSE para o Double X conectar
    app.get('/sse', async (req, res) => {
      console.log("Nova conexão MCP recebida!");
      const transport = new SSEServerTransport('/messages', res);
      await server.connect(transport);
    });

    app.post('/messages', async (req, res) => {
      await server.handlePostMessage(req, res);
    });

    app.listen(PORT, () => {
      console.log(`Servidor MCP rodando na porta ${PORT}`);
      console.log(`URL para o Double X: https://SEU-APP.onrender.com/sse`);
    });

  } catch (err) {
    console.error("Erro ao iniciar:", err);
  }
}

startServer();
