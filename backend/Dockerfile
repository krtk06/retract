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

RUN pip install ".[embeddings]"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
