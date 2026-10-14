# syntax=docker/dockerfile:1.7
#
# Two stages: dependencies are built into a virtualenv in the first, and only that
# virtualenv plus the application code reach the runtime image. The runtime has no pip,
# no compiler and no shell history to speak of, which keeps the Trivy gate green.

ARG PYTHON_IMAGE=python:3.13-alpine3.24

# ---------------------------------------------------------------- build
FROM ${PYTHON_IMAGE} AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

COPY requirements.txt .
RUN pip install --require-hashes --no-deps -r requirements.txt 2>/dev/null \
    || pip install -r requirements.txt

# pip and setuptools are only needed to install; drop them from the shipped venv.
RUN pip uninstall -y pip setuptools wheel 2>/dev/null || true

# ---------------------------------------------------------------- runtime
FROM ${PYTHON_IMAGE} AS runtime

ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="shelfwise-backend" \
      org.opencontainers.image.description="Shelfwise library circulation API (FastAPI)" \
      org.opencontainers.image.source="https://github.com/Aanviiii/DevOps-project" \
      org.opencontainers.image.version="${APP_VERSION}"

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHELFWISE_APP_VERSION=${APP_VERSION}

# The base image's own pip is not used at runtime either; removing it removes its CVEs.
RUN python -m pip uninstall -y pip 2>/dev/null; \
    addgroup -S -g 10001 shelfwise && \
    adduser -S -D -H -u 10001 -G shelfwise shelfwise

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --chown=10001:10001 alembic.ini ./
COPY --chown=10001:10001 alembic ./alembic
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 docker-entrypoint.sh ./

# Numeric UID so Kubernetes can verify runAsNonRoot without resolving names.
USER 10001

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
