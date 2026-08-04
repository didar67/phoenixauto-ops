# ---------------------------------------------------
# PhoenixAuto-Ops Core Automation Engine
# Author: Didarul Islam
# Multi-stage build for PhoenixAuto-Ops
# Stage 1: Builder - install dependencies
# ---------------------------------------------------
FROM python:3.11-slim as builder

WORKDIR /build

# Install system dependencies for build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies: cron, curl, shell utilities, sudo
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    curl \
    bash \
    procps \
    sudo \
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
COPY --chown=phoenixops:phoenixops cron/ /app/cron/
COPY --chown=phoenixops:phoenixops scripts/ /app/scripts/

# Make all shell scripts executable
RUN chmod +x /app/scripts/*.sh /app/cron/*.sh && \
    # Create log directory with proper permissions
    mkdir -p /app/logs && \
    chown -R phoenixops:phoenixops /app/logs && \
    chmod 755 /app/logs

# Allow phoenixops to run scripts without password (for sudo in scripts if needed)
RUN echo "phoenixops ALL=(ALL) NOPASSWD: /usr/sbin/systemctl, /usr/bin/find, /bin/bash" >> /etc/sudoers.d/phoenixops && \
    chmod 0440 /etc/sudoers.d/phoenixops

# Switch to non-root user
USER phoenixops

# Verify Python packages are accessible
RUN python -c "import psutil, yaml, requests, dotenv; print('Dependencies verified')"

# Default entrypoint: run main monitoring engine
ENTRYPOINT ["python", "-u"]
CMD ["app/main.py"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import app.engine; print('healthy')" || exit 1
