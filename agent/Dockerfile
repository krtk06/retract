# eve requires Node >= 24.
FROM node:24-alpine

WORKDIR /srv/agent

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build once so `eve start` serves the compiled Nitro output.
#
# KNOWN LIMITATION: eve compiles the agent definition — including the *resolved model* —
# into .output/.eve/compile/compiled-agent-manifest.json at build time, so in this image
# AI_INTEL_LLM_PROVIDER, AI_INTEL_MODEL and the NODE_ENV fixture-model guard are resolved
# from the *build* environment and ignored at run time. Verified: a container started with
# AI_INTEL_LLM_PROVIDER=openai and a valid AI_INTEL_API_KEY still called the AI Gateway,
# and the manifest contained no occurrence of "openai". Note the corollary — a provider
# needing a key (openai) would have that key baked into the manifest, so it must never be
# built with one. Build args are the supported way to select the provider; see
# implementation.md for the options and the reason this is not simply moved to start-up.
RUN npm run build

# Run unprivileged. /srv/agent is owned by root so the image contents cannot be
# edited by the running process; the workflow state directory is the one place it
# must write, and it is created up front and chowned.
RUN addgroup -S eve && adduser -S -G eve -h /home/eve eve \
    && mkdir -p /srv/agent/.eve/.workflow-data \
    && chown -R eve:eve /srv/agent/.eve

USER eve

ENV HOME=/home/eve \
    PORT=3000 \
    NODE_ENV=production

EXPOSE 3000

# Liveness probe. Routes tested against a real container:
#   /eve/v1/health -> 200, unauthenticated. This is the route to use: eve keeps it
#                     outside the channel's auth walk.
#   /eve/v1/info   -> 401 once AI_INTEL_JWT_SECRET is set, so it cannot be probed
#                     blindly. (It only looked public in development, where no
#                     secret is set and `none()` admits every caller.)
#   /health        -> 404; /eve/health -> 404. eve does not serve either, despite
#                     its docs implying a health route.
# A plain GET is used rather than `wget --spider`, which sends HEAD and reports a
# healthy server as failed.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD wget --quiet --tries=1 --output-document=/dev/null http://127.0.0.1:3000/eve/v1/health || exit 1

CMD ["npm", "run", "start"]
