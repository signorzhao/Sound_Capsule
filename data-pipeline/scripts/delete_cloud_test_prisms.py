#!/usr/bin/env python3
"""
从云端删除测试棱镜（test、mechanics、spectral）。
仅管理员棱镜会受影响。执行后，胶囊客户端点「同步」会以云端为准，本地多余的 3 个棱镜会被删除。

使用：在 data-pipeline 目录、已激活 venv 时执行
  python scripts/delete_cloud_test_prisms.py
"""
import sys
from pathlib import Path

# 保证能导入项目模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dal_cloud_prisms import CloudPrismDAL

TO_DELETE = ['test', 'mechanics', 'spectral']

def main():
    dal = CloudPrismDAL()
    admin_id = CloudPrismDAL.ADMIN_USER_ID
    print(f"从云端删除测试棱镜（管理员 user_id: {admin_id[:8]}...）")
    for pid in TO_DELETE:
        try:
            ok = dal.delete_prism(admin_id, pid)
            print(f"  {pid}: {'已删除' if ok else '删除失败或不存在'}")
        except Exception as e:
            print(f"  {pid}: 异常 {e}")
    print("完成。请在胶囊客户端点「云同步」以拉取最新棱镜并移除本地多余棱镜。")

if __name__ == '__main__':
    main()
