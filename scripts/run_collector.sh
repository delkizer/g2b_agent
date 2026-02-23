#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENT_DIR="$PROJECT_ROOT/agent"
VENV_DIR="$PROJECT_ROOT/.venv"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "[ERROR] 가상환경을 찾을 수 없습니다: $VENV_DIR" >&2
    exit 1
fi

source "$VENV_DIR/bin/activate"
cd "$AGENT_DIR"

echo "[INFO] 수집 에이전트 시작: $(date '+%Y-%m-%d %H:%M:%S')"
echo "[INFO] Python: $(which python) ($(python --version 2>&1))"

exec uvicorn server:app --host 0.0.0.0 --port 8100
