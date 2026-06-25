#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CLONE_DIFFLOCKS=0
INSTALL_DIFFLOCKS_DEPS=0
START_AFTER=0

for arg in "$@"; do
  case "$arg" in
    --clone-difflocks) CLONE_DIFFLOCKS=1 ;;
    --install-difflocks-deps) INSTALL_DIFFLOCKS_DEPS=1 ;;
    --start) START_AFTER=1 ;;
  esac
done

VENV_DIR="$ROOT/.venv_web"
DATA_DIR="$ROOT/runtime_data"
THIRD_PARTY="$ROOT/third_party"
DIFFLOCKS_DIR="$THIRD_PARTY/difflocks"
ENV_PATH="$ROOT/.env"

mkdir -p "$DATA_DIR" "$THIRD_PARTY"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$ROOT/server/requirements.txt"

if [[ "$CLONE_DIFFLOCKS" == "1" && ! -d "$DIFFLOCKS_DIR" ]]; then
  git clone https://github.com/Meshcapade/difflocks "$DIFFLOCKS_DIR"
fi

if [[ "$INSTALL_DIFFLOCKS_DEPS" == "1" && -f "$DIFFLOCKS_DIR/requirements.txt" ]]; then
  "$VENV_PYTHON" -m pip install -r "$DIFFLOCKS_DIR/requirements.txt"
fi

if [[ ! -f "$ENV_PATH" ]]; then
  cat > "$ENV_PATH" <<EOF
DIFFLOCKS_PUBLIC=1
DIFFLOCKS_WEB_PASSWORD=
HAIRGEN_INVITE_CODE=
DIFFLOCKS_WEB_DATA=$DATA_DIR
DIFFLOCKS_REPO=$DIFFLOCKS_DIR
DIFFLOCKS_PYTHON=$VENV_PYTHON
BLENDER_PATH=
DIFFLOCKS_INPROCESS=1
HAIRGEN_FACE_MODEL_PROVIDER=off
HAIRGEN_FACE_MODEL_MODE=cpu
EOF
fi

echo "本地 Web 环境已准备好。"
echo "如果还没放权重，请按 DiffLocks 官方说明下载 checkpoints 并放入 third_party/difflocks 对应目录。"
echo "CUDA 推理还需要按 DiffLocks 官方 README 安装 NATTEN 和 FlashAttention-2。"
echo "启动命令: bash ./local_deploy/start_linux.sh"

if [[ "$START_AFTER" == "1" ]]; then
  bash "$ROOT/local_deploy/start_linux.sh"
fi
