# ─────────────────────────────────────────────────────────────────
# Worker Dockerfile
# Build context: raiz do monorepo
#
# Estratégia de paths:
#   O worker importa de '../../backend/src/...' (TypeScript).
#   Após compilação, o JS emitido faz require("../../backend/src/...").
#   No container final, copiamos o backend compilado para /app/backend/src/
#   para que o require() resolve corretamente sem ts-node.
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────
# Stage 1 — compilar backend
# ─────────────────────────────────────────────
FROM node:20-alpine AS backend-builder

WORKDIR /build/backend

RUN apk add --no-cache python3 make g++

COPY systems/backend/package*.json ./
COPY systems/backend/prisma ./prisma/

RUN npm ci --ignore-scripts
RUN npx prisma generate

COPY systems/backend/src              ./src
COPY systems/backend/tsconfig*.json   ./
COPY systems/backend/nest-cli.json    ./

# Compila backend → dist/  (com declaration: true → gera também .d.ts)
RUN npm run build

# ─────────────────────────────────────────────
# Stage 2 — compilar worker
# ─────────────────────────────────────────────
FROM node:20-alpine AS worker-builder

WORKDIR /build/worker

RUN apk add --no-cache python3 make g++

COPY systems/worker/package*.json ./
RUN npm ci --ignore-scripts

COPY systems/worker/src          ./src
COPY systems/worker/tsconfig.json ./

# O tsc precisa dos arquivos .ts do backend para resolver tipos
COPY --from=backend-builder /build/backend/src         ../../backend/src
COPY --from=backend-builder /build/backend/node_modules ../../backend/node_modules
COPY --from=backend-builder /build/backend/prisma      ../../backend/prisma

# Compila worker
RUN npx tsc -p tsconfig.json

RUN npm prune --production

# ─────────────────────────────────────────────
# Stage 3 — runtime
# ─────────────────────────────────────────────
FROM node:20-alpine AS runtime

# Estrutura que replica o layout relativo esperado pelo worker:
#   /app/worker/dist/worker.module.js
#   require("../../backend/src/prisma/prisma.module") → /app/backend/src/prisma/prisma.module.js
#
# Então: worker rodará de /app/worker/, com /app/backend/src/ contendo o JS do backend.

RUN addgroup -S app && adduser -S app -G app

# Worker
COPY --from=worker-builder /build/worker/dist         /app/worker/dist
COPY --from=worker-builder /build/worker/node_modules /app/worker/node_modules
COPY --from=worker-builder /build/worker/package.json /app/worker/package.json

# Backend JS copiado para /app/backend/src/ — resolve require("../../backend/src/...")
# Nota: dist/ do backend contém os .js compilados; copiamos para src/ no container
COPY --from=backend-builder /build/backend/dist         /app/backend/src
COPY --from=backend-builder /build/backend/node_modules /app/backend/node_modules
COPY --from=backend-builder /build/backend/prisma       /app/backend/prisma

RUN chown -R app:app /app
USER app

WORKDIR /app/worker

CMD ["node", "dist/main.js"]
