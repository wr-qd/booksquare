#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# 激活虚拟环境（使用根目录 .venv）
if [ ! -f ".venv/bin/activate" ]; then
	echo "❌ 未找到 .venv，请先创建：python -m venv .venv"
	exit 1
fi
source .venv/bin/activate

# 安装后端依赖
pip install -r requirements.txt

# 启动后端
cd server
FLASK_DEBUG=${FLASK_DEBUG:-0}
python app.py
