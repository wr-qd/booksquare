@echo off
REM Windows批处理脚本 - 启动后端（使用根目录 .venv 与统一 requirements.txt）

setlocal

set "ROOT_DIR=%~dp0..\.."
pushd "%ROOT_DIR%"

if not exist ".venv\Scripts\python.exe" (
	echo [ERROR] 未找到 .venv\Scripts\python.exe
	echo         请先创建虚拟环境：python -m venv .venv
	pause
	popd
	exit /b 1
)

echo 激活 Python 虚拟环境...
call .venv\Scripts\activate.bat

echo 安装/校验依赖（requirements.txt）...
pip install -r requirements.txt

echo 启动后端 Flask 服务器...
set FLASK_DEBUG=0
cd server
python app.py

popd
pause
