FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ARG GITLEAKS_VERSION=8.28.0
# Checksums from the release's gitleaks_<version>_checksums.txt. Pinned here so a
# compromised release page cannot substitute a different binary for the one this
# image installs.
ARG GITLEAKS_SHA256_X64=a65b5253807a68ac0cafa4414031fd740aeb55f54fb7e55f386acb52e6a840eb
ARG GITLEAKS_SHA256_ARM64=eff65261156100e5d94a6b3dec313d532fddfe19ae1590bf7a2b4f2699128356

# The Oracle free tier is arm64, and the old image unconditionally downloaded the
# x64 tarball, so the build succeeded nowhere the target actually was. Select the
# asset from TARGETARCH (set by BuildKit) and verify it before extraction.
ARG TARGETARCH
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates git curl tar; \
    case "${TARGETARCH:-amd64}" in \
      amd64) gitleaks_arch=x64; gitleaks_sha=${GITLEAKS_SHA256_X64} ;; \
      arm64) gitleaks_arch=arm64; gitleaks_sha=${GITLEAKS_SHA256_ARM64} ;; \
      *) echo "unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    asset="gitleaks_${GITLEAKS_VERSION}_linux_${gitleaks_arch}.tar.gz"; \
    curl -fsSLo "/tmp/${asset}" \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${asset}"; \
    echo "${gitleaks_sha}  /tmp/${asset}" | sha256sum -c -; \
    tar xzf "/tmp/${asset}" -C /usr/local/bin gitleaks; \
    rm -f "/tmp/${asset}"; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /srv/app

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install .

# Run unprivileged. /srv/app stays root-owned and read-only to the service; the
# only writable path is the checkout/data directory the analysis pipeline uses,
# which is a mounted volume in compose.
#
# The long option forms are deliberate: python:3.12-slim is Debian trixie, whose
# adduser/addgroup no longer accept the `-S`/`-G` short flags (they fail with exit
# 51 and print usage), which broke the first image build.
RUN addgroup --system intel && adduser --system --ingroup intel --home /home/intel intel \
    && mkdir -p /data \
    && chown intel:intel /data

USER intel

ENV RETRACT_DATA_DIR=/data

EXPOSE 8000

# A plain GET, not `wget --spider`: spider sends HEAD and the health route only
# answers GET, which would report a healthy container as unhealthy.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
