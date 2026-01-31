#!/usr/bin/env bash
# 私有化 Supabase 完整备份脚本（含数据）
# 用法：chmod +x backup-supabase.sh && ./backup-supabase.sh
set -e

cd /home/sbadmin/supabase-project
echo "[1/2] 停止并移除容器..."
docker compose down

cd /home/sbadmin
BACKUP_NAME="supabase-full-$(date +%Y%m%d-%H%M).tar.gz"
echo "[2/2] 打包中..."
tar -czvf "$BACKUP_NAME" supabase-project/ database/

echo ""
echo "=== 备份完成 ==="
echo "文件: /home/sbadmin/$BACKUP_NAME"
echo "恢复: ./restore-supabase.sh $BACKUP_NAME"
echo "启动: cd supabase-project && docker compose up -d"
