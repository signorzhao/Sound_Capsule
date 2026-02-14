#!/usr/bin/env python3
"""
批量回填云端胶囊的语义 embedding（标签级细粒度）

对本地已有 cloud_id 的胶囊：
1. 主体 embedding -> cloud_capsules.embedding
2. 每个标签 embedding -> cloud_capsule_tags.embedding

用法:
  cd data-pipeline
  python backfill_capsule_embeddings.py [--dry-run] [--limit N]
"""

import argparse
import logging
import sys
from pathlib import Path

# 确保 data-pipeline 在 path 中
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="批量回填 cloud_capsules.embedding")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要处理的胶囊，不写入")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个胶囊（0=全部）")
    parser.add_argument("--config-dir", type=str, help="配置目录（可选，默认使用标准路径）")
    parser.add_argument("--export-dir", type=str, help="导出目录（可选，默认使用标准路径）")
    args = parser.parse_args()

    try:
        from common import PathManager
        from capsule_db import get_database
        from supabase_client import SupabaseClient
        from capsule_embedding_service import update_embedding_for_cloud_capsule
    except ImportError as e:
        logger.error("依赖导入失败: %s", e)
        sys.exit(1)

    # 初始化 PathManager（独立脚本需手动初始化）
    try:
        try:
            pm = PathManager.get_instance()
        except RuntimeError:
            config_dir = args.config_dir or str(Path.home() / "Library" / "Application Support" / "com.soundcapsule.app")
            if args.export_dir:
                export_dir = args.export_dir
            else:
                config_file = Path(config_dir) / "config.json"
                if config_file.exists():
                    import json
                    with open(config_file) as f:
                        export_dir = json.load(f).get("export_dir", str(Path.home() / "Documents" / "soundcapsule_syncfolder"))
                else:
                    export_dir = str(Path.home() / "Documents" / "soundcapsule_syncfolder")
            resource_dir = str(BASE_DIR)
            PathManager.initialize(config_dir=config_dir, export_dir=export_dir, resource_dir=resource_dir)
            pm = PathManager.get_instance()
    except Exception as e:
        logger.error("PathManager 初始化失败: %s", e)
        sys.exit(1)
    db_path = pm.db_path
    if not db_path or not Path(db_path).exists():
        logger.error("本地数据库不存在: %s", db_path)
        sys.exit(1)

    db = get_database()
    db.connect()
    try:
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id, name, keywords, description, cloud_id
            FROM capsules
            WHERE cloud_id IS NOT NULL AND cloud_id != ''
            ORDER BY id
        """)
        rows = cursor.fetchall()
    except Exception as e:
        db.close()
        logger.error("查询本地胶囊失败: %s", e)
        sys.exit(1)

    if not rows:
        logger.info("没有需要回填的胶囊（无 cloud_id）")
        return

    total = len(rows)
    if args.limit:
        rows = rows[: args.limit]
        logger.info("将处理 %d / %d 个胶囊（--limit=%d）", len(rows), total, args.limit)
    else:
        logger.info("将处理 %d 个胶囊", total)

    if args.dry_run:
        for r in rows:
            logger.info("  [dry-run] id=%s name=%s cloud_id=%s", r[0], r[1], r[4])
        logger.info("dry-run 完成，未写入")
        return

    try:
        supabase = SupabaseClient()
    except Exception as e:
        logger.error("Supabase 初始化失败: %s", e)
        sys.exit(1)

    ok_count = 0
    fail_count = 0

    for row in rows:
        local_id, name, keywords, description, cloud_id = row
        try:
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT lens, word_id, word_cn, word_en, x, y FROM capsule_tags WHERE capsule_id = ?",
                (local_id,),
            )
            tags = []
            for t in cursor.fetchall():
                tags.append({
                    "lens": t[0],
                    "word_id": t[1],
                    "word_cn": t[2],
                    "word_en": t[3],
                    "x": t[4],
                    "y": t[5],
                })
        except Exception as e:
            logger.warning("读取标签失败 id=%s: %s", local_id, e)
            tags = []

        ok, tag_embeddings = update_embedding_for_cloud_capsule(
            supabase,
            cloud_id,
            name=name or "",
            keywords=keywords or "",
            description=description or "",
            tags=tags,
        )
        if ok:
            # 回填标签 embedding：从云端拉取 tags，按 (lens_id, word_cn, word_en) 匹配
            try:
                cloud_tags = supabase.download_capsule_tags(cloud_id)
                emb_map = {}
                for i, t in enumerate(tags):
                    if i < len(tag_embeddings) and tag_embeddings[i]:
                        key = (t.get("lens") or "", t.get("word_cn") or "", t.get("word_en") or "")
                        emb_map[key] = tag_embeddings[i]
                for ct in cloud_tags:
                    key = (ct.get("lens_id") or ct.get("lens") or "", ct.get("word_cn") or "", ct.get("word_en") or "")
                    emb = emb_map.get(key)
                    if emb and ct.get("id"):
                        supabase.update_tag_embedding(ct["id"], emb)
            except Exception as e:
                logger.warning("  回填标签 embedding 失败: %s", e)
            ok_count += 1
            logger.info("  ✓ %s (id=%s)", name or cloud_id, local_id)
        else:
            fail_count += 1
            logger.warning("  ✗ %s (id=%s)", name or cloud_id, local_id)

    db.close()
    logger.info("回填完成: 成功 %d, 失败 %d", ok_count, fail_count)


if __name__ == "__main__":
    main()
