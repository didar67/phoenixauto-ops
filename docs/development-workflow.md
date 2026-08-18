# 🔀 PhoenixAuto-Ops — Development Workflow

This document covers the Git branching strategy used to build PhoenixAuto-Ops, the reasoning behind it, and how to follow the same workflow when adding new features.

---

## Branching Strategy

PhoenixAuto-Ops was built using a **feature branch workflow**: every piece of functionality was developed in an isolated branch, tested independently, and merged into `main` only after it was working correctly. `main` always remains in a stable, runnable state.

```
main
 │
 ├── feat/initial-skeleton       ──► merged → Core project skeleton + modular architecture
 ├── feat/config-loader          ──► merged → ConfigLoader + thresholds.yaml
 ├── feat/logging-setup          ──► merged → JSON logger + RotatingFileHandler
 ├── feat/monitoring-system-metrics ──► merged → BaseMetricCollector + SystemMetrics
 ├── feat/monitoring-network     ──► merged → NetworkMetrics
 ├── feat/alerting-base          ──► merged → BaseAlertSender + cooldown logic
 ├── feat/alerting-telegram      ──► merged → TelegramAlertSender
 ├── feat/alerting-slack         ──► merged → SlackAlertSender
 ├── feat/alerting-email         ──► merged → EmailAlertSender
 ├── feat/healing-base           ──► merged → BaseHealer (dry-run, retry)
 ├── feat/healing-actions        ──► merged → HealingActions shell integration
 ├── feat/linux-automation-scripts ──► merged → service_manager.sh + cleanup.sh
 ├── feat/healing-shell-integration ──► merged → actions.py updated to call scripts
 ├── feat/cron-scheduler         ──► merged → run_monitor.sh + setup_cron.sh
 ├── feat/core-engine            ──► merged → engine.py + main.py (full cycle)
 ├── feat/project-installer      ──► merged → Automated one-command setup script setup.sh
 ├── feat/env-files              ──► merged → Secure configuration template .env.example
 ├── feat/documentation-core     ──► merged → README.md, architecture.md, structure.md
 ├──feat/documentation-guides   ──► merged → setup.md, configuration.md, development-workflow.md
 ├── feature/dockerization       ──► merged → Multi-stage Dockerfile, Docker Compose, containerized runtime
 ├── feat/docker-security        ──► merged → Non-root user, removed sudo/sudoers dependency
 ├── feat/docker-runtime         ──► merged → Graceful SIGTERM shutdown, double-collect fix, OCI metadata
 ├── feat/docker-host-monitoring ──► merged → Host /proc & rootfs mounts, PROCFS_PATH support
 ├── feat/docker-healthcheck     ──► merged → Log-based liveness HEALTHCHECK
 ├── feat/docker-documentation   ──► merged → docs/docker.md (Dockerfile/compose reference, host-monitoring design, WSL2 limitation)
 └── feat/pytest-suite           ──► merged → 48-case pytest suite (unit + integration), 80% coverage
```

**Branch naming convention:** `feat/<component-or-feature-name>` — lowercase, hyphen-separated, scoped to what the branch actually builds.

---

## Why Feature Branches?

Building one component per branch rather than committing everything to `main` directly provides several concrete benefits:

**Clean commit history.** Each merge commit represents a single, reviewable unit of work. `git log --oneline` reads like a changelog, not a stream of "fix" and "update" messages.

**Isolated testing.** A bug in `feat/alerting-telegram` doesn't block work on `feat/healing-actions`. Each branch can be tested independently before it touches `main`.

**Safe experimentation.** If an approach doesn't work out — for example, a first attempt at the healing retry loop — the branch can be deleted and restarted without any cleanup on `main`.

**Portfolio visibility.** The branch history on GitHub demonstrates how the project was built incrementally and systematically, which is a meaningful signal to engineering reviewers. It shows you understand how collaborative development works even on a solo project.

---

## Completed Feature Branches

