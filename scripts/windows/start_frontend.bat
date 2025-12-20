@echo off
REM Windows批处理脚本 - 启动前端（使用 scripts/windows 目录相对路径）

setlocal

set "ROOT_DIR=%~dp0..\.."
pushd "%ROOT_DIR%"
set "CLIENT_DIR=%CD%\client"

if not exist "%CLIENT_DIR%\package.json" (
	echo 未找到前端目录: %CLIENT_DIR%
	pause
	exit /b 1
)

cd /d "%CLIENT_DIR%"

REM 确保能找到 node/npm（有些环境里 VS Code 终端 PATH 不包含 nodejs）
set "NODEJS_DIR=C:\Program Files\nodejs"
if exist "%NODEJS_DIR%\npm.cmd" (
	set "PATH=%NODEJS_DIR%;%PATH%"
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
	echo 未找到 npm.cmd，请确认已安装 Node.js，或将 C:\Program Files\nodejs 加入系统 PATH。
	pause
	exit /b 1
)

if not exist "node_modules" (
	echo 正在安装前端依赖...
	call npm.cmd install
)

echo 正在启动前端开发服务器...
call npm.cmd run dev

popd
pause
