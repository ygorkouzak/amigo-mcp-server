// IMPORTANTE: Sem .js no final para respeitar o 'exports' da biblioteca
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse";
import express from "express";
import cors from "cors";
import axios from "axios";
import dotenv from "dotenv";

dotenv.config();

// --- CONFIGURAÇÕES ---
const PORT = process.env.PORT || 3000;
const AMIGO_API_URL = "https://amigobot-api.amigoapp.com.br";
const API_TOKEN = process.env.AMIGO_API_TOKEN;

// IDs DA CLÍNICA
const CONFIG = {
  PLACE_ID: Number(process.env.PLACE_ID),
  EVENT_ID: Number(process.env.EVENT_ID),
  ACCOUNT_ID: Number(process.env.ACCOUNT_ID),
  USER_ID: Number(process.env.USER_ID),
  INSURANCE_ID: Number(process.env.INSURANCE_ID) || 1
};

const app = express();
app.use(cors());

// --- SERVIDOR MCP ---
const server = new McpServer({
  name: "amigo-scheduler",
  version: "1.0.0",
});

// --- FERRAMENTA 1: BUSCAR PACIENTE ---
server.tool(
  "buscar_paciente",
  "Busca um paciente pelo nome ou CPF para encontrar seu ID interno.",
  {
    nome: { type: "string", description: "Nome do paciente" },
    cpf: { type: "string", description: "CPF do paciente (opcional)" }
  },
  async ({ nome, cpf }) => {
    try {
      console.log(`Buscando paciente: ${nome || cpf}`);
      const response = await axios.get(`${AMIGO_API_URL}/patients`, {
        params: { name: nome, cpf: cpf },
        headers: { "Authorization": `Bearer ${API_TOKEN}` }
      });

      const resultados = response.data.map((p: any) => ({
        id: p.id,
        nome: p.name,
        telefone: p.contact_cellphone || p.cellphone,
        nascimento: p.born
      }));

      return {
        content: [{ type: "text", text: JSON.stringify(resultados) }]
      };
    } catch (error: any) {
      return {
        content: [{ type: "text", text: `Erro ao buscar: ${JSON.stringify(error.response?.data || error.message)}` }],
        isError: true,
      };
    }
  }
);

// --- FERRAMENTA 2: CONSULTAR HORÁRIOS ---
server.tool(
  "consultar_horarios",
  "Consulta horários disponíveis na agenda.",
  {
    data: { type: "string", description: "Data no formato YYYY-MM-DD" }
  },
  async ({ data }) => {
    try {
      const response = await axios.get(`${AMIGO_API_URL}/calendar`, {
        params: {
          date: data,
          event_id: CONFIG.EVENT_ID,
          place_id: CONFIG.PLACE_ID,
          insurance_id: CONFIG.INSURANCE_ID
        },
        headers: { "Authorization": `Bearer ${API_TOKEN}` }
      });

      return {
        content: [{ type: "text", text: JSON.stringify(response.data) }]
      };
    } catch (error: any) {
      return {
        content: [{ type: "text", text: `Erro ao ver agenda: ${JSON.stringify(error.response?.data || error.message)}` }],
        isError: true,
      };
    }
  }
);

// --- FERRAMENTA 3: AGENDAR CONSULTA ---
server.tool(
  "agendar_consulta",
  "Realiza o agendamento final.",
  {
    start_date: { type: "string", description: "Data e hora exata: 'YYYY-MM-DD HH:mm'" },
    patient_id: { type: "string", description: "ID numérico do paciente" },
    telefone: { type: "string", description: "Telefone apenas números" }
  },
  async (args) => {
    try {
      const body = {
        insurance_id: CONFIG.INSURANCE_ID,
        event_id: CONFIG.EVENT_ID,
        user_id: CONFIG.USER_ID,
        place_id: CONFIG.PLACE_ID,
        start_date: args.start_date,
        patient_id: Number(args.patient_id),
        account_id: CONFIG.ACCOUNT_ID,
        chat_id: "whatsapp_integration",
        scheduler_phone_dial_code: "55",
        scheduler_phone: args.telefone || "000000000",
        is_dependent_schedule: false
      };

      console.log("Agendando...", body);

      const response = await axios.post(`${AMIGO_API_URL}/attendances`, body, {
        headers: { "Authorization": `Bearer ${API_TOKEN}` }
      });

      return {
        content: [{ type: "text", text: `Sucesso! ID: ${JSON.stringify(response.data.id || response.data)}` }]
      };
    } catch (error: any) {
      return {
        content: [{ type: "text", text: `Erro ao agendar: ${JSON.stringify(error.response?.data || error.message)}` }],
        isError: true,
      };
    }
  }
);

// --- ROTAS ---
app.get("/health", (req, res) => { res.send("Running OK"); });

app.get("/sse", async (req, res) => {
  console.log("Conexão SSE iniciada");
  const transport = new SSEServerTransport("/messages", res);
  await server.connect(transport);
});

app.post("/messages", async (req, res) => { res.sendStatus(200); });

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