| Branch | What Was Built |
|--------|----------------|
| `feat/initial-skeleton` | Modular folder setup (app/, config/, scripts/), configured .gitignore, added requirements.txt, and introduced environment setup shell script |
| `feat/config-loader` | `ConfigLoader` class in `app/utils/config_loader.py`; `config/thresholds.yaml` with initial threshold structure; `.env.example` template |
| `feat/logging-setup` | `app/utils/logger.py` with JSON formatter and `RotatingFileHandler`; `logs/` directory with `.gitkeep` |
| `feat/monitoring-system-metrics` | `BaseMetricCollector` in `app/monitoring/base.py`; `SystemMetrics` in `app/monitoring/system.py` for CPU, memory, disk, and load average collection via `psutil` |
| `feat/monitoring-network` | `NetworkMetrics` in `app/monitoring/network.py` for TX/RX throughput and connection count; `app/monitoring/__init__.py` updated |
| `feat/alerting-base` | `BaseAlertSender` in `app/alerting/base.py` with cooldown enforcement and `format_message()`; `app/alerting/__init__.py` |
| `feat/alerting-telegram` | `TelegramAlertSender` in `app/alerting/telegram.py`; Telegram Bot API integration with `requests` |
| `feat/alerting-slack` | `SlackAlertSender` in `app/alerting/slack.py`; Slack Incoming Webhook POST |
| `feat/alerting-email` | `EmailAlertSender` in `app/alerting/email.py`; SMTP/TLS via `smtplib` with multi-recipient support |
| `feat/healing-base` | `BaseHealer` in `app/healing/base.py` with dry-run flag, retry loop, per-action cooldown, and `auto_healing` config integration |
| `feat/healing-actions` | `HealingActions` in `app/healing/actions.py`; initial breach-type to action mapping |
| `feat/linux-automation-scripts` | `scripts/service_manager.sh` (systemctl wrapper); `scripts/cleanup.sh` (disk/cache cleanup with dry-run flag) |
| `feat/healing-shell-integration` | `app/healing/actions.py` updated to run shell scripts with `subprocess.run()` and timeout handling |
| `feat/cron-scheduler` | `scripts/run_monitor.sh` (venv-aware, cron-safe wrapper that activates venv); `cron/setup_cron.sh` (idempotent crontab installer) |
| `feat/core-engine` | `app/engine.py` (`MonitoringEngine` — full monitor → evaluate → alert → heal cycle); `app/main.py` (entry point); manual end-to-end testing via one-shot runs and log inspection |
| `feat/project-installer` | Root-level `setup.sh` (venv, deps, permissions, cronjob)
| `feat/env-files` | Added `.env.example` template for Telegram, Slack, and Email alerting |
| `feat/documentation-core` | Added and refined `README.md`, `docs/architecture.md`, and `docs/structure.md` with project overview, architecture documentation, and repository structure reference |
| `feat/documentation-guides` | Added and refined `docs/setup.md`, `docs/configuration.md`, and `docs/development-workflow.md` covering installation, configuration management, and the project's Git workflow |
| `feature/dockerization` | Initial `Dockerfile` (multi-stage), `docker-compose.yml`, `.dockerignore`; Python application containerized with a builder + runtime stage |
| `feat/docker-security` | Removed `sudo`/sudoers dependency and cron-in-container from the runtime image; confirmed non-root `phoenixops` user for all subprocess calls |
| `feat/docker-runtime` | SIGTERM handler in `app/main.py` for graceful shutdown; fixed a double `collect()` call per cycle in `engine.py`; `python -m app.main` module entrypoint; OCI image labels (`org.opencontainers.image.*`) |
| `feat/docker-host-monitoring` | Host `/proc` and root filesystem bind-mounted read-only into the container; `HOST_PROC_PATH`/`HOST_ROOT_PATH` env vars; `psutil.PROCFS_PATH` override in `app/monitoring/system.py` |
| `feat/docker-healthcheck` | Replaced import-only `HEALTHCHECK` with a log-freshness check (`find ... -mmin -2`) validating the monitoring loop is actually alive, not just that the module imports |
| `feat/docker-documentation` | `docs/docker.md` — full Dockerfile/`docker-compose.yml` reference, multi-stage build breakdown, non-root user rationale, host `/proc`+`/` bind-mount design for `HOST_PROC_PATH`/`HOST_ROOT_PATH`, graceful SIGTERM shutdown flow, and the documented Docker Desktop (WSL2) network-metrics limitation with root cause and workaround plan |
| `feat/pytest-suite` | `tests/conftest.py` with `patch_config` fixture; unit tests for `ConfigLoader`, `SystemMetrics`, `NetworkMetrics`, all three alert senders, and `HealingActions`; integration tests for `MonitoringEngine.run_cycle()`; `pytest.ini` with coverage reporting |

---

## Standard Development Flow

This is the workflow to follow for any new feature, whether a new alert channel, a new monitor, or a configuration improvement.

### 1. Create a Feature Branch

Branch off `main`. Never develop directly on `main`.

```bash
git checkout main
git pull origin main                      # Ensure you're starting from the latest state
git checkout -b feat/new-alert-channel
```

### 2. Build and Test Locally

Run the feature locally and verify behavior with a one-shot execution and log inspection.

### 3. Commit with a Meaningful Message

Write commit messages that describe **what changed and why**, not just what the file is:

```bash
# Good — describes the change and its purpose
git commit -m "Add PagerDuty alert channel with cooldown and retry support"

# Too vague — tells a reviewer nothing
git commit -m "update alerting"
```

For a multi-step feature, commit each logical step separately:

```bash
git commit -m "Add BaseAlertSender._dispatch() contract for PagerDuty"
git commit -m "Implement PagerDuty Events API v2 POST in PagerDutySender"
git commit -m "Register PagerDutySender in engine.py alert dispatch list"
```

