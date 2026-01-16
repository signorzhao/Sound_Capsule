@echo off
chcp 65001 >nul
title Sound Capsule - 后端开发服务器

echo ============================================
echo   Sound Capsule 后端开发服务器
echo ============================================
echo.

:: 设置路径变量
set "PROJECT_ROOT=%~dp0"
set "DATA_PIPELINE=%PROJECT_ROOT%data-pipeline"
set "CONFIG_DIR=%USERPROFILE%\.soundcapsule"
set "EXPORT_DIR=%USERPROFILE%\Documents\SoundCapsule\Exports"

:: 创建必需的目录
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
if not exist "%EXPORT_DIR%" mkdir "%EXPORT_DIR%"

cd /d %DATA_PIPELINE%

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

echo.
echo 启动 API 服务器 (端口 5002)...
echo   --config-dir: %CONFIG_DIR%
echo   --export-dir: %EXPORT_DIR%
echo.

python capsule_api.py --config-dir "%CONFIG_DIR%" --export-dir "%EXPORT_DIR%"
