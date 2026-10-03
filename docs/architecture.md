# 🏗️ PhoenixAuto-Ops — System Architecture

This document covers the internal design of PhoenixAuto-Ops: component responsibilities, execution flow, design patterns, and extension points.

---

## High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                        PhoenixAuto-Ops Runtime                           │
│                                                                          │
│   cron / run_monitor.sh                                                  │
│           │                                                              │
│           ▼                                                              │
│     app/main.py  ───────────────────────────────────────────────────┐   │
│           │                                                          │   │
│           ▼                                                          │   │
│     app/engine.py  (MonitoringEngine)                               │   │
│     ┌────────────────────────────────────────────────────────────┐  │   │
│     │                                                            │  │   │
│     │  ┌─────────────────┐  ┌───────────────────┐  ┌─────────┐  │  │   │
│     │  │  monitoring/    │  │    alerting/       │  │healing/ │  │  │   │
│     │  │                 │  │                    │  │         │  │  │   │
│     │  │ SystemMetrics   │─▶│ TelegramAlertSender│─▶│ actions │  │  │   │
│     │  │ NetworkMetrics  │  │ SlackAlertSender   │  │   .py   │  │  │   │
│     │  │                 │  │ EmailAlertSender   │  │         │  │  │   │
│     │  └─────────────────┘  └───────────────────┘  └────┬────┘  │  │   │
│     │                                                    │       │  │   │
│     └────────────────────────────────────────────────────┼───────┘  │   │
│                                                          │           │   │
│                                                          ▼           │   │
│                                                  scripts/            │   │
│                                                  service_manager.sh  │   │
│                                                  cleanup.sh          │   │
│                                                                      │   │
│   ┌──────────────────────────────────────────────────────────────┐  │   │
│   │  app/utils/                                                  │  │   │
│   │  config_loader.py ← config/thresholds.yaml + .env           │  │   │
│   │  logger.py        → logs/phoenixauto_ops.log                 │◀─┘   │
│   └──────────────────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### `app/engine.py` — MonitoringEngine

`app/engine.py` is the central orchestrator. It loads configuration, creates the monitoring, alerting, and healing components, and runs the monitor → evaluate → alert → heal cycle for each run.

### `app/monitoring/` — Metrics Layer

`app/monitoring/` collects system and network metrics through a shared ABC contract.

| Class | File | Responsibility |
|-------|------|----------------|
| `BaseMetricCollector` | `base.py` | Defines the `collect()` contract |
| `SystemMetrics` | `system.py` | Collects CPU, memory, disk, and load average |
| `NetworkMetrics` | `network.py` | Collects TX/RX throughput and active connections |

`SystemMetrics.collect()` returns a consistent metric dictionary. Metrics are collected in a single pass to reduce timing differences between related values.

### `app/alerting/` — Alert Dispatch Layer

`app/alerting/` sends notifications through Telegram, Slack, and Email.

| Class | File | Channel |
|-------|------|---------|
| `BaseAlertSender` | `base.py` | Shared cooldown and formatting logic |
| `TelegramAlertSender` | `telegram.py` | Telegram Bot API |
| `SlackAlertSender` | `slack.py` | Incoming Webhook |
| `EmailAlertSender` | `email.py` | SMTP/TLS email delivery |

`BaseAlertSender` keeps a cooldown timestamp per metric key to prevent repeated alerts for the same metric within the cooldown window. Channel-specific classes only implement `_dispatch(payload)`.
Each channel's `_send()` returns `True` on an actual dispatch attempt and `False` when the channel is unconfigured and the send was intentionally skipped (missing credentials) - `send_alert()` only logs "Alert sent" and starts the cooldown timer on `True`, so a skipped channel is never misreported as delivered.

### `app/healing/` — Remediation Layer

`app/healing/` handles remediation actions such as service restarts and cleanup tasks.

| Class | File | Responsibility |
|-------|------|----------------|
| `BaseHealer` | `base.py` | Dry-run mode, retry logic, and cooldown handling |
| `HealingActions` | `actions.py` | Executes shell-based remediation scripts |

