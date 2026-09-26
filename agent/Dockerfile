# eve requires Node >= 24.
FROM node:24-alpine

WORKDIR /srv/agent

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build once so `eve start` serves the compiled Nitro output.
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

# /eve/v1/info is the framework's agent-info route: public (outside the auth
# walk), ~6ms, and it only answers once the runtime is serving. Two traps avoided
# here, both verified against a running `eve start`:
#   * `/health` is NOT exposed by eve 0.66 in `eve start` (returns 404).
#   * `wget --spider` sends HEAD, which this route does not answer (404); a plain
#     GET is required, or a healthy container is reported unhealthy.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD wget --quiet --tries=1 --output-document=/dev/null http://127.0.0.1:3000/eve/v1/info || exit 1

CMD ["npm", "run", "start"]
