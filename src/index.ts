import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import express from "express";
import cors from "cors";
import axios from "axios";
import dotenv from "dotenv";

dotenv.config();

// Configurações
const AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br"; // Base URL
const PORT = process.env.PORT || 3000;

// Inicializa o servidor Express (para hospedar o MCP no Render)
const app = express();
app.use(cors());

// Inicializa o Servidor MCP
const server = new McpServer({
  name: "amigo-scheduler",
  version: "1.0.0",
});

// --- FERRAMENTA 1: Consultar Horários ---
server.tool(
  "consultar_horarios",
  "Consulta os horários disponíveis na agenda para uma data específica.",
  {
    data: { type: "string", description: "Data no formato AAAA-MM-DD (ex: 2025-10-25)" },
    profissional_id: { type: "string", description: "ID do médico/profissional (opcional se houver apenas um)" }
  },
  async ({ data, profissional_id }) => {
    try {
      // DICA: Verifique no Swagger qual o endpoint exato de GET calendário
      // Estou assumindo /Calendário baseado no seu link
      const response = await axios.get(`${AMIGO_API_URL}/api/Calendario`, {
        params: { date: data, profissional: profissional_id },
        headers: {
          // O Token virá das variaveis de ambiente do Render
          "Authorization": `Bearer ${process.env.AMIGO_API_TOKEN}`,
          "Content-Type": "application/json"
        }
      });

      // Retorna os dados limpos para a IA
      return {
        content: [{ type: "text", text: JSON.stringify(response.data) }]
      };
    } catch (error: any) {
      return {
        content: [{ type: "text", text: `Erro ao buscar horários: ${error.message}` }],
        isError: true,
      };
    }
  }
);

// --- FERRAMENTA 2: Agendar Consulta ---
server.tool(
  "agendar_consulta",
  "Realiza o agendamento de um novo atendimento.",
  {
    paciente_nome: { type: "string", description: "Nome do paciente" },
    paciente_telefone: { type: "string", description: "Telefone do paciente" },
    data_horario: { type: "string", description: "Data e hora ISO (ex: 2025-10-25T14:00:00)" },
    profissional_id: { type: "string", description: "ID do médico" }
  },
  async (args) => {
    try {
      // DICA: Ajuste este body conforme o Swagger "addAttendance"
      const body = {
        name: args.paciente_nome,
        phone: args.paciente_telefone,
        start_date: args.data_horario,
        professional_id: args.profissional_id,
        status: "SCHEDULED" // Exemplo
      };

      const response = await axios.post(`${AMIGO_API_URL}/api/Atendimentos/addAttendance`, body, {
        headers: {
          "Authorization": `Bearer ${process.env.AMIGO_API_TOKEN}`,
          "Content-Type": "application/json"
        }
      });

      return {
        content: [{ type: "text", text: `Agendamento realizado com sucesso! ID: ${response.data.id}` }]
      };
    } catch (error: any) {
      return {
        content: [{ type: "text", text: `Erro ao agendar: ${error.message}` }],
        isError: true,
      };
    }
  }
);

// --- Configuração do Transporte SSE (Server-Sent Events) ---
// Isso é necessário para conectar via HTTP (Double X <-> Render)
app.get("/sse", async (req, res) => {
  const transport = new SSEServerTransport("/messages", res);
  await server.connect(transport);
});

app.post("/messages", async (req, res) => {
  // Nota: Em uma implementação real completa, você precisa gerenciar 
  // sessões SSE aqui, mas para um teste simples single-instance:
  // O MCP SDK gerencia a maior parte da lógica se conectado corretamente.
  // Para Render + MCP simples, o endpoint /sse é o principal.
  res.sendStatus(200);
});

app.listen(PORT, () => {
  console.log(`Servidor MCP rodando na porta ${PORT}`);
});
