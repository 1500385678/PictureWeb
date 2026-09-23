#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_split_dbs.py · 从 SpaceDb.db 同步 metadata 到 6 个分库

按 abs_path(优先)+ filename 匹配,同步 12 个 metadata 列(scene/light/mood/project 等)。
自动备份所有目标(.pre-sync-<ts>.db),只本地写不 commit。

用法:
    # 默认从 PICTUREWEB_DB_ROOT 同步所有分库
    python scripts/sync_split_dbs.py

    # 同步指定分库
    python scripts/sync_split_dbs.py --target MasterDb

    # 同步到自定义根目录
    python scripts/sync_split_dbs.py --root "G:/_MyDatabase/01_Space_ImageDb"
"""
import argparse
import os
import sqlite3
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 单一事实源(原则 5.2):从 env 读,默认值跟 server.py 对齐(server.py:13)
DEFAULT_ROOT = os.environ.get('PICTUREWEB_DB_ROOT', r'G:\_MyDatabase\01_Space_ImageDb')

# 6 个分库路径(SpaceDb 是总库,不需要同步)
SPLIT_DBS = [
    '01_Master/MasterDb.db',
    '02_WeWork/WeWorkDb.db',
    '03_Residence/ResidenceDb.db',
    '04_Block/BlockDb.db',
    '07_Visualization/VisualizationDb.db',
    '08_Diagram/DiagramDb.db',
]

# 路径迁移:2026-09-22 旧 01_SpaceDb 整体迁到 01_Space_ImageDb
# 同步时自动把旧路径改新路径
OLD_PREFIX = '01_SpaceDb'
NEW_PREFIX = '01_Space_ImageDb'

# 12 个 metadata 列(原则 8 数据库规范:facets 派生源)
METADATA_COLS = [
    'project', 'scene', 'light', 'space', 'material', 'mood',
    'caption', 'description', 'keywords', 'arch_type',
    'render_style', 'render_company', 'view_type', 'color_palette',
    'scale', 'dimension', 'expression', 'building_type',
]


def get_source_db(root: str) -> str:
    """总库(数据源)路径"""
    return os.path.join(root, 'SpaceDb.db')


def load_source_index(source_db: str) -> tuple:
    """加载 SpaceDb.db 索引(按 abs_path 和 filename 双索引)"""
    src = sqlite3.connect(source_db)
    src.row_factory = sqlite3.Row
    cur = src.execute(f'SELECT filename, abs_path, {",".join(METADATA_COLS)} FROM images')
    by_abspath = {}
    by_filename = {}
    for r in cur.fetchall():
        d = dict(r)
        if d['abs_path']:
            by_abspath[d['abs_path']] = d
        if d['filename']:
            by_filename[d['filename']] = d
    src.close()
    return by_abspath, by_filename


def backup(target_path: str) -> str:
    """备份目标 db(.pre-sync-<ts>.db 命名,跟 mavis-trash 兼容)"""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = target_path + f'.pre-sync-{ts}.db'
    shutil.copy2(target_path, bak)
    return bak


def sync_one(target_path: str, source_index: tuple, dry_run: bool = False) -> dict:
    """同步一个分库,返回同步统计"""
    by_abspath, by_filename = source_index

    if not os.path.exists(target_path) or os.path.getsize(target_path) == 0:
        return {'skipped': True, 'reason': 'missing or empty'}

    if not dry_run:
        backup(target_path)

    db = sqlite3.connect(target_path)
    db.row_factory = sqlite3.Row
    cols_in_db = [r[1] for r in db.execute('PRAGMA table_info(images)').fetchall()]
    cols_to_sync = [c for c in METADATA_COLS if c in cols_in_db]

    rows = db.execute('SELECT id, filename, abs_path FROM images').fetchall()
    fixed = 0
    missing = 0
    for row_id, fn, ap in rows:
        # 修 abs_path(01_SpaceDb → 01_Space_ImageDb)
        new_ap = None
        if ap and OLD_PREFIX in ap:
            new_ap = ap.replace(OLD_PREFIX, NEW_PREFIX)
            if not dry_run:
                db.execute('UPDATE images SET abs_path = ? WHERE id = ?', (new_ap, row_id))

        # 按新 abs_path → 旧 abs_path → filename 顺序匹配
        src_rec = None
        if new_ap and new_ap in by_abspath:
            src_rec = by_abspath[new_ap]
        elif ap and ap in by_abspath:
            src_rec = by_abspath[ap]
        elif fn and fn in by_filename:
            src_rec = by_filename[fn]
        if not src_rec:
            missing += 1
            continue

        # 同步 metadata(只在有值时覆盖)
        update_cols = []
        update_vals = []
        for c in cols_to_sync:
            new_val = src_rec.get(c)
            if new_val:
                update_cols.append(f'{c} = ?')
                update_vals.append(new_val)
        if update_cols:
            update_vals.append(row_id)
            if not dry_run:
                db.execute(f'UPDATE images SET {",".join(update_cols)} WHERE id = ?', update_vals)
            fixed += 1

    # ★★★ 原则 8 必加 commit()(2026-09-23 教训)
    if not dry_run:
        db.commit()
    db.close()

    return {'fixed': fixed, 'missing': missing, 'total': len(rows)}


def main():
    ap = argparse.ArgumentParser(description='从 SpaceDb.db 同步 metadata 到 6 个分库')
    ap.add_argument('--root', default=DEFAULT_ROOT, help=f'DB 根目录(默认 {DEFAULT_ROOT})')
    ap.add_argument('--target', help='只同步指定分库(如 MasterDb)')
    ap.add_argument('--dry-run', action='store_true', help='只看不动')
    args = ap.parse_args()

    root = args.root
    source_db = get_source_db(root)

    if not os.path.exists(source_db):
        print(f'❌ 总库不存在: {source_db}', file=sys.stderr)
        sys.exit(3)

    print(f'=== Sync 同步器 ===')
    print(f'  ROOT   : {root}')
    print(f'  SOURCE : {source_db}')
    print(f'  MODE   : {"DRY-RUN" if args.dry_run else "REAL"}')
    print()

    source_index = load_source_index(source_db)
    print(f'  SpaceDb 索引: {len(source_index[0])} abs_path + {len(source_index[1])} filename')
    print()

    targets = SPLIT_DBS
    if args.target:
        targets = [t for t in SPLIT_DBS if os.path.basename(t).replace('.db', '') == args.target]
        if not targets:
            print(f'❌ --target {args.target} 没匹配到分库', file=sys.stderr)
            sys.exit(4)

    total_fixed = 0
    total_missing = 0
    for rel in targets:
        target_path = os.path.join(root, rel)
        if not os.path.exists(target_path):
            print(f'  ⏭ {rel}: 不存在')
            continue
        stat = sync_one(target_path, source_index, dry_run=args.dry_run)
        if stat.get('skipped'):
            print(f'  ⏭ {rel}: {stat["reason"]}')
            continue
        total_fixed += stat['fixed']
        total_missing += stat['missing']
        flag = '✓' if stat['fixed'] == stat['total'] else '⚠'
        print(f'  {flag} {rel}: synced {stat["fixed"]}/{stat["total"]}, missing {stat["missing"]}')

    print()
    print(f'=== 总计 synced {total_fixed} 行,missing {total_missing} ===')


if __name__ == '__main__':
    main()