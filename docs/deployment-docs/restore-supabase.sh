#!/usr/bin/env bash
# 私有化 Supabase 恢复脚本
# 用法：./restore-supabase.sh <备份文件路径>
# 示例：./restore-supabase.sh /home/sbadmin/supabase-full-20250131-1200.tar.gz
set -e

if [ -z "$1" ]; then
  echo "用法: $0 <备份文件路径>"
  echo "示例: $0 supabase-full-20250131-1200.tar.gz"
  exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
  echo "错误: 备份文件不存在: $BACKUP_FILE"
  exit 1
fi

# 转为绝对路径
BACKUP_FILE="$(cd "$(dirname "$BACKUP_FILE")" && pwd)/$(basename "$BACKUP_FILE")"
RESTORE_DIR="$(dirname "$BACKUP_FILE")"

echo "[1/3] 解包到 $RESTORE_DIR ..."
cd "$RESTORE_DIR"
tar -xzvf "$(basename "$BACKUP_FILE")"

echo "[2/3] 拉取镜像..."
cd supabase-project
docker compose pull

echo "[3/3] 启动服务..."
docker compose up -d

echo ""
echo "=== 恢复完成 ==="
echo "Studio: http://<本机IP>:8000"
echo "检查: docker compose ps"
