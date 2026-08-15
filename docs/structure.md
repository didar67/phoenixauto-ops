# 📁 PhoenixAuto-Ops — Project Structure

This document explains every folder and file in the repository: what it does, why it exists, and how it fits into the system.

---

## Full Tree

```
phoenixauto-ops/
│
├── app/                            # All Python application code
│   ├── __init__.py
│   ├── main.py                     # Entry point — loads config and starts MonitoringEngine
│   ├── engine.py                   # Core orchestration: collect → evaluate → alert → heal
│   │
│   ├── monitoring/                 # Metric collection layer
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseMetricCollector ABC — collect() interface contract
│   │   ├── system.py               # SystemMetrics: CPU, memory, disk, load average
│   │   └── network.py              # NetworkMetrics: TX/RX throughput and active connections
│   │
│   ├── alerting/                   # Alert dispatch layer
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseAlertSender: in-memory cooldown logic, message formatting
│   │   ├── telegram.py             # TelegramAlertSender: Bot API sendMessage
│   │   ├── slack.py                # SlackAlertSender: Incoming Webhook POST
│   │   └── email.py                # EmailAlertSender: SMTP/TLS via smtplib
│   │
│   ├── healing/                    # Auto-remediation layer
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseHealer: dry-run flag, retry loop, cooldown
│   │   └── actions.py              # HealingActions: maps breach types → shell scripts
│   │
│   └── utils/                      # Shared infrastructure utilities
│       ├── config_loader.py        # Loads `thresholds.yaml` and `.env` into one merged config dict
│       └── logger.py               # JSON formatter + Console Logging + RotatingFileHandler setup
│
├── scripts/                        # Production Bash scripts for system-level operations
│   ├── service_manager.sh          # systemctl wrapper with input validation and logging
│   ├── cleanup.sh                  # Disk/cache cleanup and temporary file maintenance
│   ├── run_monitor.sh              # Cron-safe runner: activates venv and runs `python3 -m app.main`
│   └── .gitkeep
│
├── cron/                           # Scheduling setup
│   ├── setup_cron.sh               # Idempotent crontab installer
│   └── .gitkeep
│
├── config/
│   └── thresholds.yaml             # All metric thresholds + auto_healing flags
│
├── logs/                           # Runtime log output — git-ignored, directory tracked
│   └── .gitkeep
│
├── docs/                           # Technical documentation
│   ├── architecture.md             # System design, data flow, design patterns
│   ├── structure.md                # This file — folder and file explanations
│   ├── setup.md                    # Full installation guide
│   ├── configuration.md            # thresholds.yaml and .env complete reference
│   └── development-workflow.md     # Git branching strategy, code standards, and roadmap
│   └── docker.md                   # Dockerfile, docker-compose.yml, host monitoring, known limitations
├── Dockerfile                      # Multi-stage build: builder (gcc/psutil compile) → runtime (non-root)
├── docker-compose.yml              # phoenixops service: env, volumes, host-monitoring mounts, healthcheck
├── .dockerignore                   # Excludes .env, secrets, venv/, tests/ from build context
│
├── venv/                           # Python virtual environment — generated locally, git-ignored
├── .env                            # Runtime secrets — git-ignored, NEVER commit
├── .env.example                    # Secret template — safe to commit, no real values
├── .gitignore
├── requirements.txt
├── setup.sh                        # One-command bootstrap script
└── README.md                       # Project overview, quick start, and entry points
```

---

## File-by-File Explanation

### `app/main.py`

Entry point invoked by `scripts/run_monitor.sh` and direct `python3 -m app.main` calls. Responsible for:

- Loading the merged config via `config_loader`
- Instantiating `MonitoringEngine`
- Handling top-level exceptions so the process exits with a meaningful code (used by the cron wrapper to detect failures)

Does not contain business logic — that all lives in `engine.py`.

### `app/engine.py`

The brain of PhoenixAuto-Ops. `MonitoringEngine` drives a single execution cycle:

1. Collect metric snapshot from all enabled monitors
2. Evaluate each metric against its configured threshold
3. Dispatch alerts through all enabled channels for breached metrics
4. Trigger healing actions for breaches that have healing configured

Keeps the orchestration logic thin and delegates all implementation details to the respective layers. Each layer is instantiated fresh per run — no stale state carries between cron invocations.

### `app/monitoring/base.py`

Defines `BaseMetricCollector` as an abstract base class. The only contract it enforces is:

```python
def collect(self) -> dict:
    """Return a metric snapshot as a flat or nested dict."""
```

Any class that inherits `BaseMetricCollector` must implement `collect()`. This makes it possible to add new metric sources (database, Redis, custom endpoints) without touching the engine or alerting layers.

### `app/monitoring/system.py`

`SystemMetrics` implements CPU utilization, memory pressure, per-mount disk usage, and system load average using `psutil`. All readings are collected in a single pass to minimize time skew between related values.

### `app/monitoring/network.py`

`NetworkMetrics` collects network activity metrics used for threshold evaluation and alert generation.

### `app/alerting/base.py`

`BaseAlertSender` handles everything that is common across all channels:
- Cooldown enforcement (in-memory, per-process)
- Message formatting (`format_message()` produces a consistent alert body)
- Logging of sent/skipped decisions at appropriate levels

Subclasses implement only `_dispatch(payload)` — the channel-specific HTTP or SMTP call.

