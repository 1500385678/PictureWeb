#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_p1p2.py · PictureWeb 2026-08-06 夜间批 1 数据迁移

一次性迁移,idempotent(可重跑):
1. 加 pending_tag 字段(给 light 等字段 AI 补全失败用)
2. 建 image_arch_types 关联表(1NF 化)
3. 拆 3 条 arch_type 复合值入表
4. description 空值降级为 caption+keywords 拼接
5. 重建 images_fts(含 description + arch_type 多值)

用法:
    python3 tools/migrate_p1p2.py --dry-run   # 只看计划
    python3 tools/migrate_p1p2.py             # 真跑
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


def has_pending_tag(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(images)").fetchall()]
    return "pending_tag" in cols


def has_arch_types_table(conn):
    r = conn.execute(
        "SELECT name FROM sqlite_master WHERE name='image_arch_types'"
    ).fetchone()
    return bool(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found: {DB_PATH}")
        sys.exit(1)

    # 备份
    if not args.dry_run:
        backup = DB_PATH + f".bak_{time.strftime('%Y%m%d_%H%M%S')}"
        import shutil
        shutil.copy2(DB_PATH, backup)
        print(f"💾 备份: {backup}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")

        # === 1. pending_tag 字段 ===
        if has_pending_tag(conn):
            print("⏭  pending_tag 字段已存在,跳过")
        else:
            print("🔧 加 pending_tag 字段")
            if not args.dry_run:
                conn.execute("ALTER TABLE images ADD COLUMN pending_tag INTEGER DEFAULT 0")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pending_tag ON images(pending_tag)"
                )
                conn.commit()
            print("   ✅ pending_tag INTEGER DEFAULT 0 + idx_pending_tag")

        # === 2. image_arch_types 关联表 ===
        if has_arch_types_table(conn):
            print("⏭  image_arch_types 表已存在,跳过 CREATE")
        else:
            print("🔧 建 image_arch_types 关联表")
            if not args.dry_run:
                conn.execute("""
                    CREATE TABLE image_arch_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        image_id INTEGER NOT NULL,
                        value TEXT NOT NULL,
                        created_at TEXT,
                        UNIQUE(image_id, value),
                        FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
                    )
                """)
                conn.execute(
                    "CREATE INDEX idx_arch_type_value ON image_arch_types(value)"
                )
                conn.execute(
                    "CREATE INDEX idx_arch_type_image ON image_arch_types(image_id)"
                )
                conn.commit()
            print("   ✅ image_arch_types (id, image_id, value, created_at)")

        # === 3. 拆 arch_type 复合值入表 ===
        print("🔧 拆 arch_type 复合值入 image_arch_types")
        multi_rows = conn.execute(
            "SELECT id, arch_type FROM images WHERE arch_type LIKE '%+%'"
        ).fetchall()
        print(f"   待拆: {len(multi_rows)} 条")
        split_total = 0
        for r in multi_rows:
            parts = [p.strip() for p in (r["arch_type"] or "").split("+") if p.strip()]
            print(f"   id={r['id']} arch_type='{r['arch_type']}' → {parts}")
            for p in parts:
                if not args.dry_run:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO image_arch_types "
                            "(image_id, value, created_at) VALUES (?, ?, ?)",
                            (r["id"], p, now),
                        )
                        split_total += 1
                    except sqlite3.IntegrityError:
                        pass
        if not args.dry_run:
            conn.commit()
        print(f"   ✅ 拆出 {split_total} 条 image_arch_types 记录")

        # === 4. description 降级 ===
        print("🔧 description 空值降级为 caption+keywords 拼接")
        empty_desc = conn.execute(
            "SELECT id, caption, keywords FROM images "
            "WHERE description IS NULL OR description=''"
        ).fetchall()
        print(f"   待补: {len(empty_desc)} 条")
        desc_ok = 0
        for r in empty_desc:
            cap = (r["caption"] or "").strip()
            kw = (r["keywords"] or "").strip()
            if cap and kw:
                merged = f"{cap}\n\n{kw}"
            elif cap:
                merged = cap
            elif kw:
                merged = kw
            else:
                continue
            if not args.dry_run:
                conn.execute(
                    "UPDATE images SET description=?, updated_at=? WHERE id=?",
                    (merged, now, r["id"]),
                )
                desc_ok += 1
        if not args.dry_run:
            conn.commit()
        print(f"   ✅ 填充 {desc_ok} 条 description")

        # === 5. 重建 images_fts ===
        print("🔧 重建 images_fts (含 description + arch_type)")
        if not args.dry_run:
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
                    arch_type,
                    tokenize = "unicode61 remove_diacritics 2"
                )
            """)
            # arch_type 来源: 优先 image_arch_types 多值关联表(空格拼接),
            # 回退到 images.arch_type 单值(兼容未迁移的旧数据)
            conn.execute("""
                INSERT INTO images_fts (id, caption, description, filename, project, scene, space, material, mood, light, arch_type)
                SELECT
                    i.id,
                    i.caption,
                    i.description,
                    i.filename,
                    i.project,
                    i.scene,
                    i.space,
                    i.material,
                    i.mood,
                    i.light,
                    COALESCE(
                        (SELECT GROUP_CONCAT(value, ' ') FROM image_arch_types WHERE image_id = i.id),
                        i.arch_type
                    )
                FROM images i
            """)
            conn.commit()
            cnt = conn.execute("SELECT COUNT(*) FROM images_fts").fetchone()[0]
            print(f"   ✅ images_fts 重建,共 {cnt} 条索引(已含 arch_type)")

        # === 6. 验证 ===
        print("\n📊 验证:")
        def safe_count(sql, fallback="(无表/无字段)"):
            try:
                return conn.execute(sql).fetchone()[0]
            except sqlite3.OperationalError:
                return fallback
        pending_tag_exists = has_pending_tag(conn)
        arch_types_exists = has_arch_types_table(conn)
        total_imgs = safe_count("SELECT COUNT(*) FROM images")
        arch_types_cnt = safe_count("SELECT COUNT(*) FROM image_arch_types") if arch_types_exists else "(待建)"
        fts_cnt = safe_count("SELECT COUNT(*) FROM images_fts")
        desc_empty = safe_count("SELECT COUNT(*) FROM images WHERE description IS NULL OR description=''")
        light_empty = safe_count("SELECT COUNT(*) FROM images WHERE light IS NULL OR light=''")
        arch_multi = safe_count("SELECT COUNT(*) FROM images WHERE arch_type LIKE '%+%'")
        print(f"   images 总数: {total_imgs}")
        print(f"   pending_tag 字段: {'存在' if pending_tag_exists else '不存在'}")
        print(f"   image_arch_types 总数: {arch_types_cnt}")
        print(f"   images_fts 总数: {fts_cnt}")
        print(f"   description 空值: {desc_empty}")
        print(f"   light 空值: {light_empty}")
        print(f"   arch_type 复合值残留: {arch_multi}")

        if args.dry_run:
            print("\n🧪 dry-run 完成,未修改数据库")
        else:
            print(f"\n✅ 迁移完成。备份在 {DB_PATH}.bak_*")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
