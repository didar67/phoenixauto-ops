#!/usr/bin/env bash

# ==========================================================
# PhoenixAuto_Ops - Project Initialization Script
# Description: Creates a clean modular project skeleton
# Author: Didarul Islam
# ==========================================================

set -euo pipefail

echo "Initializing PhoenixAuto_Ops project structure..."

# Create main application directories
mkdir -p app
mkdir -p config
mkdir -p scripts
mkdir -p cron
mkdir -p logs
mkdir -p tests
mkdir -p docs

# Create root-level files if they do not exist
touch README.md
touch LICENSE
touch requirements.txt

# Add placeholder to keep logs directory in git
touch logs/.gitkeep

echo "Project structure created successfully."
echo "PhoenixAuto_Ops skeleton is ready."