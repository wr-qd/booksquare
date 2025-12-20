#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "正在激活 Python 虚拟环境 (.venv)..."
source .venv/bin/activate

# 检查是否激活成功
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo "✅ 虚拟环境已激活: $VIRTUAL_ENV"
    echo "📦 Python版本: $(python --version)"
    echo "🔧 工具位置: $(which python)"
else
    echo "❌ 虚拟环境激活失败"
    exit 1
fi
