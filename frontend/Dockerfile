FROM node:20-slim AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# DEMO-MOCKED: hardcoded per-role login creds baked in at build time (Vite
# only exposes VITE_-prefixed vars at build time, not runtime) — see
# src/store/auth.ts and root .env.example.
ARG VITE_PATIENT_USERNAME
ARG VITE_PATIENT_PASSWORD
ARG VITE_REVIEWER_USERNAME
ARG VITE_REVIEWER_PASSWORD
ARG VITE_ADMIN_USERNAME
ARG VITE_ADMIN_PASSWORD
# Shared secret sent as X-API-Key on every backend request — see
# src/store/api.ts and backend/app/core/auth.py.
ARG VITE_API_KEY
ENV VITE_PATIENT_USERNAME=$VITE_PATIENT_USERNAME \
    VITE_PATIENT_PASSWORD=$VITE_PATIENT_PASSWORD \
    VITE_REVIEWER_USERNAME=$VITE_REVIEWER_USERNAME \
    VITE_REVIEWER_PASSWORD=$VITE_REVIEWER_PASSWORD \
    VITE_ADMIN_USERNAME=$VITE_ADMIN_USERNAME \
    VITE_ADMIN_PASSWORD=$VITE_ADMIN_PASSWORD \
    VITE_API_KEY=$VITE_API_KEY

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=5s --timeout=5s --retries=10 \
    CMD wget -q -O /dev/null http://localhost:80 || exit 1
