#!/usr/bin/env bash
# ======================================================================
# PhoenixAuto-Ops: Cron Setup Script
# Purpose: Automatically and safely adds cronjob using dynamic paths.
# ======================================================================

set -euo pipefail

# Get absolute path of the project root and wrapper
PROJECT_DIR=$(cd "$(dirname "$0")/.." && pwd)
WRAPPER_SCRIPT="$PROJECT_DIR/scripts/run_monitor.sh"
LOG_DIR="$PROJECT_DIR/logs"

log() {
    local level="$1"
    local msg="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $msg"
}

log "INFO" "Starting cron setup process"

# Create logs directory if missing
mkdir -p "$LOG_DIR"

# Define Cron Job (Every 5 minutes is standard for monitoring)
CRON_JOB="*/5 * * * * $WRAPPER_SCRIPT"

# Check if cronjob already exists
if crontab -l 2>/dev/null | grep -Fq "$WRAPPER_SCRIPT"; then
    log "INFO" "Cronjob already exists. Skipping."
    exit 0
fi

# Add cronjob safely
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

if crontab -l | grep -Fq "$WRAPPER_SCRIPT"; then
    log "SUCCESS" "Cronjob added successfully: $CRON_JOB"
    exit 0
else
    log "ERROR" "Failed to add cronjob"
    exit 1
fi