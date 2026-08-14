# ---------------------------------------------------
# PhoenixAuto-Ops Core Automation Engine
# Author: Didarul Islam
# Multi-stage build for PhoenixAuto-Ops
# ---------------------------------------------------

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

WORKDIR /build

# psutil compiles a C extension at install time - gcc is only needed here,
# never in the runtime image
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim

# Populated at build time (see docker-compose.yml build.args or the
# --build-arg flags below) so the image carries real provenance instead of
# static placeholder metadata baked in once and never updated.
ARG BUILD_DATE=unknown
ARG VCS_REF=unknown
ARG VERSION=0.1.0

LABEL org.opencontainers.image.title="PhoenixAuto-Ops" \
      org.opencontainers.image.description="Modular server health monitoring, alerting, and self-healing engine" \
      org.opencontainers.image.authors="Didarul Islam" \
      org.opencontainers.image.source="https://github.com/didar67/phoenixauto-ops" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}"

WORKDIR /app

# curl/procps kept for the healthcheck and for future healing actions that
# inspect processes. cron and sudo intentionally dropped - see notes below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    bash \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for running the application
RUN useradd -m -u 1000 phoenixops && \
    mkdir -p /app/logs /app/config && \
    chown -R phoenixops:phoenixops /app

# Copy Python packages from builder
COPY --chown=phoenixops:phoenixops --from=builder /root/.local /home/phoenixops/.local

# Set environment variables
ENV PYTHONPATH=/app:$PYTHONPATH \
    PYTHONUNBUFFERED=1 \
    PATH=/home/phoenixops/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1

# Copy project files
COPY --chown=phoenixops:phoenixops app/ /app/app/
COPY --chown=phoenixops:phoenixops config/ /app/config/
COPY --chown=phoenixops:phoenixops scripts/ /app/scripts/

# Make all shell scripts executable
RUN chmod +x /app/scripts/*.sh && \
    # Create log directory with proper permissions
    mkdir -p /app/logs && \
    chown -R phoenixops:phoenixops /app/logs && \
    chmod 755 /app/logs

# NOTE ON HEALING SCRIPTS (documented honestly rather than hidden):
# service_manager.sh calls `sudo systemctl ...`. Inside this container there
# is no systemd process (PID 1 is the Python engine, not init) and no sudo
# binary, so restart_service() will fail structurally regardless of
# permissions. We deliberately do NOT grant sudo/systemctl access here - a
# NOPASSWD sudoers entry would defeat the entire point of running as a
# non-root user without making systemctl actually work. Recommended fix:
# set auto_healing.dry_run: true in config/thresholds.yaml for containerized
# deployments, or gate service-restart healing behind a HOST_MODE env check
# once host-level monitoring (mounted /proc, --pid=host) is wired up.


USER phoenixops


RUN python -c "import psutil, yaml, requests, dotenv; print('Dependencies verified')"

# Split ENTRYPOINT/CMD so the module can be overridden at `docker run` time
# without editing the image (e.g. for a one-off script or a shell for debugging)
ENTRYPOINT ["python"]
CMD ["-u", "-m", "app.main"]

# Import-only healthchecks lie: a hung run_forever() loop still imports fine.
# StructuredLogger touches logs/phoenixauto-ops.log every cycle
# (cycle_interval_seconds, default 60s), so a stale log file is a much more
# honest liveness signal than "did the import succeed."
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD find /app/logs/phoenixauto-ops.log -mmin -2 | grep -q . || exit 1
