# Frontend image: Next.js (App Router) production server.
FROM node:20-slim

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# Install dependencies against the lockfile first (better layer caching).
# .npmrc carries legacy-peer-deps (React 19 + Base UI peer ranges) — copy it before
# npm ci so the install resolves the same way it does locally.
COPY package.json package-lock.json .npmrc ./
RUN npm ci

COPY . .

# AUTH_SECRET is needed at build only as a placeholder; the real one is injected at
# runtime via the environment (and must match the backend's AUTH_SECRET — ADR-0009).
ENV AUTH_SECRET=build-time-placeholder-not-used-at-runtime
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
