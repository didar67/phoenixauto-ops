# 🐳 PhoenixAuto-Ops — Docker & Containerization

This document covers the containerized deployment of PhoenixAuto-Ops: the multi-stage Dockerfile, `docker-compose.yml` service definition, host-system monitoring design, lifecycle handling, and a known platform limitation identified during runtime testing.

Docker packages the same `MonitoringEngine` cycle described in [docs/architecture.md](architecture.md) — nothing about the monitor → evaluate → alert → heal flow changes inside a container. What Docker adds is process isolation, a non-root runtime, and (optionally) the ability to observe the *host* machine's vitals from inside a container rather than the container's own namespace.

---

## Why Containerize

- **Portability** — runs identically on any Docker-capable host without a Python/venv setup per machine
- **Isolation** — the monitoring engine and its dependencies are sandboxed from the host's own Python environment
- **Deployment path** — a prerequisite for Phase 3 (CI/CD + GHCR image push) and Phase 4 (AWS ECS Fargate) on the project roadmap

---

## Container Architecture

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                         Docker Build (multi-stage)                       │
│                                                                          │
│   Stage 1: builder (python:3.11-slim)                                    │
│     └── gcc installed → pip install --user -r requirements.txt          │
│           (psutil compiles a C extension; gcc never reaches runtime)    │
│                                                                          │
│   Stage 2: runtime (python:3.11-slim)                                    │
│     ├── curl, bash, procps installed                                    │
│     ├── non-root user `phoenixops` (uid 1000) created                   │
│     ├── /root/.local copied from builder → /home/phoenixops/.local     │
│     ├── app/, config/, scripts/ copied in                               │
│     └── ENTRYPOINT ["python"]  CMD ["-u", "-m", "app.main"]             │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      docker-compose.yml (phoenixops service)             │
│                                                                          │
│   env_file: .env  +  environment: HOST_PROC_PATH, HOST_ROOT_PATH        │
│   volumes:                                                              │
│     ./config  → /app/config   (rw — tune thresholds without rebuild)   │
│     ./logs    → /app/logs     (rw — persists across container restart) │
│     ./.env    → /app/.env     (ro)                                      │
│     /proc     → /host/proc    (ro — host-level metric visibility)      │
│     /         → /rootfs       (ro — host disk usage visibility)        │
│   healthcheck: inherited from Dockerfile HEALTHCHECK (no override)     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Dockerfile Reference

### Multi-Stage Build

| Stage | Base Image | Purpose |
|-------|-----------|---------|
| `builder` | `python:3.11-slim` | Compiles `psutil`'s C extension and installs all packages from `requirements.txt` into `--user` site-packages |
| runtime (final) | `python:3.11-slim` | Copies only the installed packages and application code — no compiler toolchain ships in the final image |

Splitting the build this way keeps `gcc` and its transitive `apt` dependencies out of the image that actually runs in production, which matters for both image size and attack surface.

### Non-Root Runtime User

