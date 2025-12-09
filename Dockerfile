FROM node:18-slim

WORKDIR /app

# Copia os arquivos que criamos
COPY package.json .
COPY index.js .

# Instala as dependências
RUN npm install

# Expõe a porta
EXPOSE 8080

# Inicia o servidor
CMD ["npm", "start"]
