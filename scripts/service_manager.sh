#!/usr/bin/env bash
# ======================================================================
# PhoenixAuto-Ops: Service Manager Script
# Purpose:  Safely start/stop/restart/status systemd services.
#           Called from Python healing module via subprocess.
# Usage:    sudo ./service_manager.sh <action> <service_name>
# ======================================================================

set -euo pipefail

ACTION="$1"
SERVICE="$2"

# Log file (project-local for simplicity, can change to /var/log later)
LOG_FILE="logs/service_manager.log"

# Simple logging function
log() {
    local level="$1"
    local message="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message" | tee -a "$LOG_FILE"
}

# Validation
if [[ -z "$ACTION" || -z "$SERVICE" ]]; then
    log "ERROR" "Usage: $0 {start|stop|restart|status} <service_name>"
    exit 1
fi

# Allowed actions only
case "$ACTION" in
    start|stop|restart|status) ;;
    *)
        log "ERROR" "Invalid action: $ACTION. Allowed: start, stop, restart, status"
        exit 1
        ;;
esac

# Check if service exists
if ! systemctl cat "$SERVICE" &>/dev/null; then
    log "ERROR" "Service '$SERVICE' does not exist"
    exit 1
fi

log "INFO" "Starting action: $ACTION on service $SERVICE"

# Execute the command
if sudo systemctl "$ACTION" "$SERVICE" 2>&1 | tee -a "$LOG_FILE"; then
    log "SUCCESS" "$ACTION completed successfully for $SERVICE"
    exit 0
else
    log "ERROR" "Failed to $ACTION $SERVICE (exit code $?)"
    exit 1
fi