The container runs as `phoenixops` (uid 1000), not root. Earlier iterations of the Dockerfile granted this user passwordless `sudo` access to `systemctl` so `HealingActions.restart_service()` (see [docs/architecture.md](architecture.md#apphealing--remediation-layer)) could reach host services — this was removed. A container has no `systemd` process (PID 1 is the Python engine itself), so `sudo systemctl restart <service>` fails structurally regardless of permissions; keeping the sudoers grant would have been a real privilege-escalation surface for a command that could never actually succeed. See **Known Limitations** below for what this means for the healing layer specifically.

### Entrypoint

```dockerfile
ENTRYPOINT ["python"]
CMD ["-u", "-m", "app.main"]
```

Run as a module (`-m app.main`) rather than a direct script path, matching how the venv-based setup runs it (see [docs/setup.md](setup.md#step-7--verify-the-full-stack)). Splitting `ENTRYPOINT`/`CMD` lets the module be overridden at `docker run` time (e.g. `docker run phoenixauto-ops -m pytest`) without rebuilding.

### Healthcheck

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD find /app/logs/phoenixauto-ops.log -mmin -2 | grep -q . || exit 1
```

Checks that the structured log file (see [docs/architecture.md](architecture.md#apputils--support-layer)) has been touched within the last two monitoring cycles at the default `cycle_interval_seconds`. An import-only healthcheck (`python -c "import app.engine"`) would report healthy even if the monitoring loop had hung mid-cycle — checking for a recent log write is a genuine liveness signal, not just an import smoke test.

`docker-compose.yml` does not define its own `healthcheck:` block. Compose inherits the image's `HEALTHCHECK` automatically; a service-level override was removed because it duplicated the exact same values, which just meant the two could silently drift apart over time.

### OCI Image Metadata

```dockerfile
ARG VERSION=0.1.0
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="PhoenixAuto-Ops" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}"
```

Standard `org.opencontainers.image.*` labels, populated at build time via `--build-arg` (wired through `docker-compose.yml`'s `build.args`, see below). Registry tooling and vulnerability scanners (e.g. Trivy, planned for Phase 3) read these labels for provenance — a static, hand-written label would defeat the purpose.

---

## docker-compose.yml Reference

### Build Arguments

```yaml
build:
  args:
    VERSION: "${VERSION:-0.1.0}"
    VCS_REF: "${VCS_REF:-unknown}"
    BUILD_DATE: "${BUILD_DATE:-unknown}"
```

Export these before building to get real provenance instead of the `unknown` fallback:

```bash
export VERSION=1.0.0
export VCS_REF=$(git rev-parse --short HEAD)
export BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
docker compose build
```

### Lifecycle Settings

| Setting | Value | Reason |
|---------|-------|--------|
| `restart` | `unless-stopped` | Recovers from crashes without manual intervention, but respects an intentional `docker compose down` |
| `stop_grace_period` | `40s` | `HealingActions._execute_command()` gives shell scripts up to 30s (see [docs/architecture.md](architecture.md#apphealing--remediation-layer)); the default 10s grace period could get a mid-healing cycle SIGKILLed before it finishes cleanly |
| `logging.driver` | `json-file`, `max-size: 10m`, `max-file: 3` | Caps on-disk log growth — the same rotation concern `logger.py` already handles for `logs/phoenixauto_ops.log`, applied at the Docker layer for stdout |

---

## Host System Monitoring

By default, a containerized process only sees its own namespace — `psutil.cpu_percent()`, `virtual_memory()`, etc. would describe the *container*, not the machine it runs on. Since PhoenixAuto-Ops exists to monitor a server, self-monitoring the container defeats the purpose.

### Design

```yaml
environment:
  HOST_PROC_PATH: /host/proc
  HOST_ROOT_PATH: /rootfs

volumes:
  - /proc:/host/proc:ro
  - /:/rootfs:ro
```

`app/monitoring/system.py` reads these at import time:

```python
_HOST_PROC_PATH = os.environ.get("HOST_PROC_PATH")
if _HOST_PROC_PATH:
    psutil.PROCFS_PATH = _HOST_PROC_PATH

_DISK_CHECK_PATH = os.environ.get("HOST_ROOT_PATH", "/")
```

This is the same bind-mount pattern used by Prometheus `node_exporter` and cAdvisor — mount the host's `/proc` and `/` read-only, then point the metrics library at the mount instead of the container's own view. `/proc/stat`, `/proc/meminfo`, and `/proc/loadavg` are generated relative to whichever namespace originally mounted that procfs instance; since it's the host's real `/proc` bind-mounted in, reading it from inside the container returns the host's actual numbers. This works without `--pid=host` or `network_mode: host`, so the container keeps its own process and network isolation.

| Metric | Source | Needs host mount? |
|--------|--------|--------------------|
| CPU / memory | `/proc/stat`, `/proc/meminfo` via `PROCFS_PATH` | Yes |
| Disk usage | `psutil.disk_usage(HOST_ROOT_PATH)` | Yes |
| Load average | `os.getloadavg()` | No — load average is a global kernel statistic, not namespaced per container |

---

## Graceful Shutdown

Docker sends `SIGTERM` on `docker stop` / `docker compose down`, not `SIGINT`. `KeyboardInterrupt` in `app/main.py` only fires on `SIGINT`, so the original container implementation was getting silently `SIGKILL`ed once the stop grace period elapsed — no shutdown log entry, no confirmation the current cycle had finished.

`app/main.py` now registers a handler:

```python
def _handle_sigterm(signum, frame) -> None:
    logger.info("Received shutdown signal. Stopping gracefully.")
    engine.shutdown()

signal.signal(signal.SIGTERM, _handle_sigterm)
```

`MonitoringEngine.shutdown()` sets a flag checked between cycles, and `run_forever()` sleeps in 1-second increments (`_interruptible_sleep()`) rather than one long `time.sleep(cycle_interval)` call, so a `SIGTERM` arriving mid-wait is honored within roughly a second instead of waiting out the full interval.

---

## ⚠️ Known Limitation — Network Metrics Under Docker Desktop (WSL2)

`NetworkMetrics.collect()` reads `/proc/net/dev` and `/proc/net/tcp` for bandwidth and connection-count metrics. Under native Linux, the `HOST_PROC_PATH` bind-mount described above makes these resolve correctly. Verified via runtime testing on **Docker Desktop for Windows (WSL2 backend)**, this fails:

```
WARNING | Failed to get bytes sent: [Errno 2] No such file or directory: '/host/proc/net/dev'
WARNING | Failed to get bytes received: [Errno 2] No such file or directory: '/host/proc/net/dev'
WARNING | Failed to get connections: [Errno 2] No such file or directory: '/host/proc/net/tcp'
```

**Root cause:** Docker Desktop's WSL2 backend runs the Docker daemon inside a separate, hidden lightweight VM (`docker-desktop` distro), not the user's own WSL distro. The `/proc:/host/proc:ro` bind mount attaches to that VM's `/proc`. Static, snapshot-style files (`/proc/stat`, `/proc/meminfo`) relay through Docker Desktop's file-sharing layer correctly, but dynamically-generated `seq_file` entries like `/proc/net/dev` and `/proc/net/tcp` require direct kernel procfs access that the virtio-fs/gRPC-FUSE sharing layer does not forward.

**What still works correctly despite this:**
- CPU, memory, disk, and load average metrics — confirmed accurate against host `htop`/`free -h` during testing
- `_safe_execute()` (see [docs/architecture.md](architecture.md#appmonitoring--metrics-layer)) catches the exception per-metric, logs a `WARNING`, and returns a `0` default — the monitoring cycle completes successfully rather than crashing
- Graceful shutdown, healing, and alerting are entirely unaffected

**Not planned as a container-level fix.** This is a Docker Desktop / WSL2 platform constraint, not a bug in `NetworkMetrics` or the mount configuration — the identical `docker-compose.yml` is expected to report network metrics correctly on a native Linux host (the Phase 4 AWS EC2 target). Re-verification on a native Linux Docker host is a follow-up item once Phase 4 begins.

---

## Running with Docker

```bash
git clone https://github.com/didar67/phoenixauto-ops.git
cd phoenixauto-ops

cp .env.example .env
nano .env   # same secrets as the venv-based setup — see docs/setup.md

export VERSION=1.0.0
export VCS_REF=$(git rev-parse --short HEAD)
export BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')

docker compose up --build
```

Watch structured logs the same way as the venv-based setup:

```bash
docker compose logs -f phoenixops
```

Stop cleanly (confirms `"Received shutdown signal. Stopping gracefully."` in the logs before exit):

```bash
docker compose down
```

---

## Git Branch History — Docker Work

Following the same feature-branch workflow documented in [docs/development-workflow.md](development-workflow.md), containerization was built across five sequential branches, each merged to `main` before the next was cut:

| Branch | What Was Built |
|--------|----------------|
| `feature/dockerization` | Initial multi-stage `Dockerfile`, `docker-compose.yml`, and `.dockerignore`; base Python application container and runtime image setup |
| `feat/docker-security` | Non-root `phoenixops` runtime user; removed `sudo`/sudoers dependency and the unprivileged-but-`NOPASSWD`-sudo contradiction it created |
| `feat/docker-runtime` | Graceful `SIGTERM` shutdown; eliminated a redundant second `collect()` call per cycle; module-based `python -m app.main` entrypoint; OCI image metadata via build args |
| `feat/docker-host-monitoring` | Host `/proc` and root filesystem mounts; `HOST_PROC_PATH` / `HOST_ROOT_PATH` environment variables; `psutil.PROCFS_PATH` override in `system.py` |
| `feat/docker-healthcheck` | Docker `HEALTHCHECK` directive; log-freshness-based liveness validation replacing the earlier import-only check |

---

## Security Model Additions

Extending the security table in [docs/architecture.md](architecture.md#security-model) for the containerized deployment specifically:

| Concern | Mitigation |
|---------|------------|
| Root-in-container | `phoenixops` (uid 1000) runs the engine; no `sudo` binary or sudoers grant exists in the image |
| Host filesystem exposure | `/proc` and `/` are mounted **read-only** (`:ro`) — the container can read host metrics but cannot write to the host filesystem |
| Secrets in image layers | `.dockerignore` excludes `.env` and `config/secrets.yaml` from the build context entirely, so they can never be baked into a layer even by an accidental `COPY . .` |
| Unbounded resource usage | `deploy.resources.limits` caps the container at 1 CPU / 512M memory |
