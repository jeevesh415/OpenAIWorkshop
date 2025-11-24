# syntax=docker/dockerfile:1.7

### Builder image ---------------------------------------------------------
FROM node:20-alpine AS builder

# Copy source and build. Vite reads env vars at build time, so expose them as args.
ARG VITE_BACKEND_URL=http://localhost:7000
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}

WORKDIR /app

# Install dependencies (locked)
COPY package*.json ./
RUN npm ci --include=dev

COPY . .
RUN npm run build

### Runtime image ---------------------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app

RUN npm install -g serve && adduser -D app && chown app /app

USER app

COPY --from=builder /app/dist ./dist

EXPOSE 3000

CMD ["npx", "serve", "-s", "dist", "-l", "3000"]
