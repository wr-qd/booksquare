$ErrorActionPreference = 'Stop'

# Ensure Chinese output is readable in Windows terminals.
# On Windows PowerShell 5.1 + ConsoleHost, switching the code page is often required.
try {
  if ($Host.Name -eq 'ConsoleHost') {
    & cmd /c 'chcp 65001 >NUL'
  }
} catch {
  # Best-effort only.
}

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Help child processes (Python) default to UTF-8.
$env:PYTHONUTF8 = '1'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
  Write-Host "[ERROR] 未找到 $Python"
  Write-Host "请先创建虚拟环境：python -m venv .venv"
  exit 1
}

Write-Host "[1/3] 安装/校验后端依赖..."
& $Python -m pip install -r (Join-Path $Root 'requirements.txt')

Write-Host "[2/3] 启动后端 (http://127.0.0.1:5000)..."
$Backend = Start-Process -FilePath $Python -WorkingDirectory $Root -ArgumentList @('server/app.py') -PassThru

Write-Host "[3/3] 启动前端 (http://127.0.0.1:3000)..."
$ClientDir = Join-Path $Root 'client'
if (-not (Test-Path (Join-Path $ClientDir 'package.json'))) {
  Write-Host "[ERROR] 未找到前端目录：$ClientDir"
  Stop-Process -Id $Backend.Id -Force -ErrorAction SilentlyContinue
  exit 1
}

# 确保依赖已安装
if (-not (Test-Path (Join-Path $ClientDir 'node_modules'))) {
  & npm.cmd --prefix $ClientDir install
}

$Frontend = Start-Process -FilePath 'npm.cmd' -WorkingDirectory $ClientDir -ArgumentList @('run','dev') -PassThru

Write-Host "`n已启动："
Write-Host "- Backend PID=$($Backend.Id)"
Write-Host "- Frontend PID=$($Frontend.Id)"
Write-Host "按 Ctrl+C 结束。`n"

try {
  while (-not $Backend.HasExited -and -not $Frontend.HasExited) {
    Start-Sleep -Seconds 1
  }
} finally {
  if ($Frontend -and -not $Frontend.HasExited) { Stop-Process -Id $Frontend.Id -Force -ErrorAction SilentlyContinue }
  if ($Backend -and -not $Backend.HasExited) { Stop-Process -Id $Backend.Id -Force -ErrorAction SilentlyContinue }
}
