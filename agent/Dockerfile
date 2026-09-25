FROM node:24-alpine

WORKDIR /srv/agent

# eve requires Node >= 24.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build once so `eve start` serves the compiled Nitro output.
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
