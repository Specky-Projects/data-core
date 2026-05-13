# ─────────────────────────────────────────────
# Stage 1 — builder
# ─────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Instala dependências nativas (bcrypt, canvas, etc.)
RUN apk add --no-cache python3 make g++

# Copia apenas os manifestos primeiro (layer caching)
COPY package*.json ./
COPY prisma ./prisma/

RUN npm ci --ignore-scripts

# Gera o Prisma Client antes de compilar
RUN npx prisma generate

# Copia o restante do código-fonte
COPY . .

# Compila TypeScript → dist/
RUN npm run build

# Remove devDependencies para reduzir a imagem final
RUN npm prune --production

# ─────────────────────────────────────────────
# Stage 2 — runtime
# ─────────────────────────────────────────────
FROM node:20-alpine AS runtime

WORKDIR /app

# Usuário não-root por segurança
RUN addgroup -S app && adduser -S app -G app

# Copia apenas o necessário do builder
COPY --from=builder /app/dist            ./dist
COPY --from=builder /app/node_modules    ./node_modules
COPY --from=builder /app/prisma          ./prisma
COPY --from=builder /app/package.json    ./package.json

# Aplica migrações e inicia o servidor
# (migração é executada no entrypoint para garantir idempotência)
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh && chown -R app:app /app

USER app

EXPOSE 3001

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["node", "dist/main"]
