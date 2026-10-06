#!/usr/bin/env bash
# ======================================================================
# PhoenixAuto-Ops: Run Monitor Wrapper
# Purpose: Reliable wrapper to start the Python monitoring engine.
# ======================================================================

set -euo pipefail

# Get absolute path of the project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

LOG_FILE="$PROJECT_ROOT/logs/run_monitor.log"
VENV_PATH="$PROJECT_ROOT/venv"

log() {
    local level="$1"
    local msg="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $msg" | tee -a "$LOG_FILE"
}

log "INFO" "Starting PhoenixAuto-Ops monitoring wrapper"

# Check and activate venv
if [[ ! -d "$VENV_PATH" ]]; then
    log "ERROR" "Virtual environment not found at $VENV_PATH. Run setup first."
    exit 1
fi

source "$VENV_PATH/bin/activate" || {
    log "ERROR" "Failed to activate virtual environment"
    exit 1
}

log "INFO" "Running Python monitoring engine"

# Run the engine as a module (-u for unbuffered logs); blocks until stopped
if python3 -u -m app.main >> "$LOG_FILE" 2>&1; then
    log "SUCCESS" "Engine stopped cleanly"
    exit 0
else
    log "ERROR" "Engine exited with an error"
    exit 1
fi
