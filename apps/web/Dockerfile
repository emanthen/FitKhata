# syntax=docker/dockerfile:1
FROM node:20-slim AS base
RUN corepack enable
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-lock.yaml* ../../pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile || pnpm install

# Dev stage: source bind-mounted by docker-compose.dev.yml for hot reload.
FROM base AS dev
COPY . .
RUN pnpm install
RUN useradd -m appuser && chown -R appuser /app
USER appuser
EXPOSE 3000
CMD ["pnpm", "dev"]

# Build stage: produces the Next.js standalone output.
FROM deps AS builder
COPY . .
RUN pnpm build

# Runtime stage: standalone server, non-root.
FROM base AS runtime
RUN useradd -m appuser
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
USER appuser
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
