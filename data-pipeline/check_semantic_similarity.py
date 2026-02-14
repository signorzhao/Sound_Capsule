#!/usr/bin/env python3
"""
语义搜索相似度诊断工具

查看指定查询与各胶囊的原始相似度（未做阈值过滤），用于调试和评估语义准确性。

用法:
  python check_semantic_similarity.py "寒冷"
  python check_semantic_similarity.py "硕大" --limit 10
"""

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def main():
    parser = argparse.ArgumentParser(description="检查查询与胶囊的语义相似度")
    parser.add_argument("query", type=str, help="搜索词")
    parser.add_argument("--limit", type=int, default=20, help="显示前 N 个结果")
    parser.add_argument("--user-id", type=str, help="Supabase 用户 UUID（必填，否则 RPC 无 auth 会返回空）")
    args = parser.parse_args()

    # 初始化 PathManager
    try:
        from common import PathManager
        try:
            PathManager.get_instance()
        except RuntimeError:
            config_dir = str(Path.home() / "Library" / "Application Support" / "com.soundcapsule.app")
            config_file = Path(config_dir) / "config.json"
            if config_file.exists():
                import json
                with open(config_file) as f:
                    export_dir = json.load(f).get("export_dir", str(Path.home() / "Documents" / "soundcapsule_syncfolder"))
            else:
                export_dir = str(Path.home() / "Documents" / "soundcapsule_syncfolder")
            PathManager.initialize(config_dir=config_dir, export_dir=export_dir, resource_dir=str(BASE_DIR))
    except Exception as e:
        print(f"初始化失败: {e}")
        sys.exit(1)

    # 获取 query embedding
    from hybrid_embedding_service import get_hybrid_service
    service = get_hybrid_service()
    emb = service.get_embedding(args.query)
    if not emb or len(emb) != 384:
        print("获取 query embedding 失败")
        sys.exit(1)

    # 调用 Supabase RPC（不设阈值，取更多结果）
    try:
        from supabase_client import get_supabase_client
        supabase = get_supabase_client()
        if not supabase:
            print("Supabase 未配置")
            sys.exit(1)

        user_id = args.user_id
        if not user_id:
            # 尝试从本地 capsules 表获取 owner_supabase_user_id
            from capsule_db import get_database
            db = get_database()
            db.connect()
            try:
                cur = db.conn.cursor()
                cur.execute("SELECT owner_supabase_user_id FROM capsules WHERE cloud_id IS NOT NULL LIMIT 1")
                row = cur.fetchone()
                user_id = row[0] if row and row[0] else None
            finally:
                db.close()
        if not user_id:
            print("请指定 --user-id <Supabase用户UUID>，或确保本地胶囊有 owner_supabase_user_id")
            sys.exit(1)

        rpc_result = supabase.client.rpc(
            "semantic_search_capsules_tag_level",
            {
                "query_embedding": emb,
                "match_limit": args.limit * 2,
                "match_user_id": user_id,
            },
        ).execute()

        rows = rpc_result.data or []
    except Exception as e:
        print(f"RPC 失败: {e}")
        sys.exit(1)

    # 拉取各胶囊关键词（cloud_capsule_tags）
    cap_ids = [r["id"] for r in rows[: args.limit] if r.get("id")]
    keywords_by_cap = {}
    if cap_ids:
        try:
            for cid in cap_ids:
                tags_result = supabase.client.table("cloud_capsule_tags").select("word_cn, word_en").eq("capsule_id", cid).execute()
                parts = []
                for t in (tags_result.data or []):
                    w = (t.get("word_cn") or t.get("word_en") or "").strip()
                    if w:
                        parts.append(w)
                keywords_by_cap[cid] = " ".join(parts) if parts else "(无标签)"
        except Exception:
            keywords_by_cap = {cid: "(获取失败)" for cid in cap_ids}

    print(f"\n查询: 「{args.query}」")
    print("=" * 90)
    print(f"{'序号':<4} {'相似度':<8} {'关键词':<70}")
    print("-" * 90)

    for i, row in enumerate(rows[: args.limit], 1):
        sim = row.get("similarity") or 0
        cap_id = row.get("id")
        kw = keywords_by_cap.get(cap_id, "(无)")[:68]
        print(f"{i:<4} {sim:<8.4f} {kw}")

    print("-" * 90)
    print(f"共 {len(rows)} 条（阈值 0.3 以下的结果通常被过滤）")
    print()


if __name__ == "__main__":
    main()
