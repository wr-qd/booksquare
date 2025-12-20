#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLIENT_DIR="$ROOT_DIR/client"
cd "$CLIENT_DIR"

echo "🌐 启动前端开发服务器"
echo "================================"

# 安装前端依赖（如未安装）
if [ ! -d "node_modules" ]; then
	echo "📦 正在安装依赖..."
	npm install
else
	echo "✅ 依赖已存在"
fi

echo ""
echo "2. 启动开发服务器 (http://localhost:3000)"
npm run dev