Implemented actions include service restart, cache cleanup, and log rotation. `kill_process()` treats `pkill`'s own exit code 1 ("no process matched") as success rather than a failure - the expected outcome on any cycle after a prior cycle already cleared the target, not a real error. Each sustained-breach healing action (CPU/memory/network) is executed in its own isolated `try/except` inside `_trigger_healing()`, so one action failing (e.g. `restart_service` with no matching systemd unit) does not prevent the other sustained breaches in the same cycle from getting their own healing attempt. All subprocess calls use a timeout so a stuck script does not block the monitoring cycle. When `auto_healing.dry_run` is enabled, actions are logged but not executed.

### `app/utils/` — Support Layer

`app/utils/` contains shared infrastructure helpers.

- `config_loader.py` loads `config/thresholds.yaml` and merges environment variables from `.env` into a single merged config dictionary.
- `logger.py` configures console logging and a rotating JSON file logger at `logs/phoenixauto_ops.log`.

---

## Execution Data Flow

```
Step 1 — COLLECT
  cron triggers scripts/run_monitor.sh
    └── calls python3 -m app.main
          └── MonitoringEngine instantiated with merged config
          └── SystemMetrics.collect()  → metric_snapshot dict
          └── NetworkMetrics.collect() → appended to snapshot

Step 2 — EVALUATE (streak-gated)
  engine compares each metric to its own thresholds.yaml value every cycle
    └── cpu_usage_percent 91.3 > threshold 85.0 → streak[cpu] += 1
    └── memory_usage_percent 78.2 < threshold 90.0 → streak[memory] = 0
  a metric only becomes a "sustained breach" once its streak reaches
  auto_healing.consecutive_breaches_required (default 3) - a single
  spiky cycle logs "streak 1/3" and takes no further action

Step 3 — ALERT (cooldown-aware, sustained breaches only)
  for each metric that just reached its required streak this cycle:
    └── TelegramAlertSender.send_alert(...) → checks cooldown → dispatches
    └── SlackAlertSender.send_alert(...)    → checks cooldown → dispatches
    └── EmailAlertSender.send_alert(...)    → checks cooldown → dispatches
  cooldown prevents re-alerting the same metric within cooldown_seconds,
  independent of the streak counter

Step 4 — HEAL (per-metric isolated, dry-run / retry-aware)
  if auto_healing.enabled, for each metric that just reached sustained breach:
    └── cpu_usage_percent  → identify real top-CPU process → restart_service(target)
    └── memory_usage_percent → clear_cache()
    └── network_connections  → kill_process("high-connection-process")
  each action runs in its own try/except - one action failing does not
  skip the others in the same cycle
    └── dry_run=true  → log intended action, return
    └── dry_run=false → subprocess.run(script, timeout=30)
          └── exit 0  → log success
          └── exit !=0 → retry up to max_retry_attempts
                └── exhausted → log error for that action only, continue

Step 5 — LOG
  all steps emit structured JSON to logs/phoenixauto_ops.log
  engine exits cleanly after each cycle.
```

---

## Key Design Principles

PhoenixAuto-Ops is designed around modularity, separation of concerns, and configuration-driven behavior.

- Monitoring, alerting, and healing are isolated into separate layers.
- Each layer exposes a small interface through abstract base classes.
- The system favors Linux-native tooling and minimal dependencies.
- Healing supports dry-run mode, retries, and cooldown control for safety.

---

## Known Limitations & Future Work

- **Single-node only**: the engine runs as one process on one machine. If
  that machine or process dies, monitoring stops. `scripts/watchdog.sh`
  mitigates this via an independent cron-based log-freshness check that
  can alert even when the main engine itself is down, but true
  high-availability would require a multi-node/leader-election setup.
- **No alert escalation**: a missed alert has no automatic escalation to
  a second responder. Acceptable for a single-operator setup; a team
  environment would need this.
- **No long-term trend storage**: metrics aren't persisted beyond the
  current log file - no historical dashboards or trend analysis across
  days/weeks (a time-series backend would add this).
