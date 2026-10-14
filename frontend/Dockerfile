# syntax=docker/dockerfile:1.7
#
# Stage 1 compiles the React app with Node; stage 2 serves the static files from an
# unprivileged nginx. Node, npm and node_modules never reach the runtime image.

# ---------------------------------------------------------------- build
FROM node:25-alpine AS build

WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src

# Shown in the sidebar so anyone can tell which commit is deployed.
ARG APP_VERSION=dev
ENV VITE_APP_VERSION=${APP_VERSION}
RUN npm run build

# ---------------------------------------------------------------- runtime
FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime

ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="shelfwise-frontend" \
      org.opencontainers.image.description="Shelfwise library desk UI (React, served by nginx)" \
      org.opencontainers.image.source="https://github.com/Aanviiii/DevOps-project" \
      org.opencontainers.image.version="${APP_VERSION}"

# Where /api/ is proxied to. Overridden per environment.
ENV SHELFWISE_API_UPSTREAM=http://backend:8000 \
    NGINX_ENVSUBST_FILTER=^SHELFWISE_

USER root
# Patch the base image's OS packages so known fixes land even between nginx releases,
# and drop the stock site config in favour of ours.
RUN apk upgrade --no-cache && rm -f /etc/nginx/conf.d/default.conf
USER 101

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build --chown=101:101 /src/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
