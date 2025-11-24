# syntax=docker/dockerfile:1.7

### Builder ---------------------------------------------------------------
FROM node:20-alpine AS builder

# Vite reads env vars during build time. Provide overrides via build args.
ARG VITE_API_BASE_URL=/api
ARG VITE_WS_URL=ws://localhost:8001/ws

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_WS_URL=${VITE_WS_URL}

WORKDIR /app

COPY package*.json ./
RUN npm ci --include=dev

COPY . .
RUN npm run build

### Runtime ---------------------------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app

RUN npm install -g serve && adduser -D app && chown app /app

USER app

COPY --from=builder /app/dist ./dist

EXPOSE 3000

CMD ["npx", "serve", "-s", "dist", "-l", "3000"]
