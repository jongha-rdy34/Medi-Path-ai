# Development image for the core profile: serves the Vite dev server.
# A production build (static files behind Caddy) is set up in T31.
FROM node:22.23.4-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
