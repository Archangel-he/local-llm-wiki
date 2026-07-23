FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/ .
RUN npm install && npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /build/dist /usr/share/caddy
EXPOSE 8000
