#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_description_default.py · PictureWeb description 字段降级脚本

背景:P2 信号缺失修复。images.description 331/390 空(84.9%)。
策略:把空 description 降级为 caption + keywords 拼接(用 \\n\\n 分隔),保证 FTS5 检索有信号可吃。
GPT 扩写留待后续接入(单独脚本,避免一次性大成本)。

用法:
    # 试运行(只统计)
    python3 tools/fill_description_default.py --dry-run

    # 真跑
    python3 tools/fill_description_default.py

    # 只补某个 project
    python3 tools/fill_description_default.py --project "中建·玖上琅宸"

效果:
- description 原本空 → 写入 "{caption}\\n\\n{keywords}"
- description 原本非空 → 跳过
- 同时把 FTS5 重建,新文本进索引

退出码:
- 0:成功
- 2:部分失败
"""
import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = os.environ.get(
    "PICTUREDB_DB",
    str(Path(__file__).parent.parent / "PictureDb.db"),
)


def rebuild_fts(conn):
    """重建 images_fts,把 description 也纳入索引字段。"""
    print("🔧 重建 images_fts (含 description 字段)...")
    conn.execute("DROP TABLE IF EXISTS images_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE images_fts USING fts5(
            id UNINDEXED,
            caption,
            description,
            filename,
            project,
            scene,
            space,
            material,
            mood,
            light,
            tokenize = "unicode61 remove_diacritics 2"
        )
    """)
    conn.execute("""
        INSERT INTO images_fts (id, caption, description, filename, project, scene, space, material, mood, light)
        SELECT id, caption, description, filename, project, scene, space, material, mood, light
        FROM images
    """)
    conn.commit()
    cnt = conn.execute("SELECT COUNT(*) FROM images_fts").fetchone()[0]
    print(f"   ✅ images_fts 重建完成,共 {cnt} 条索引")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计,不写入")
    ap.add_argument("--project", help="只补某个 project")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    try:
        # 统计
        total_empty = conn.execute(
            "SELECT COUNT(*) FROM images WHERE description IS NULL OR description=''"
        ).fetchone()[0]
        print(f"📊 当前 description 空值总数: {total_empty}")

        sql = """
            SELECT id, caption, keywords, project
            FROM images
            WHERE (description IS NULL OR description = '')
        """
        params = []
        if args.project:
            sql += " AND project = ?"
            params.append(args.project)
        rows = conn.execute(sql, params).fetchall()
        print(f"🎯 本次将处理: {len(rows)} 条"
              + (f" (project={args.project})" if args.project else ""))

        if not rows:
            print("✅ 没有待补条目,退出")
            return

        if args.dry_run:
            print("🧪 dry-run 模式,样例前 3 条:")
            for r in rows[:3]:
                cap = (r[1] or "")[:50]
                kw = (r[2] or "")[:50]
                print(f"  id={r[0]} project={r[3]}")
                print(f"    caption  : {cap}{'...' if len(r[1] or '')>50 else ''}")
                print(f"    keywords : {kw}{'...' if len(r[2] or '')>50 else ''}")
                print(f"    降级结果  : {cap}\\n\\n{kw}")
            return

        # 真跑
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        ok = 0
        for r in rows:
            cap = (r[1] or "").strip()
            kw = (r[2] or "").strip()
            if cap and kw:
                merged = f"{cap}\n\n{kw}"
            elif cap:
                merged = cap
            elif kw:
                merged = kw
            else:
                merged = ""
            if merged:
                conn.execute(
                    "UPDATE images SET description=?, updated_at=? WHERE id=?",
                    (merged, now, r[0]),
                )
                ok += 1
        conn.commit()
        print(f"✅ 已填充 {ok}/{len(rows)} 条 description")

        # 重建 FTS5
        rebuild_fts(conn)
        print(f"\n📈 完成。新增 description 信号条数: {ok}")
        sys.exit(0)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
