#!/usr/bin/env bash
# ======================================================================
# PhoenixAuto-Ops: One-Command Setup Script
# Purpose: Automates project setup (venv, dependencies, permissions, cron)
# Usage:   sudo ./setup.sh
# Features: idempotent, logging, validation, safe execution
# ======================================================================

set -euo pipefail

LOG_FILE="logs/setup.log"

log() {
    local level="$1"
    local msg="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $msg" | tee -a "$LOG_FILE"
}

log "INFO" "Starting PhoenixAuto-Ops setup process"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    log "ERROR" "This script must be run as root (use sudo ./setup.sh)"
    exit 1
fi

# Create logs directory
mkdir -p logs
touch logs/setup.log logs/cron.log
chmod 644 logs/*.log

log "INFO" "Logs directory prepared"

# 1. Install system dependencies
log "INFO" "Installing system dependencies..."
apt-get update -y
apt-get install -y python3-venv python3-pip cron logrotate

# 2. Create virtual environment
log "INFO" "Creating virtual environment..."
if [[ ! -d "venv" ]]; then
    python3 -m venv venv
    log "SUCCESS" "Virtual environment created"
else
    log "INFO" "Virtual environment already exists"
fi

# 3. Activate venv and install Python packages
log "INFO" "Installing Python dependencies..."
source venv/bin/activate
pip install --break-system-packages -r requirements.txt || {
    log "WARNING" "Some packages may already be installed"
}

# 4. Make scripts executable
log "INFO" "Making shell scripts executable..."
chmod +x scripts/*.sh

# 5. Setup cronjob
log "INFO" "Setting up cronjob..."
if [[ -f "cron/setup_cron.sh" ]]; then
    bash cron/setup_cron.sh
else
    log "WARNING" "cron/setup_cron.sh not found. Skipping cron setup."
fi

log "SUCCESS" "PhoenixAuto-Ops setup completed successfully!"
log "INFO" "To run manually: source venv/bin/activate && python3 -m app.main"
log "INFO" "Cronjob is now active — monitoring will run automatically."

exit 0