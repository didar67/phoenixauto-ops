# 🔥 PhoenixAuto-Ops

> **Automated Server Health Monitoring, Alerting & Self-Healing System** — a production-oriented Python/Bash system that watches your infrastructure, fires multi-channel alerts, and autonomously remediates failures without human intervention.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%2F%20Ubuntu-orange?logo=linux)](https://ubuntu.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen)]()

---

## 📌 What Is This?

PhoenixAuto-Ops continuously monitors server vitals — CPU, memory, disk, load average, and network I/O — and reacts to threshold violations through a multi-channel alert pipeline (Telegram, Slack, Email) and an automated healing engine that can restart services, flush caches, and execute custom remediation scripts.

Designed as a portfolio-grade DevOps project demonstrating: modular Python architecture, production Bash scripting, systemd/cron integration, and disciplined configuration management.

---

## ✨ Features

- 📊 **Real-time metrics** — CPU, memory, disk, load average, network TX/RX via `psutil`
- 🚨 **Multi-channel alerting** — Telegram, Slack, Email with per-channel cooldown enforcement
- 🛠️ **Self-healing engine** — service restarts, cache flush, and old log cleanup via shell scripts with dry-run support
- 🔁 **Dry-run & retry** — safely test healing logic before enabling it on production
- 🗂️ **Structured logging** — JSON log output with rotation to `logs/phoenixauto_ops.log`
- ⚙️ **Config-driven** — all thresholds and healing flags live in `config/thresholds.yaml`
- 🔒 **Secrets management** — credentials in `.env`, never committed to version control
- ⏰ **Autonomous scheduling** — cron-based execution via idempotent `cron/setup_cron.sh`
- 🐳 **Containerized** — multi-stage Docker build, non-root runtime, host-level system monitoring via read-only `/proc` and host filesystem mounts

---

## 🏗️ Architecture

```
engine.py (Orchestration Loop)
    │
    ├── monitoring/     → Collect CPU / Mem / Disk / Network snapshots
    ├── alerting/       → Evaluate thresholds → dispatch Telegram / Slack / Email
    └── healing/        → Execute shell-level remediation (restart, flush, cleanup)
```

For detailed component breakdown, data flow, and design patterns → **[docs/architecture.md](docs/architecture.md)**

---

## 📁 Project Structure

```
phoenixauto-ops/
├── app/
│   ├── monitoring/         # SystemMetrics, NetworkMetrics (psutil)
│   ├── alerting/           # Telegram, Slack, Email senders
│   ├── healing/            # HealingActions with dry-run and retry
│   ├── utils/              # Config loader, structured logger
│   ├── engine.py           # Core monitor → alert → heal orchestration
│   └── main.py             # Entry point
├── scripts/                # Bash: service_manager.sh, cleanup.sh, run_monitor.sh
├── cron/                   # setup_cron.sh — idempotent crontab installer
├── config/                 # Metric thresholds + healing config
├── logs/                   # Runtime JSON logs (git-ignored)
├── venv/                   # Python virtual environment (Generated locally, git-ignored)
├── .env                    # Secrets — NEVER commit (git-ignored)
├── .env.example            # Secret template — safe to commit
├── setup.sh                # One-command setup script
└── requirements.txt        # Python dependencies for PhoenixAuto-Ops
```

Full structure explanation → **[docs/structure.md](docs/structure.md)**

---

## 🚀 Quick Start

```bash
git clone https://github.com/didar67/phoenixauto-ops.git
cd phoenixauto-ops

# One-command setup (creates venv, installs deps, sets permissions)
chmod +x setup.sh && sudo ./setup.sh

# Activate virtual environment
source venv/bin/activate

# Configure secrets
cp .env.example .env
nano .env   # Add TELEGRAM_BOT_TOKEN, SLACK_WEBHOOK_URL, or SMTP credentials

# Run a one-shot monitoring cycle
python3 -m app.main
```

Full setup instructions including sudoers, cron, and threshold tuning → **[docs/setup.md](docs/setup.md)**

### Run with Docker (alternative to venv/cron)
Prefer a container?

\`\`\`bash
docker compose up --build
\`\`\`

Full container details, host monitoring setup, and known limitations → **[docs/docker.md](docs/docker.md)**

---

## ⚙️ Configuration

| File | Purpose | Commit? |
|------|---------|---------|
| `config/thresholds.yaml` | Metric thresholds + healing flags | ✅ Yes |
| `.env` | Bot tokens, webhook URLs, SMTP creds | ❌ Never |

Key thresholds (`config/thresholds.yaml`):

```yaml
thresholds:
  cpu_usage_percent: 80.0       # Alert/Heal if CPU > this value
  memory_usage_percent: 85.0    # Alert/Heal if RAM > this value
  disk_usage_percent: 90.0      # Alert/Heal if Disk (/) > this value
  load_average_limit: 4.0       # 1-minute load average 

# Network related thresholds
network:
  max_connections: 500          # Active TCP connections
  latency_ms: 200               # Round-trip latency in ms

# Self-Healing behavior
auto_healing:
  enabled: true
  dry_run: false                # If true, actions will be logged but not executed
  max_retry_attempts: 3         # How many times to retry an action before giving up
  cooldown_seconds: 300         # Wait time between healing attempts (5 min)
```

Full configuration reference → **[docs/configuration.md](docs/configuration.md)**

---

## 🧪 Verify It's Working

```bash
# One-shot run — see metrics, alerts, healing output
python3 -m app.main

# Watch structured JSON logs in real time
tail -f logs/phoenixauto_ops.log | python3 -m json.tool

# Run via production wrapper (handles venv)
bash scripts/run_monitor.sh
```

---

## 🗺️ Roadmap

| Phase | Status | Scope |
|-------|--------|-------|
| **Phase 1** — Core System | ✅ Complete | Python monitoring + alerting + healing + cron |
| **Phase 2** — Docker | ✅ Complete | Multi-stage build, non-root container, host-level monitoring, health checks, OCI metadata |
| **Phase 3** — CI/CD + Security | 🔜 Planned | GitHub Actions, Trivy scanning, GHCR image push |
| **Phase 4** — AWS | 🔜 Planned | ECS Fargate, Secrets Manager, Terraform IaC |

---

## 📚 Documentation

| File | Description |
|------|-------------|
| [docs/architecture.md](docs/architecture.md) | System design, component responsibilities, data flow |
| [docs/structure.md](docs/structure.md) | Project folder structure and file explanations |
| [docs/setup.md](docs/setup.md) | Full installation, sudoers, cron, and troubleshooting |
| [docs/configuration.md](docs/configuration.md) | Complete thresholds.yaml and .env reference |
| [docs/development-workflow.md](docs/development-workflow.md) | Git branching model, commit guidelines, and roadmap steps |
| [docs/docker.md](docs/docker.md) | Dockerfile, docker-compose.yml, .dockerignore, host monitoring design, and known limitations |

---

## 👨‍💻 Author

**Md. Didarul Islam** — Aspiring DevOps / Cloud Engineer (Portfolio Project)

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin)](https://linkedin.com/in/didarul-islam-00b083373)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?logo=github)](https://github.com/didar67)
