# 🚀 PhoenixAuto-Ops — Setup Guide

Complete installation, configuration, and verification guide for running PhoenixAuto-Ops on a Linux server.

---

## Prerequisites

Before starting, confirm the following are available on your server:

| Requirement | Minimum Version | Check Command |
|-------------|-----------------|---------------|
| Linux | Ubuntu 20.04+, Debian 12+, RHEL/Rocky Linux equivalent | `lsb_release -a` |
| Python | 3.10+ | `python3 --version` |
| Bash | 5.0+ | `bash --version` |
| systemd | Any modern | `systemctl --version` |
| sudo access | Required for setup and healing actions | `sudo -l` |
| Git | Any | `git --version` |

**At least one alert channel is required:**

| Channel | What You Need |
|---------|---------------|
| Telegram | Bot token (from @BotFather) + chat ID |
| Slack | Incoming Webhook URL (from Slack App config) |
| Email | SMTP host, port, authenticated username + app password |

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/<your-username>/phoenixauto-ops.git
cd phoenixauto-ops
```

---

## Step 2 — Run the Bootstrap Script

`setup.sh` automates virtual environment creation, dependency installation, and script permission setup in one shot:

```bash
chmod +x setup.sh
sudo ./setup.sh       # Use `sudo` because the script sets execute permissions and may perform system-level setup tasks.
```

What it does:
- Creates `venv/` with `python3 -m venv venv`
- Activates the venv and installs all packages from `requirements.txt`
- Sets execute permissions on all scripts in `scripts/` and `cron/`

After it completes, your venv is ready and `.env` is waiting to be populated.

---

## Step 3 — Configure Secrets

Open `.env` and fill in credentials for at least one alert channel:

```bash
nano .env
```

```dotenv
# ─── Telegram Alerting ────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_CHAT_ID=<your_chat_id>

# ─── Slack Alerting ───────────────────────────────────────────────
SLACK_WEBHOOK_URL=<your_slack_webhook_url>

# ─── Email Alerting (SMTP/TLS) ────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<your_email_address>
SMTP_PASSWORD=<your_app_password>
ALERT_EMAIL_RECIPIENTS=<your_email1>,<your_email2>
```

> **Security:** `.env` is listed in `.gitignore`. Always confirm it is not staged before committing:
> ```bash
> git status   # .env must NOT appear in the output
> ```

To get a Telegram chat ID: message your bot, then visit  
`https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and read the `chat.id` field.

---

## Step 4 — Configure Thresholds

Edit `config/thresholds.yaml` to match your server's expected baseline load:

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

**Recommended starting point:** keep `dry_run: true` until you verify the logs and confirm expected healing behavior.

---

## Step 5 — Grant Sudoers Permission for Healing Actions

The healing engine needs elevated privileges to restart services and flush system cache. We grant minimum required permissions only.

Run the following command:

```bash
sudo visudo -f /etc/sudoers.d/phoenixautoops
```

Add these lines (replace `youruser` with your actual Linux username):

```bash
# PhoenixAuto-Ops — Limited sudo for healing actions
youruser ALL=(ALL) NOPASSWD: /bin/systemctl restart *
youruser ALL=(ALL) NOPASSWD: /bin/systemctl status *
youruser ALL=(ALL) NOPASSWD: /path/to/phoenixauto-ops/scripts/cleanup.sh
youruser ALL=(ALL) NOPASSWD: /path/to/phoenixauto-ops/scripts/service_manager.sh
```

Save and verify the file syntax:

```bash
sudo visudo -c -f /etc/sudoers.d/phoenixautoops
# Expected output: /etc/sudoers.d/phoenixautoops: parsed OK
```

Set correct permissions on the sudoers file:

```bash
sudo chmod 440 /etc/sudoers.d/phoenixautoops
```

> **Principle of least privilege:** these rules allow only the specific commands PhoenixAuto-Ops needs. Never use `NOPASSWD: ALL` for a monitoring process.

