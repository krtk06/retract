# One image, two shapes.
#   * default (nginx) — the production bundle behind a static server.
#   * `dev` target    — the Vite dev server, used by docker-compose.yml so edits
#                       hot-reload instead of needing a rebuild.
# A dev server in the production image was the original bug here: `npm run dev`
# shipped unminified modules, HMR, and dev-only source maps.

FROM node:24-alpine AS deps

WORKDIR /srv/app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# --- production -------------------------------------------------------------
FROM deps AS build
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=build /srv/app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# GET rather than `wget --spider`: --spider sends HEAD, which is not answered
# uniformly across servers and silently reports a healthy container as unhealthy.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --output-document=/dev/null http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]

# --- development ------------------------------------------------------------
FROM deps AS dev

EXPOSE 5173

# VITE_API_PROXY / VITE_EVE_PROXY are read by vite.config.ts at startup.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
