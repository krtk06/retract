# One image, two shapes.
#   * `runtime` — the production bundle behind nginx. This is the LAST stage on
#                 purpose: `docker build` with no --target builds the final stage,
#                 so making it last means an unqualified build cannot silently
#                 produce a dev server.
#   * `dev`     — the Vite dev server, used by docker-compose.yml so edits
#                 hot-reload instead of needing a rebuild.
#
# A dev server in the production image was the original bug here: `npm run dev`
# shipped unminified modules, HMR, and dev-only source maps. It bit again when
# `dev` was the last stage: docker-compose.prod.yml built without a `target`, got
# the dev server, and published host :80 to a container serving :5173 — so every
# request to the published port was refused. Both layers now guard it: `runtime`
# is last here, and the prod compose names `target: runtime` explicitly.

FROM node:24-alpine AS deps

WORKDIR /srv/app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

FROM deps AS build
RUN npm run build

# --- development -------------------------------------------------------------
FROM deps AS dev

EXPOSE 5173

# VITE_API_PROXY / VITE_EVE_PROXY are read by vite.config.ts at startup.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# --- production --------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY --from=build /srv/app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# GET rather than `wget --spider`: --spider sends HEAD, which is not answered
# uniformly across servers and silently reports a healthy container as unhealthy.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --output-document=/dev/null http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]