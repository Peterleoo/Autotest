@echo off
chcp 65001 >nul
title Autotest AI Service (Port 8000)
echo ===================================================
echo       Autotest AI 自动化测试工作台 启动中...
echo ===================================================
echo.
echo [1/2] 正在切换到工作目录: %~dp0
cd /d "%~dp0"

echo [2/2] 正在启动 FastAPI Web 服务 (热重载模式)...
echo 服务访问地址: http://127.0.0.1:8000
echo 按 Ctrl + C 可终止服务。
echo.

python -m uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload

pause
