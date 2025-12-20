#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "🚀 启动书籍评论系统后端"
echo "================================"

"$ROOT_DIR/scripts/unix/start_backend.sh"