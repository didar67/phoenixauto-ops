#!/usr/bin/env bash
# ======================================================================
# PhoenixAuto-Ops: Watchdog Script
# Purpose: Detect if the main monitoring engine has stopped writing logs
#           (crashed, hung, or killed) - runs independently via its own
#           cron entry, so a dead engine can still trigger a notification.
# Usage:   ./watchdog.sh
# ======================================================================

set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

LOG_FILE="$PROJECT_ROOT/logs/phoenixauto-ops.log"
STALE_MINUTES=5
WATCHDOG_LOG="$PROJECT_ROOT/logs/watchdog.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$WATCHDOG_LOG"
}

if [[ ! -f "$LOG_FILE" ]]; then
    log "ERROR: $LOG_FILE does not exist - engine may never have started"
    exit 1
fi

if [[ -z "$(find "$LOG_FILE" -mmin -"$STALE_MINUTES")" ]]; then
    log "ALERT: No log activity in $STALE_MINUTES minutes - engine appears down"

    # .env is loaded separately by ConfigLoader for the Python app; this
    # script reads the webhook directly since it runs standalone via cron,
    # outside the app's own process.
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        # shellcheck disable=SC1091
        source "$PROJECT_ROOT/.env"
    fi

    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        curl -s -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"⚠️ PhoenixAuto-Ops watchdog: no log activity in ${STALE_MINUTES} min on $(hostname) - engine may be down\"}" \
            "$SLACK_WEBHOOK_URL" > /dev/null || log "WARNING: failed to send watchdog alert to Slack"
    else
        log "WARNING: SLACK_WEBHOOK_URL not set - cannot send watchdog alert"
    fi

    exit 1
fi

log "OK: engine log is fresh"
exit 0
