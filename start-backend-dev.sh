#!/bin/bash

# Sound Capsule 开发环境后端启动脚本
# 自动读取用户配置并使用正确的路径启动 Python 后端

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Sound Capsule 开发环境后端启动脚本${NC}"
echo ""

# 从系统配置读取用户设置的 export_dir
USER_CONFIG_FILE="$HOME/Library/Application Support/com.soundcapsule.app/config.json"

if [ ! -f "$USER_CONFIG_FILE" ]; then
    echo -e "${RED}❌ 配置文件不存在: $USER_CONFIG_FILE${NC}"
    echo -e "${YELLOW}请先启动 Tauri 应用并完成初始化设置${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 找到配置文件: $USER_CONFIG_FILE${NC}"

# 使用 Python 解析 JSON 配置
EXPORT_DIR=$(python3 -c "import json; print(json.load(open('$USER_CONFIG_FILE'))['export_dir'])" 2>/dev/null)

if [ -z "$EXPORT_DIR" ]; then
    echo -e "${YELLOW}⚠️  配置文件中未设置 export_dir，使用项目默认值${NC}"
    EXPORT_DIR="$(cd "$(dirname "$0")/output" && pwd)"
fi

# 路径配置
# 🔴 开发模式：CONFIG_DIR 指向项目目录（包含开发数据库）
CONFIG_DIR="$(cd "$(dirname "$0")/data-pipeline" && pwd)"
RESOURCE_DIR="$(cd "$(dirname "$0")/data-pipeline" && pwd)"
PORT=5002

echo ""
echo -e "${GREEN}📋 启动参数:${NC}"
echo -e "  CONFIG_DIR:   $CONFIG_DIR"
echo -e "  EXPORT_DIR:   $EXPORT_DIR"
echo -e "  RESOURCE_DIR: $RESOURCE_DIR"
echo -e "  PORT:         $PORT"
echo ""

# 检查 Python 脚本是否存在
PYTHON_SCRIPT="$RESOURCE_DIR/capsule_api.py"
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}❌ Python 脚本不存在: $PYTHON_SCRIPT${NC}"
    exit 1
fi

# 启动后端
echo -e "${GREEN}🚀 启动 Python 后端...${NC}"
echo ""

cd "$RESOURCE_DIR"
python3 capsule_api.py \
  --config-dir "$CONFIG_DIR" \
  --export-dir "$EXPORT_DIR" \
  --resource-dir "$RESOURCE_DIR" \
  --port $PORT
