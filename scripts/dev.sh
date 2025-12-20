#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".venv/bin/activate" ]; then
  echo "❌ 未找到 .venv，请先创建：python -m venv .venv"
  exit 1
fi

source .venv/bin/activate

echo "[1/3] 安装/校验后端依赖..."
pip install -r requirements.txt

echo "[2/3] 启动后端 (http://127.0.0.1:5000)..."
python server/app.py &
BACK_PID=$!

echo "[3/3] 启动前端 (http://127.0.0.1:3000)..."
cd client
npm install
npm run dev &
FRONT_PID=$!

cleanup() {
  echo "\nStopping..."
  kill "$FRONT_PID" 2>/dev/null || true
  kill "$BACK_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "\n已启动："
echo "- Backend PID=$BACK_PID"
echo "- Frontend PID=$FRONT_PID"
echo "按 Ctrl+C 结束。"

wait "$FRONT_PID"
wait "$BACK_PID"
