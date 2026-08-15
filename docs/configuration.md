# ⚙️ PhoenixAuto-Ops — Configuration Reference

PhoenixAuto-Ops uses a two-layer configuration system: a YAML file for operational parameters and a `.env` file for runtime secrets. This document covers every configurable value, how the two layers are merged at runtime, and best practices for managing config across environments.

---

## Configuration Layers

| File | Contains | Commit to Git? |
|------|----------|----------------|
| `config/thresholds.yaml` | Metric thresholds and healing flags | Yes |
| `.env` | API tokens, webhook URLs, SMTP credentials | No |

---

## Configuration Flow

```text
  thresholds.yaml
        │
        ▼
  config_loader.py
        │
        ▼
   merged config
        │
        ▼
    monitoring
     alerting
     healing
```

---

## `config/thresholds.yaml` — Full Reference

### Parameter Reference

| Key | Default | Type | Description |
|-----|---------|------|-------------|
| `thresholds.cpu_usage_percent` | `85.0` | float | Aggregate CPU utilization % above which an alert is dispatched |
| `thresholds.memory_usage_percent` | `90.0` | float | RAM usage % (used / total) that triggers an alert |
| `thresholds.disk_usage_percent` | `80.0` | float | Usage % on any single mount point that triggers an alert |
| `thresholds.load_average_limit` | `4.0` | float | 1-minute load average above which an alert fires |
| `thresholds.network.max_connections` | `500` | int | Total active TCP connections above which an alert is dispatched |
| `thresholds.network.latency_ms` | `200` | int | Round-trip latency threshold in milliseconds that triggers an alert |
| `auto_healing.enabled` | `true` | bool | Master switch — `false` disables the entire healing layer |
| `auto_healing.dry_run` | `false` | bool | When `true`, logs intended actions without executing shell scripts |
| `auto_healing.max_retry_attempts` | `3` | int | How many times a failed healing action is retried before giving up |
| `auto_healing.cooldown_seconds` | `300` | int | Minimum seconds between repeated healing for the same trigger type |

### Threshold Tuning Guide

**CPU (`cpu_usage_percent`):** On application servers under normal load, CPU typically stays below 60–70%. Set the threshold to leave a 15–20% buffer before the server becomes genuinely unresponsive. For batch-job servers that legitimately spike, consider `92.0`.

**Memory (`memory_usage_percent`):** Linux uses free RAM for cache, so `used/total` alone can look high. Values above 90% usually indicate real memory pressure.

**Disk (`disk_usage_percent`):** `80.0` leaves approximately 20% headroom, which is the widely used operations standard. Set lower (`70.0`) on small-volume servers where 10GB free makes a meaningful difference.

**Load average (`load_average_limit`):** Compare the threshold with CPU core count. As a rule of thumb, a starting point around 80% of core count is reasonable.

---

## `.env` — Full Reference

### Complete File

```dotenv
# .env — runtime secrets for PhoenixAuto-Ops
# Copy from .env.example: cp .env.example .env
# This file is listed in .gitignore — NEVER commit it.

# ─── Telegram Alerting ────────────────────────────────────────────────────────
# Get BOT_TOKEN from @BotFather in Telegram.
# Get CHAT_ID by messaging your bot and checking:
# https://api.telegram.org/bot<TOKEN>/getUpdates → result[0].message.chat.id
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_CHAT_ID=<your_chat_id>

# ─── Slack Alerting ───────────────────────────────────────────────────────────
# Create an Incoming Webhook at: https://api.slack.com/apps → Incoming Webhooks
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/xxxxxxxxxxxxxxxxxxxx

# ─── Email Alerting (SMTP/TLS) ────────────────────────────────────────────────
# For Gmail: use an App Password, not your account password.
# Generate at: https://myaccount.google.com/apppasswords
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@yourdomain.com
SMTP_PASSWORD=your_app_password_here
ALERT_EMAIL_RECIPIENTS=ops@yourdomain.com,oncall@yourdomain.com
```

### Variable Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | If using Telegram | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | If using Telegram | Target chat or group ID (negative = group) |
| `SLACK_WEBHOOK_URL` | If using Slack | Full Incoming Webhook URL from Slack App config |
| `SMTP_HOST` | If using Email | SMTP server hostname |
| `SMTP_PORT` | If using Email | Usually `587` (STARTTLS) or `465` (SSL) |
| `SMTP_USER` | If using Email | Authenticated sender address |
| `SMTP_PASSWORD` | If using Email | App password or SMTP relay credential |
| `ALERT_EMAIL_RECIPIENTS` | If using Email | Comma-separated list of recipient addresses |