---

## Step 6 — Set Up Cron Job

Install the crontab entry with the idempotent setup script:

```bash
bash cron/setup_cron.sh
```

Verify the entry was added:

```bash
crontab -l | grep phoenixauto-ops
```

Expected output:

```
*/5 * * * * /path/to/phoenixauto-ops/scripts/run_monitor.sh >> /path/to/logs/phoenixauto_ops.log 2>&1
```

The default interval is every 5 minutes. To change it, edit `CRON_SCHEDULE` in `cron/setup_cron.sh` before running:

```bash
# Default is every 5 minutes; change only if you want a different interval.
CRON_SCHEDULE="*/5 * * * *"   # Every 5 minutes
```

---

## Step 7 — Verify the Full Stack

**Run a one-shot cycle manually:**

```bash
source venv/bin/activate
python3 -m app.main
```

Expected console output:

```
2025-06-09 14:32:07 INFO  [engine] Starting monitoring cycle
2025-06-09 14:32:07 INFO  [system_metrics] cpu=72.4% memory=68.1% disk[/]=76.0%
2025-06-09 14:32:07 INFO  [engine] No thresholds breached — cycle complete
```

**Watch live JSON logs:**

```bash
tail -f logs/phoenixauto_ops.log
```

**Test via the production wrapper:**

```bash
bash scripts/run_monitor.sh
```

**Verify alerting works** by temporarily lowering a threshold in `thresholds.yaml` below your current value (e.g., set `cpu_usage_percent: 1.0`), running `python3 -m app.main`, then restoring the real threshold. You should receive an alert on your configured channel.

---

## Common Setup Errors

### `systemctl` path not found

```
sudo: /bin/systemctl: command not found
```

**Fix:** Check whether `systemctl` is at `/bin/systemctl` or `/usr/bin/systemctl` on your distro:

```bash
which systemctl
```

Update the path in `/etc/sudoers.d/phoenixauto-ops` to match. Re-run `sudo visudo -c -f /etc/sudoers.d/phoenixauto-ops` to validate.

### `ModuleNotFoundError: No module named 'psutil'`

The virtual environment is not activated, or `requirements.txt` was not installed into it.

**Fix:**

```bash
source venv/bin/activate
pip install -r requirements.txt
python3 -c "import psutil; print('OK')"
```

If running via cron and seeing this error in logs, confirm `run_monitor.sh` is activating `venv/` using an **absolute path**:

```bash
# Correct in run_monitor.sh — absolute path, not relative
source /home/youruser/phoenixauto-ops/venv/bin/activate
```

### Cron job not appearing in `crontab -l`

**Fix:**

```bash
# Confirm the script is executable
ls -la cron/setup_cron.sh

# Run manually and check output
bash cron/setup_cron.sh

# Check for errors in script output — common cause is missing $PROJECT_ROOT detection
```

### Telegram alert not delivered — no errors in logs

The bot has not been started by the chat recipient. In Telegram, send any message to your bot directly (or add it to a group and send `/start`) before expecting it to deliver messages to that `TELEGRAM_CHAT_ID`.

Also confirm your bot has not been blocked — test via:

```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
# Should return {"ok":true,"result":{"username":"your_bot_name",...}}
```

### `logs/` directory not found

The `logs/` directory is tracked via `.gitkeep` but the directory itself must exist at runtime:

```bash
mkdir -p logs
```

`setup.sh` handles this automatically. If you skipped `setup.sh` and ran `python3 -m app.main` directly, create the directory manually.

---

## Uninstalling the Cron Job

```bash
# Remove only the PhoenixAuto-Ops entry from crontab
crontab -l | grep -v phoenixauto-ops | crontab -
crontab -l   # Confirm it's gone
```

---

## Supported Platforms

**Tested On:**

- Ubuntu 22.04
- Ubuntu 24.04

**Expected To Work On:**

- Debian 12
- Linux Mint
- Rocky Linux
