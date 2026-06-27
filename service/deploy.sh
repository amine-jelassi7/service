#!/usr/bin/env bash
# deploy.sh — run this on the competition VM to install deps and start the service.
# Usage:  bash deploy.sh
# Assumes the repo is at /opt/app/repo/ and service files at /opt/app/service/

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$APP_DIR/repo"
SERVICE_DIR="$APP_DIR/service"

echo "=== [deploy] APP_DIR=$APP_DIR ==="

# ── 1. Install Python dependencies from the DS team's exact versions ──────────
echo "=== [deploy] Installing Python dependencies ==="
pip install -q -r "$REPO_DIR/requirements.txt"

# ── 2. Build the Go HTTP server ───────────────────────────────────────────────
echo "=== [deploy] Building Go server ==="
cd "$SERVICE_DIR"
go build -o server .

echo "=== [deploy] Build complete ==="

# ── 3. Start the service ──────────────────────────────────────────────────────
echo "=== [deploy] Starting service on port 8080 ==="
# Run from SERVICE_DIR so relative paths in worker.py work
cd "$SERVICE_DIR"
exec ./server
