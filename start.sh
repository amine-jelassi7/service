#!/usr/bin/env bash
# start.sh — single command to get the service running on the VM.
# Run from the project root (where repo/ and service/ live):
#   bash start.sh
#
# What it does:
#   1. pip installs the DS team's exact requirements
#   2. go build compiles the HTTP server
#   3. launches the server (which spawns Python workers automatically)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "[start] ROOT=$ROOT"

# ── Python deps ───────────────────────────────────────────────────────────────
echo "[start] Installing Python deps..."
pip install -q -r "$ROOT/repo/requirements.txt"

# ── Build Go server ───────────────────────────────────────────────────────────
echo "[start] Building Go server..."
cd "$ROOT/service"
go build -o server .

# ── Launch ────────────────────────────────────────────────────────────────────
echo "[start] Launching server on :8080 ..."
# PYTHONPATH lets preload.py find the repo's src/ without installing it
export PYTHONPATH="$ROOT/repo:${PYTHONPATH:-}"
exec ./server
