#!/bin/bash

# 启动 Synesth 完整系统（前端 + 后端）

echo "🚀 启动 Synesth 系统..."

# 进入后端目录
cd "$(dirname "$0")/data-pipeline" || exit 1

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv venv"
    exit 1
fi

# 激活虚拟环境并启动后端
echo "📡 启动后端 API 服务器 (端口 5002)..."
source venv/bin/activate
python3 capsule_api.py > /tmp/synesth-api.log 2>&1 &
API_PID=$!
echo "   后端 PID: $API_PID"

# 等待后端启动
sleep 2

# 检查后端是否成功启动
if curl -s "http://localhost:5002/api/capsules?limit=1" > /dev/null 2>&1; then
    echo "✅ 后端 API 启动成功"
else
    echo "❌ 后端 API 启动失败，请检查 /tmp/synesth-api.log"
    kill $API_PID 2>/dev/null
    exit 1
fi

# 进入前端目录并启动 Tauri
echo "🖥️  启动 Tauri 前端应用..."
cd "$(dirname "$0")/webapp" || exit 1
npm run tauri dev &

echo ""
echo "✅ 系统启动完成！"
echo ""
echo "📋 服务信息："
echo "   - 后端 API: http://localhost:5002"
echo "   - 前端应用: Tauri 窗口"
echo "   - 后端日志: tail -f /tmp/synesth-api.log"
echo ""
echo "💡 提示：按 Ctrl+C 停止所有服务"
echo ""

# 等待用户中断
trap "echo ''; echo '🛑 停止服务...'; kill $API_PID 2>/dev/null; pkill -f 'tauri dev' 2>/dev/null; exit 0" INT

# 保持脚本运行
wait