### 4. Push and Merge

```bash
git push origin feat/new-alert-channel
```

On GitHub, open a pull request from `feat/new-alert-channel` → `main`. Review the diff yourself before merging — this habit of self-reviewing catches small mistakes (debug prints, hardcoded values, leftover TODO comments) before they land on `main`.

Merge using **squash merge** if the branch has many small WIP commits, or a regular merge if the commits are already clean and meaningful.

---

## Adding New Components

### New Monitor (e.g., database metrics)

```bash
git checkout -b feat/monitoring-database

# 1. Create `app/monitoring/database.py`
touch app/monitoring/database.py

# 2. Extend `BaseMetricCollector` and implement `collect()`
# 3. Register the monitor in `app/engine.py`.
# 4. Add any new threshold to `config/thresholds.yaml`
```

### New Alert Channel (e.g., PagerDuty)

```bash
git checkout -b feat/alerting-pagerduty

# 1. Create the file
touch app/alerting/pagerduty.py

# 2. Extend BaseAlertSender, implement _dispatch()
# class PagerDutySender(BaseAlertSender):
#     def _dispatch(self, payload: dict) -> None:
#         # POST to PagerDuty Events API v2

# 3. Add credentials to .env.example and .env
# PAGERDUTY_ROUTING_KEY=your_32_char_integration_key

# 4. Register in engine.py alert dispatch list
# alert_senders.append(PagerDutySender(config))
```

### New Healing Action (e.g., Redis restart)

```bash
git checkout -b feat/healing-redis-restart

# 1. Write the shell script
touch scripts/restart_redis.sh

# 2. Implement the new method inside HealingActions in app/healing/actions.py
# def restart_redis(self) -> bool:
#     # call subprocess.run() to execute scripts/restart_redis.sh with timeout

# 3. Add sudoers permission if needed
# youruser ALL=(ALL) NOPASSWD: /path/to/scripts/restart_redis.sh
```

---

## Code Quality Standards

These standards apply to every file in `app/`:

**Type hints on all public functions:**

```python
def collect(self) -> dict:
    ...

def send(self, message: str, metric_key: str) -> bool:
    ...
```

**Docstrings on every public class and function:**

```python
def load_config(yaml_path: str = "config/thresholds.yaml") -> dict:
    """Load operational config from YAML and merge secrets from .env.

    Args:
        yaml_path: Path to thresholds.yaml, relative to project root.

    Returns:
        Merged config dict with 'thresholds', 'auto_healing', and 'secrets' keys.
    """
```

**Exception handling with specific types and logged context:**

```python
# Catches the specific failure mode, logs actionable context, doesn't swallow the error silently
try:
    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()
except requests.exceptions.Timeout:
    logger.error("Slack webhook timed out after 10s", extra={"webhook_url": webhook_url})
except requests.exceptions.HTTPError as exc:
    logger.error("Slack webhook rejected payload", extra={"status": exc.response.status_code})
```

**Meaningful comments that add context, not noise:**

```python
# Avoid — obvious loop comment
for key, value in snapshot.items():

# Better — explains why this condition exists
# Load average spikes are transient; only alert if sustained across two consecutive cycles
if current_load > threshold and self._previous_load_breach:
```

---

## Planned Future Branches (Roadmap)

This section lists **example branch names** for upcoming work.

Actual branch names may differ when implemented — these are placeholders to show the roadmap direction.

| Branch | Planned Work |
|--------|--------------|
| `feat/ci-lint-test` | GitHub Actions: lint (flake8/black) + pytest execution against the existing `tests/` suite |
| `feat/ci-docker-trivy` | Docker build validation + Trivy CRITICAL-severity scan gate |
| `feat/aws-deployment` | ECS Fargate task definition, Terraform modules, Secrets Manager integration |

---

## Folder Conventions Summary

| Path | What Goes Here |
|------|----------------|
| `app/monitoring/` | One file per metric source, all extending `BaseMetricCollector` |
| `app/alerting/` | One file per channel, all extending `BaseAlertSender` |
| `app/healing/` | `base.py` for retry/cooldown logic; `actions.py` for the action registry |
| `app/utils/` | Stateless utilities (`config_loader`, `logger`) shared across all layers |
| `scripts/` | Production Bash scripts — no Python logic, only shell-level operations |
| `config/` | YAML files only — no secrets, safe to commit |
| `cron/` | Scheduling setup scripts only |
| `logs/` | Runtime output — git-ignored, never commit actual log files |
| `tests/` | pytest suite — `unit/` mirrors `app/` module structure (`monitoring/`, `alerting/`, `healing/`); `integration/` for full-cycle orchestration tests; `conftest.py` for shared fixtures |
| `docs/` | Markdown documentation — one file per topic |
