@echo off
chcp 65001 >nul
title Sound Capsule - 启动中...

echo ============================================
echo   Sound Capsule 系统启动脚本 (Windows)
echo ============================================
echo.

:: 检查 Python 虚拟环境
if not exist "data-pipeline\venv\Scripts\activate.bat" (
    echo [错误] 虚拟环境不存在，请先运行以下命令创建:
    echo     cd data-pipeline
    echo     python -m venv venv
    echo     venv\Scripts\activate
    echo     pip install -r requirements.txt
    pause
    exit /b 1
)

:: 启动后端 API
echo [1/2] 启动后端 API 服务器 (端口 5002)...
start "Sound Capsule API" cmd /k "cd /d %~dp0data-pipeline && venv\Scripts\activate && python capsule_api.py"

:: 等待后端启动
echo     等待后端启动...
timeout /t 3 /nobreak >nul

:: 检查后端是否成功启动
curl -s "http://localhost:5002/api/capsules?limit=1" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 后端 API 可能未完全启动，请检查 API 窗口
) else (
    echo     后端 API 启动成功
)

:: 启动前端 Tauri
echo [2/2] 启动 Tauri 前端应用...
start "Sound Capsule Frontend" cmd /k "cd /d %~dp0webapp && npm run tauri dev"

echo.
echo ============================================
echo   系统启动完成!
echo ============================================
echo.
echo 服务信息:
echo   - 后端 API: http://localhost:5002
echo   - 前端应用: Tauri 窗口
echo.
echo 提示: 关闭此窗口不会停止服务
echo       需要手动关闭 API 和 Frontend 窗口
echo.
pause