At least one alert channel must be fully configured for PhoenixAuto-Ops to deliver notifications. Unconfigured channels are skipped at runtime with a `WARNING` log entry.

---

## Container-Specific Environment Variables

These are only relevant when running via `docker-compose.yml` — they have no effect in the venv-based setup and are not part of `.env`.

| Variable | Required | Description |
|----------|----------|--------------|
| `HOST_PROC_PATH` | Docker only | Path to the host's bind-mounted `/proc` (e.g. `/host/proc`). When set, `psutil.PROCFS_PATH` is overridden so CPU/memory/network metrics reflect the host, not the container's own namespace. |
| `HOST_ROOT_PATH` | Docker only | Path to the host's bind-mounted `/` (e.g. `/rootfs`). Used for disk usage checks instead of the container's overlay filesystem. |

Full explanation of why these are needed and how the mounts work → **[docs/docker.md](docs/docker.md#host-level-monitoring)**

---

## How `config_loader.py` Merges Both Layers

`load_config()` in `app/utils/config_loader.py` constructs the unified config dict that every component receives at instantiation:

The loader:

- Loads thresholds from YAML
- Loads secrets from .env
- Merges both sources
- Returns a unified configuration dictionary

Components access credentials via `config.get('telegram.bot_token')` — no direct `os.environ` calls outside `config_loader.py`. This keeps secret access centralized and makes unit testing straightforward in the future (pass a mock config dict).

---

## Environment-Specific Configuration

PhoenixAuto-Ops does not have a built-in environment flag, but the two-layer design makes per-environment configuration easy to manage:

**Development server** — higher thresholds, dry-run enabled, single alert channel:

```yaml
thresholds:
  cpu_usage_percent: 95.0
  memory_usage_percent: 95.0
  disk_usage_percent: 90.0
  load_average_limit: 8.0

network:
  max_connections: 400
  latency_ms: 100

auto_healing:
  enabled: true
  dry_run: true
  max_retry_attempts: 1
  cooldown_seconds: 60
```

**Production server** — tighter thresholds, healing enabled, all channels active:

```yaml
thresholds:
  cpu_usage_percent: 80.0
  memory_usage_percent: 85.0
  disk_usage_percent: 90.0
  load_average_limit: 4.0
  
network:
  max_connections: 600
  latency_ms: 200

auto_healing:
  enabled: true
  dry_run: false
  max_retry_attempts: 3
  cooldown_seconds: 300
```

---

## 🔒 Configuration Security Checklist

Before every `git push`, run through this checklist:

```bash
# 1. Confirm .env is not staged
git status
# .env must NOT appear — if it does: git rm --cached .env

# 2. Confirm .gitignore is covering .env
grep "^\.env$" .gitignore
# Expected output: .env

# 3. Confirm no secrets appear in thresholds.yaml
grep -v "^#" config/thresholds.yaml | grep -i "token\|password\|webhook\|secret" 
# Expected: no output

# 4. Confirm venv/ is not being committed
git status | grep "venv/"
# Expected: no output
```

**If `.env` was accidentally committed in a prior commit:**

```bash
# Remove from tracking without deleting the local file
git rm --cached .env
git commit -m "Remove accidentally tracked .env secrets file"

# Immediately rotate all credentials that were exposed:
# - Regenerate Telegram bot token via @BotFather
# - Rotate Slack webhook URL in Slack App settings
# - Revoke and regenerate Gmail App Password
```

---

## Best Practices Summary

- **Cooldown asymmetry:** Set `auto_healing.cooldown_seconds` higher than the alerting cooldown in `BaseAlertSender`. Alerting at 300s intervals is fine; triggering a service restart every 5 minutes on a flapping service is a remediation loop. Use 600s or higher for healing cooldowns on production.

- **Validate dry-run first:** Every time `thresholds.yaml` is changed on a production server, temporarily set `dry_run: true`, run one cycle, inspect `logs/phoenixauto_ops.log` to confirm which actions would have fired, then restore `dry_run: false`.

- **Mount-specific disk thresholds:** The current `disk_usage_percent` threshold applies to all mount points. If `/data` is a high-churn volume and `/` is stable, adjust the threshold upward and add a note in the YAML explaining why.

- **App password over account password:** For Gmail SMTP, an App Password is scoped to a single app and can be individually revoked without changing your account password. Never use your Google account password as `SMTP_PASSWORD`.
