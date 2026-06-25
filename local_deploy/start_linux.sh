#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv_web/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "未找到 Web 虚拟环境，请先运行 local_deploy/install_linux.sh" >&2
  exit 1
fi

"$PYTHON" "$ROOT/local_deploy/run_server.py" --host 127.0.0.1 --port 7860

