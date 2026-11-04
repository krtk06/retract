# eve requires Node >= 24.
FROM node:24-alpine

WORKDIR /srv/agent

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build once so `eve start` serves the compiled Nitro output.
#
# eve compiles the resolved model and routing into
# .output/.eve/compile/compiled-agent-manifest.json, and also bundles the module that
# re-resolves process.env at request time. Both are driven by the build environment, so
# the provider, model, base URL, API mode, and non-secret headers are build args.
# Changing them requires rebuilding this image; the runtime container must be started
# with the same values or the manifest and the live model disagree.
#
# The credential is deliberately NOT a build arg. `agent.ts` resolves it at build time
# (the module is imported then) but eve does not embed it in the output; verified by
# grepping .output for the build key. A non-secret placeholder satisfies the build-time
# check, and the runtime environment supplies the real key. `scripts/verify-agent-build.sh`
# fails if a credential ever does appear in the compiled output.
ARG RETRACT_LLM_PROVIDER=gateway
ARG RETRACT_MODEL=anthropic/claude-sonnet-4.5
ARG RETRACT_LLM_BASE_URL=
ARG RETRACT_LLM_API_MODE=chat
# Only non-secret headers belong here. If a header contains a credential, add a lazy
# fetch wrapper instead; build args are visible in image history.
ARG RETRACT_LLM_HEADERS=
ARG RETRACT_BUILD_API_KEY=build-time-placeholder-not-a-credential
# Per-session caps. eve compiles the agent definition, so these are build inputs;
# the running container receives the same values from compose.
ARG RETRACT_AGENT_MAX_INPUT_TOKENS=200000
ARG RETRACT_AGENT_MAX_OUTPUT_TOKENS=50000
ARG RETRACT_AGENT_MAX_COST_USD=0.50

RUN RETRACT_LLM_PROVIDER="${RETRACT_LLM_PROVIDER}" \
    RETRACT_MODEL="${RETRACT_MODEL}" \
    RETRACT_LLM_BASE_URL="${RETRACT_LLM_BASE_URL}" \
    RETRACT_LLM_API_MODE="${RETRACT_LLM_API_MODE}" \
    RETRACT_LLM_HEADERS="${RETRACT_LLM_HEADERS}" \
    RETRACT_LLM_API_KEY="${RETRACT_BUILD_API_KEY}" \
    RETRACT_AGENT_MAX_INPUT_TOKENS="${RETRACT_AGENT_MAX_INPUT_TOKENS}" \
    RETRACT_AGENT_MAX_OUTPUT_TOKENS="${RETRACT_AGENT_MAX_OUTPUT_TOKENS}" \
    RETRACT_AGENT_MAX_COST_USD="${RETRACT_AGENT_MAX_COST_USD}" \
    npm run build

# The placeholder must not survive into the image either. The real key is runtime-only,
# but a failed guard here means the compile step serialized a credential-shaped value,
# which is the failure mode scripts/verify-agent-build.sh exists to catch.
RUN if grep -rqF "${RETRACT_BUILD_API_KEY}" .output; then \
      echo "build credential leaked into .output; refusing to ship the image" >&2; \
      exit 1; \
    fi

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
#   /eve/v1/info   -> 401 once RETRACT_JWT_SECRET is set, so it cannot be probed
#                     blindly. (It only looked public in development, where no
#                     secret is set and `none()` admits every caller.)
#   /health        -> 404; /eve/health -> 404. eve does not serve either, despite
#                     its docs implying a health route.
# A plain GET is used rather than `wget --spider`, which sends HEAD and reports a
# healthy server as failed.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD wget --quiet --tries=1 --output-document=/dev/null http://127.0.0.1:3000/eve/v1/health || exit 1

CMD ["npm", "run", "start"]
