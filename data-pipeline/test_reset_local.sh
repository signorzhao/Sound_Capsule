#!/bin/bash

# 测试重置脚本 - 清除本地数据，保留云端数据
# 用于测试完整的同步流程

echo "=========================================="
echo "🔄 开始清除本地数据..."
echo "=========================================="

DB_PATH="/Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline/database/capsules.db"
EXPORT_DIR="/Users/ianzhao/Documents/testout"

# 1. 备份数据库
echo ""
echo "📦 备份当前数据库..."
cp "$DB_PATH" "$DB_PATH.backup_before_test"
echo "✓ 数据库已备份到: $DB_PATH.backup_before_test"

# 2. 清除胶囊数据（保留用户配置）
echo ""
echo "🗑️  清除本地胶囊数据..."
sqlite3 "$DB_PATH" <<EOF
-- 删除所有胶囊记录
DELETE FROM capsules;

-- 删除所有 metadata
DELETE FROM capsule_metadata;

-- 删除所有 tags
DELETE FROM capsule_tags;

-- 删除同步状态
DELETE FROM sync_status;

-- 重置自增ID
DELETE FROM sqlite_sequence WHERE name IN ('capsules', 'capsule_metadata', 'capsule_tags', 'sync_status');
EOF

echo "✓ 本地胶囊数据已清除"

# 3. 显示当前云端胶囊数量（用于对比）
echo ""
echo "📊 当前状态统计："
TOTAL=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM capsules;")
echo "  - 本地胶囊数量: $TOTAL"

METADATA=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM capsule_metadata;")
echo "  - 本地 metadata 数量: $METADATA"

TAGS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM capsule_tags;")
echo "  - 本地标签数量: $TAGS"

echo ""
echo "=========================================="
echo "✅ 本地数据清除完成！"
echo "=========================================="
echo ""
echo "📋 下一步："
echo "  1. 打开应用"
echo "  2. 登录账号"
echo "  3. 点击「从云端下载」"
echo "  4. 验证下载的胶囊显示插件名和标签"
echo ""
