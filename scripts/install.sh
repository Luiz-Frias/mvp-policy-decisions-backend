#!/usr/bin/env bash
# install.sh – quick-start installer for MVP Policy Decision Backend
# Usage: curl -sSf https://raw.githubusercontent.com/Luiz-Frias/mvp-policy-decision-backend/main/install.sh | bash

set -euo pipefail

INFO()  { echo -e "\e[32m[INFO]\e[0m  $*"; }
WARN()  { echo -e "\e[33m[WARN]\e[0m  $*"; }
ERROR() { echo -e "\e[31m[ERROR]\e[0m $*" >&2; }

# 1. Check for Docker (required for Postgres/Redis dev containers)
if ! command -v docker &>/dev/null; then
  ERROR "Docker is not installed or not in PATH. Please install Docker Desktop / Docker Engine first."
  exit 1
fi

INFO "Docker detected: $(docker --version)"

# 2. Check for 'make' utility (POSIX make or GNU make)
if ! command -v make &>/dev/null; then
  WARN "'make' not found. Some convenience commands will be unavailable. Continuing without make..."
fi

# 3. Ensure 'uv' (Rust-based pip/venv tool) is available – install via pipx if missing
if ! command -v uv &>/dev/null; then
  INFO "'uv' not found – installing via pipx (requires Python & pipx)"
  if ! command -v pipx &>/dev/null; then
    ERROR "pipx is required to install uv automatically. Install pipx or uv manually and re-run."
    exit 1
  fi
  pipx install uv
fi

INFO "uv version: $(uv --version)"

# 4. Sync Python dependencies (dev set)
INFO "Syncing Python dependencies – this may take a minute..."
uv sync --dev

# 5. Optional: spin up local services via docker-compose if available
if [ -f docker-compose.yml ] && command -v docker-compose &>/dev/null; then
  INFO "Bringing up local PostgreSQL & Redis via docker-compose..."
  docker-compose up -d
else
  WARN "docker-compose.yml not found or docker-compose missing – skipping local service startup."
fi

INFO "Installation complete. To start the dev server run:\n  uv run uvicorn src.policy_core.main:app --reload"
