"""
棱镜配置迁移脚本

将旧的 anchor_config_v2.json 迁移到新的数据库版本控制系统

使用方法：
    cd data-pipeline
    python migrate_prisms.py
"""

import json
import os
from prism_version_manager import PrismVersionManager

def migrate():
    """执行迁移"""
    # 1. 读取旧的 JSON 配置
    json_path = os.path.join(os.path.dirname(__file__), 'anchor_config_v2.json')
    if not os.path.exists(json_path):
        print("⚠️  未找到 anchor_config_v2.json，跳过迁移。")
        print(f"   查找路径: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        old_config = json.load(f)

    # 2. 初始化管理器
    manager = PrismVersionManager()
    manager.init_tables()

    print(f"🔄 开始迁移 {len(old_config)} 个棱镜...")

    # 3. 逐个导入
    success_count = 0
    for prism_id, data in old_config.items():
        try:
            # 构建符合新结构的数据
            prism_data = {
                "name": data.get('name', prism_id),
                "description": data.get('description', ''),
                "axis_config": {
                    "x_label_pos": data.get('x_label_pos', ''),
                    "x_label_neg": data.get('x_label_neg', ''),
                    "y_label_pos": data.get('y_label_pos', ''),
                    "y_label_neg": data.get('y_label_neg', '')
                },
                "anchors": data.get('anchors', [])
            }

            manager.create_or_update_prism(prism_id, prism_data, user_id="migration_script")
            success_count += 1

        except Exception as e:
            print(f"❌ 迁移棱镜 '{prism_id}' 失败: {e}")

    print(f"\n🎉 迁移完成！成功迁移 {success_count}/{len(old_config)} 个棱镜")
    print("✅ 现在数据库是棱镜配置的 Source of Truth。")

    # 4. 验证迁移结果
    print("\n📊 迁移结果验证：")
    for prism_id in old_config.keys():
        prism = manager.get_prism(prism_id)
        if prism:
            print(f"  ✅ {prism_id}: {prism['name']} (v{prism['version']})")
        else:
            print(f"  ❌ {prism_id}: 未找到")

if __name__ == "__main__":
    migrate()
