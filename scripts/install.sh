#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

echo "Building helium..."
cd "$REPO_ROOT"
go build -o "$INSTALL_DIR/helium" ./cmd/helium

echo "Installed: $INSTALL_DIR/helium"
"$INSTALL_DIR/helium" --version 2>/dev/null || true
