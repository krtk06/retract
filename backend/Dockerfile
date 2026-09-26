FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ARG GITLEAKS_VERSION=8.28.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl tar \
    && curl -sL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
        | tar xz -C /usr/local/bin gitleaks \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/app

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install .

# Run unprivileged. /srv/app stays root-owned and read-only to the service; the
# only writable path is the checkout/data directory the analysis pipeline uses,
# which is a mounted volume in compose.
RUN addgroup -S intel && adduser -S -G intel -h /home/intel intel \
    && mkdir -p /data \
    && chown intel:intel /data

USER intel

ENV AI_INTEL_DATA_DIR=/data

EXPOSE 8000

# A plain GET, not `wget --spider`: spider sends HEAD and the health route only
# answers GET, which would report a healthy container as unhealthy.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
