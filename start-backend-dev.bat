@echo off
chcp 65001 >nul
title Sound Capsule - 后端开发服务器

echo ============================================
echo   Sound Capsule 后端开发服务器
echo ============================================
echo.

cd /d %~dp0data-pipeline

:: 检查虚拟环境
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 虚拟环境不存在
    echo 请先运行: python -m venv venv
    pause
    exit /b 1
)

:: 激活虚拟环境并启动
echo 激活虚拟环境...
call venv\Scripts\activate

echo 启动 API 服务器 (端口 5002)...
echo.
python capsule_api.py
