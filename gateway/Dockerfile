FROM node:22-alpine AS frontend-build
WORKDIR /build

RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ .
RUN pnpm build

FROM caddy:2-alpine
COPY gateway/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /build/dist /usr/share/caddy
EXPOSE 8000
