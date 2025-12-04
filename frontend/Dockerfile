# ------------------------------------------------------------
# base: dependencies only
# ------------------------------------------------------------
FROM node:24-alpine AS frontend_base
WORKDIR /frontend

COPY package*.json ./
RUN npm ci


# ------------------------------------------------------------
# dev stage (vite dev server)
# ------------------------------------------------------------
FROM frontend_base AS frontend_dev
ARG VITE_SERVER_PORT=3000

COPY . .
EXPOSE $VITE_SERVER_PORT
CMD ["npm", "run", "dev"]

# ------------------------------------------------------------
# test stage
# ------------------------------------------------------------
FROM frontend_base AS test
COPY . .
CMD ["npm", "test"]

# ------------------------------------------------------------
# build stage (used by prod)
# ------------------------------------------------------------
FROM frontend_base AS frontend_build
ENV NODE_ENV=production
COPY . .
RUN npm run build

# ------------------------------------------------------------
# prod stage (static build only, no server)
# ------------------------------------------------------------
FROM alpine:3 AS frontend_prod
LABEL authors="Andrei Olar <andrei.olar@ubbcluj.ro"
WORKDIR /opt/twin4dem/frontend

# copy build artifacts only
COPY --from=frontend_build /frontend/dist .

# allow shell usage (for integrating into backend image)
ENTRYPOINT ["/bin/sh"]

