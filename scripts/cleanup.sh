#!/usr/bin/env bash
# ======================================================================
# PhoenixAuto-Ops: Cleanup Script
# Purpose:  Safe cleanup of cache, temp files, and old project logs.
#           Called from Python healing module.
# Usage:    sudo ./cleanup.sh
# ======================================================================

set -euo pipefail

LOG_FILE="logs/cleanup.log"
PROJECT_LOG_DIR="./logs"
MAX_LOG_AGE_DAYS=7

# Logging function
log() {
    local level="$1"
    local message="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message" | tee -a "$LOG_FILE"
}

log "INFO" "Starting cleanup process"

# 1. Clear APT cache (if Debian/Ubuntu)
if command -v apt-get &>/dev/null; then
    log "INFO" "Cleaning APT cache"
    sudo apt-get clean -y || log "WARNING" "APT clean failed (non-critical)"
fi

# 2. Drop page cache (requires root)
log "INFO" "Dropping page cache"
echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || log "WARNING" "Cache drop failed"

# 3. Clean old project logs
if [[ -d "$PROJECT_LOG_DIR" ]]; then
    log "INFO" "Removing project logs older than $MAX_LOG_AGE_DAYS days"
    find "$PROJECT_LOG_DIR" -type f -name "*.log" -mtime +"$MAX_LOG_AGE_DAYS" -delete || true
else
    log "WARNING" "Project log directory not found"
fi

# 4. Clean /tmp (old files only)
log "INFO" "Cleaning old files in /tmp"
sudo find /tmp -type f -atime +1 -delete 2>/dev/null || true

log "SUCCESS" "Cleanup process finished successfully"
exit 0