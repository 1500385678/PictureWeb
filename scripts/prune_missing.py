#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prune_missing.py · 删除 db 里 abs_path 已不存在的"幽灵行"

删图后 db 还在,abs_path 指向空文件 → 前端 404,搜索结果空。
自动备份(.pre-prune-<ts>.db),只本地写不 commit。

用法:
    # 默认检查所有 db,只显示不动
    python scripts/prune_missing.py

    # 真删
    python scripts/prune_missing.py --real

    # 只清指定 db
    python scripts/prune_missing.py --target SpaceDb --real
"""
import argparse
import os
import sqlite3
import shutil
import sys
from datetime import datetime

DEFAULT_ROOT = os.environ.get('PICTUREWEB_DB_ROOT', r'G:\_MyDatabase\01_Space_ImageDb')

ALL_DBS = ['SpaceDb.db'] + [
    '01_Master/MasterDb.db',
    '02_WeWork/WeWorkDb.db',
    '03_Residence/ResidenceDb.db',
    '04_Block/BlockDb.db',
    '07_Visualization/VisualizationDb.db',
    '08_Diagram/DiagramDb.db',
]


def backup(db_path: str) -> str:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = db_path + f'.pre-prune-{ts}.db'
    shutil.copy2(db_path, bak)
    return bak


def find_ghosts(db_path: str) -> list:
    """找出 db 里 abs_path 不存在的幽灵行"""
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return []
    db = sqlite3.connect(db_path)
    cur = db.execute('SELECT id, filename, abs_path FROM images WHERE abs_path IS NOT NULL')
    ghosts = []
    for row_id, fn, ap in cur.fetchall():
        if not os.path.exists(ap):
            ghosts.append((row_id, fn, ap))
    db.close()
    return ghosts


def prune(db_path: str, real: bool = False) -> dict:
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return {'skipped': True, 'reason': 'missing or empty'}

    ghosts = find_ghosts(db_path)
    if not ghosts:
        return {'ghosts': 0}

    if real:
        backup(db_path)
        db = sqlite3.connect(db_path)
        ids = [g[0] for g in ghosts]
        qmarks = ', '.join('?' * len(ids))
        db.execute(f'DELETE FROM images WHERE id IN ({qmarks})', ids)
        # ★★★ 原则 8 必加 commit()
        db.commit()
        db.close()
        return {'ghosts': len(ghosts), 'deleted': len(ghosts)}

    return {'ghosts': len(ghosts), 'deleted': 0}


def main():
    ap = argparse.ArgumentParser(description='删 db 里的幽灵行(abs_path 不存在)')
    ap.add_argument('--root', default=DEFAULT_ROOT)
    ap.add_argument('--target', help='只清指定 db(如 SpaceDb / MasterDb)')
    ap.add_argument('--real', action='store_true', help='真删(默认 dry-run)')
    args = ap.parse_args()

    root = args.root
    print(f'=== Prune 幽灵行清理 ===')
    print(f'  ROOT: {root}')
    print(f'  MODE: {"REAL" if args.real else "DRY-RUN"}')
    print()

    dbs = ALL_DBS
    if args.target:
        dbs = [t for t in ALL_DBS if os.path.basename(t).replace('.db', '') == args.target]
        if not dbs:
            print(f'❌ --target {args.target} 没匹配', file=sys.stderr)
            sys.exit(4)

    total = 0
    for rel in dbs:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            print(f'  ⏭ {rel}: 不存在')
            continue
        ghosts = find_ghosts(path)
        if not ghosts:
            print(f'  ✓ {rel}: 干净')
            continue
        stat = prune(path, real=args.real)
        if stat.get('deleted'):
            print(f'  🗑 {rel}: 删除 {stat["deleted"]} 行')
        else:
            print(f'  👻 {rel}: 找到 {stat["ghosts"]} 幽灵行(dry-run,加 --real 真删)')
            for row_id, fn, ap in ghosts[:5]:
                print(f'      id={row_id} {fn}  →  {ap}')
            if len(ghosts) > 5:
                print(f'      ... 还有 {len(ghosts) - 5} 行')
        total += stat.get('ghosts', 0)

    print()
    print(f'=== 幽灵行总数: {total} ===')


if __name__ == '__main__':
    main()