### `app/alerting/telegram.py`, `slack.py`, `email.py`

Each file contains exactly one class that extends `BaseAlertSender` and implements `_dispatch()` for its channel:
- `TelegramAlertSender` — POST to `https://api.telegram.org/bot{token}/sendMessage`
- `SlackAlertSender` — POST JSON payload to Incoming Webhook URL
- `EmailAlertSender` — SMTP connection with STARTTLS, authenticated send via `smtplib`

Credentials are read from the config dict (sourced from `.env`), never hardcoded.

### `app/healing/base.py`

`BaseHealer` wraps all healing execution with:
- **Dry-run check** — if `config.auto_healing.dry_run` is true, log and return without executing
- **Retry loop** — calls `_execute()` up to `max_retry_attempts`, sleeps between attempts
- **Cooldown check** — won't re-execute the same action within `cooldown_seconds`
- **Result logging** — logs success/failure with action name, attempt number, and exit code

### `app/healing/actions.py`

`HealingActions` maps breach types (strings like `"high_cpu"`, `"service_down"`) to shell scripts in `scripts/`. Uses `subprocess.run()` with a `timeout` and captures both `stdout` and `stderr` for logging. All script paths are module-level constants — no dynamic string construction that could introduce injection risk.

### `app/utils/config_loader.py`

`load_config(yaml_path)` function:
1. Reads and parses `config/thresholds.yaml` with `pyyaml`
2. Calls `python-dotenv`'s `load_dotenv()` to populate `os.environ` from `.env`
3. Merges environment variables into the config dict under a `secrets` key
4. Returns the unified dict — callers never need to touch `os.environ` directly

### `app/utils/logger.py`

`setup_logger(name)` configures:
- A `StreamHandler` with a human-readable formatter for console output
- A `RotatingFileHandler` writing with daily rotation JSON to `logs/phoenixauto_ops.log` (7 backups)

The JSON formatter adds `timestamp`, `level`, `component`, and `message` keys to every record. Any `extra={}` dict passed to a log call is merged into the JSON object, enabling structured context like `{"metric": "cpu_percent", "value": 91.3}`.

### `scripts/service_manager.sh`

A `systemctl` wrapper that:
- Validates the target service name before calling `systemctl`
- Captures stdout/stderr and exits with the original exit code
- Supports `restart`, `stop`, `start`, `status` subcommands
- Has a `--dry-run` flag that mirrors the Python-layer dry-run for shell-level testing

Called by `HealingActions` for service restart remediation.

### `scripts/cleanup.sh`

Handles disk-level cleanup:
- Removes files in `/tmp` older than N days, truncates oversized log files
- Calls `/proc/sys/vm/drop_caches` (requires sudo)
- Prints what would be deleted/flushed without making changes
- Reports total bytes freed in its stdout, captured by the calling Python layer

### `scripts/run_monitor.sh`

Production-safe cron entry point:
1. Activates `venv/` relative to the script's directory
2. Sources `.env` for any shell-level variable needs
3. Executes the application as a Python module using `python3 -m app.main` to properly resolve relative imports

### `cron/setup_cron.sh`

Reads the current user's crontab, checks whether a PhoenixAuto-Ops entry already exists (grep on a comment marker), and adds the job only if absent. This makes it safe to re-run after updates without creating duplicate entries. Default schedule is `*/5 * * * *` — configurable by editing the script variable `CRON_SCHEDULE` before running.

### `config/thresholds.yaml`

The single source of truth for all operational parameters. Controls metric thresholds, healing enable/disable, dry-run mode, retry counts, and cooldown windows. Safe to commit — contains no secrets. See **[docs/configuration.md](docs/configuration.md)** for the full reference.

### `Dockerfile`

Multi-stage build. Stage 1 (`builder`) installs `psutil`'s C-extension build dependencies (`gcc`) and pip-installs into `--user` site-packages — these tools never reach the runtime image. Stage 2 copies only the installed packages, runs as a dedicated non-root user (`phoenixops`, uid 1000), supports host-level system monitoring via mounted `/proc`, defines the container's `HEALTHCHECK`, `org.opencontainers.image.*` metadata labels and starts the engine via `ENTRYPOINT ["python"]` / `CMD ["-u", "-m", "app.main"]`. See **[docs/docker.md](docs/docker.md)** for the full build breakdown.

### `docker-compose.yml`

Defines the `phoenixops` service: env vars (including `HOST_PROC_PATH`/`HOST_ROOT_PATH` for host-system monitoring), volume mounts for config/logs/`.env`, resource limits, and lifecycle settings (`restart`, `stop_grace_period`). Inherits the Dockerfile's `HEALTHCHECK` rather than redefining it. See **[docs/docker.md](docs/docker.md)**.

### `.dockerignore`

Excludes `.env`, `config/secrets.yaml`, `venv/`, `tests/`, and `docs/` from the build context — mirrors the intent of `.gitignore` keeps secrets out even if a future `COPY . .` is added by mistake.

### `.env` / `.env.example`

`.env` holds all secrets: API tokens, webhook URLs, SMTP passwords. It is listed in `.gitignore` and must never be committed. `.env.example` is the committed template — it contains all required variable names with placeholder values so contributors know what to populate.

### `setup.sh`

Bootstrap script that prepares the local development environment.

See [docs/setup.md](docs/setup.md) for full details.

Running `./setup.sh` is the only step needed before configuration.
