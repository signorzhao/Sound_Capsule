import sqlite3
import json
import time
import os
from datetime import datetime

class PrismVersionManager:
    def __init__(self, db_path=None):
        if db_path is None:
            # 默认路径
            self.db_path = os.path.join(os.path.dirname(__file__), 'database', 'capsules.db')
        else:
            self.db_path = db_path
            
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self):
        """初始化数据库表"""
        sql_path = os.path.join(os.path.dirname(__file__), 'database', 'prism_versioning.sql')
        if not os.path.exists(sql_path):
            print(f"❌ 找不到 SQL 文件: {sql_path}")
            return
            
        with open(sql_path, 'r', encoding='utf-8') as f:
            schema = f.read()
            
        with self.get_connection() as conn:
            conn.executescript(schema)
            print("✅ 棱镜版本管理表结构已初始化")

    def get_prism(self, prism_id):
        """获取棱镜的当前配置"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM prisms WHERE id = ? AND is_deleted = 0", (prism_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_all_prisms(self):
        """获取所有未删除的棱镜"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM prisms WHERE is_deleted = 0 ORDER BY id")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_dirty_prisms(self, since_version=None):
        """
        获取需要同步的棱镜（本地版本 > 云端版本）

        Args:
            since_version: 可选，只返回版本号大于此值的棱镜

        Returns:
            List[Dict]: 需要同步的棱镜列表
        """
        with self.get_connection() as conn:
            if since_version is not None:
                cursor = conn.execute(
                    "SELECT * FROM prisms WHERE is_deleted = 0 AND version > ? ORDER BY updated_at DESC",
                    (since_version,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM prisms WHERE is_deleted = 0 ORDER BY updated_at DESC"
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def create_or_update_prism(self, prism_id, prism_data, user_id="local"):
        """
        创建或更新棱镜配置（自动处理版本号）
        策略：Last Write Wins (自动增加版本号)
        """
        # 准备数据
        name = prism_data.get('name', prism_id)
        description = prism_data.get('description', '')
        axis_config = json.dumps(prism_data.get('axis_config', {}), ensure_ascii=False)
        anchors = json.dumps(prism_data.get('anchors', []), ensure_ascii=False)
        
        field_data = json.dumps(prism_data.get('field_data', []), ensure_ascii=False)
        
        with self.get_connection() as conn:
            # 1. 检查是否存在
            cursor = conn.execute("SELECT version FROM prisms WHERE id = ?", (prism_id,))
            row = cursor.fetchone()
            
            new_version = 1
            action_type = "create"
            
            if row:
                # 更新模式
                new_version = row['version'] + 1
                action_type = "update"
                
                # 更新主表
                conn.execute("""
                    UPDATE prisms 
                    SET name=?, description=?, axis_config=?, anchors=?, field_data=?,
                        version=?, updated_at=CURRENT_TIMESTAMP, updated_by=?, is_deleted=0
                    WHERE id=?
                """, (name, description, axis_config, anchors, field_data, new_version, user_id, prism_id))
            else:
                # 创建模式
                conn.execute("""
                    INSERT INTO prisms (id, name, description, axis_config, anchors, field_data, version, updated_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (prism_id, name, description, axis_config, anchors, field_data, new_version, user_id))

            # 2. 记录版本历史 (Snapshot)
            snapshot = {
                "id": prism_id,
                "name": name,
                "axis_config": json.loads(axis_config),
                "anchors": json.loads(anchors)
            }
            
            conn.execute("""
                INSERT INTO prism_versions (prism_id, version, snapshot_data, created_by, change_reason)
                VALUES (?, ?, ?, ?, ?)
            """, (prism_id, new_version, json.dumps(snapshot, ensure_ascii=False), user_id, action_type))
            
            print(f"✅ 棱镜 '{prism_id}' {action_type} 成功 (v{new_version})")
            return new_version

    def get_version_history(self, prism_id):
        """获取历史版本列表"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT version, created_at, created_by, change_reason 
                FROM prism_versions 
                WHERE prism_id = ? 
                ORDER BY version DESC
            """, (prism_id,))
            return [dict(row) for row in cursor.fetchall()]

    def restore_version(self, prism_id, target_version):
        """回滚到指定版本"""
        with self.get_connection() as conn:
            # 获取历史快照
            cursor = conn.execute("""
                SELECT snapshot_data FROM prism_versions 
                WHERE prism_id = ? AND version = ?
            """, (prism_id, target_version))
            row = cursor.fetchone()
            
            if not row:
                return False, "版本不存在"
                
            snapshot = json.loads(row['snapshot_data'])
            
            # 恢复数据 (这会创建一个比当前还要新的版本)
            # 例如当前是 v5, 回滚到 v3 -> 生成 v6 (内容等于 v3)
            self.create_or_update_prism(prism_id, snapshot, user_id="system_restore")
            return True, f"已回滚到 v{target_version}"

# 简单的测试代码
if __name__ == "__main__":
    manager = PrismVersionManager()
    manager.init_tables()
    
    # 测试数据
    test_prism = {
        "name": "Test Lens / (测试)",
        "axis_config": {"x_pos": "Light", "x_neg": "Dark"},
        "anchors": [{"word": "shadow", "x": 10, "y": 10}]
    }
    
    print("\n--- 创建测试 ---")
    manager.create_or_update_prism("test_lens_v1", test_prism)
    
    print("\n--- 更新测试 ---")
    test_prism["anchors"].append({"word": "bright", "x": 90, "y": 90})
    manager.create_or_update_prism("test_lens_v1", test_prism)
    
    print("\n--- 历史记录 ---")
    history = manager.get_version_history("test_lens_v1")
    for h in history:
        print(h)