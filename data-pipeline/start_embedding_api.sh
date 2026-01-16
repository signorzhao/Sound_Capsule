#!/bin/bash
# Phase C2: Embedding API 启动脚本

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          Phase C2: Embedding API 启动器                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 检查依赖
echo "🔍 检查依赖..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi
echo "   ✅ Python3"

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 未安装"
    exit 1
fi
echo "   ✅ pip3"

echo ""
echo "📦 安装依赖..."

# 安装依赖
pip3 install -q -r requirements-embedding.txt

if [ $? -eq 0 ]; then
    echo "   ✅ 依赖安装成功"
else
    echo "   ❌ 依赖安装失败"
    exit 1
fi

echo ""
echo "🚀 启动 Embedding API 服务..."
echo ""
echo "   服务地址: http://localhost:8000"
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "   按 Ctrl+C 停止服务"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""

# 启动服务
python3 embedding_service.py
