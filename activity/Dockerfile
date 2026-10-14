# syntax=docker/dockerfile:1.7
# A single stdlib-only script: no dependencies to install, no pip in the image.
FROM python:3.13-alpine3.24

ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="shelfwise-activity" \
      org.opencontainers.image.description="Simulated library patrons that keep the Shelfwise API busy" \
      org.opencontainers.image.source="https://github.com/Aanviiii/DevOps-project" \
      org.opencontainers.image.version="${APP_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m pip uninstall -y pip 2>/dev/null; \
    adduser -S -D -H -u 10002 activity

WORKDIR /app
COPY generator.py .
USER 10002

ENTRYPOINT ["python", "/app/generator.py"]