- **Healing restart target is CPU-only dynamic**: `get_top_cpu_process()`
  identifies the real highest-CPU process to restart, but memory and
  network healing (`clear_cache`, `kill_process`) still act on fixed
  targets rather than diagnosing the specific cause.
- **Docker: `restart_service()` cannot succeed inside a container** - no
  systemd/PID 1 init and no `sudo` binary by design (see
  [docs/docker.md](docker.md#known-limitation)). Monitoring and alerting
  work correctly in Docker; `clear_cache`/`kill_process` also work since
  they don't depend on systemd.

---

## Design Patterns

### Abstract Base Classes

All collectors, alert senders, and healers follow abstract base class contracts so new components can be added without changing the engine.

### Configuration Access via Singleton

Every component accesses configuration through a single shared `ConfigLoader` singleton (`app.utils.config_loader.config`), constructed once at import time from `thresholds.yaml` and `.env`. No component builds its own config, and no component takes a config dict as a constructor argument — they all import and read the same instance.

This makes unit testing straightforward without needing real config files on disk: tests monkeypatch the singleton's `get()` and `get_threshold()` methods directly (see `tests/conftest.py`'s `patch_config` fixture) rather than passing in a mock object, since every component resolves config through that one shared reference regardless of how it was instantiated.

---

## Extension Points

New functionality can be added without changing the core orchestration logic.

- Add a new monitor by extending BaseMetricCollector and registering it in engine.py.
- Add a new alert channel by extending BaseAlertSender and implementing _dispatch().
- Add a new healing action by adding a shell script and mapping it inside HealingActions.

---

## Containerized Runtime

PhoenixAuto-Ops runs identically whether invoked by `cron` on bare metal or as a long-running process inside Docker — the `monitoring/ → alerting/ → healing/` cycle described above does not change. Containerization changes *how* the engine is invoked and *where* its metric sources point, not the engine itself.

```text
┌───────────────────────────────┐         ┌───────────────────────────────┐
│      Bare-Metal Path          │         │        Containerized Path     │
│                                │         │                                │
│  cron (*/5 * * * *)           │         │  docker-compose up             │
│    └── run_monitor.sh          │         │    └── ENTRYPOINT python       │
│          └── python3 -m app.main         │          └── -m app.main       │
│                └── one cycle, exit        │                └── run_forever()│
│                                │         │                    (continuous) │
└───────────────────────────────┘         └───────────────────────────────┘
              │                                          │
              └──────────────────┬───────────────────────┘
                                  ▼
                    Same MonitoringEngine cycle:
                    collect → evaluate → alert → heal → log
```

Two things differ at the edges of this same cycle when running in a container:

**Invocation model.** `cron/setup_cron.sh` re-invokes `app/main.py` every 5 minutes for a single cycle, then exits. The container instead runs `MonitoringEngine.run_forever()` continuously — `cron` has no role inside a container, since the engine already loops on its own via `cycle_interval_seconds`.

**Metric source.** By default, `SystemMetrics` and `NetworkMetrics` (see [`app/monitoring/`](#appmonitoring--metrics-layer) above) read `/proc` for whichever namespace they're running in. On bare metal that's already the host. Inside a container, `psutil.PROCFS_PATH` is redirected to a bind-mounted copy of the host's `/proc` (`HOST_PROC_PATH`/`HOST_ROOT_PATH`), so the same `SystemMetrics.collect()` contract keeps returning host-level numbers rather than container-namespace numbers. `BaseMetricCollector`'s interface is untouched — only the underlying file path `psutil` reads from changes.

Full Dockerfile stages, `docker-compose.yml` service definition, host-mount design, and a known platform limitation identified during testing → **[docs/docker.md](docker.md)*

---

## Security Model

| Concern | Mitigation |
|---------|------------|
| Secrets exposure | Credentials stay in `.env` and out of YAML. |
| Privilege escalation | Sudoers allow only required healing commands. |
| Alert storms | Per-sender cooldown limits repeated notifications. |
| Healing loops | Retry limits and cooldowns prevent repeated failures. |
| Subprocess injection | Script paths are hardcoded and not user-controlled. |
