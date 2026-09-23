#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_placeholder.py · 清理数据库中错误的占位符

清理 6 类常见占位错误(2026-09-23 教训):
1. project = 'Style' / 'TBD' / '未分类' / 'titled' / 'untitled'(通用占位)
2. render_company = 'Style'(同项目名兜底)
3. project = 'Diagram-(待补)'(清掉,等手动补真实值)

用法:
    # 默认清理所有分库
    python scripts/clean_placeholder.py

    # 清理指定分库
    python scripts/clean_placeholder.py --target DiagramDb

    # DRY-RUN(只看不动)
    python scripts/clean_placeholder.py --dry-run
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

# 通用占位符(原则 8 入库占位符禁止)
PLACEHOLDER_PROJECTS = {'Style', 'TBD', 'titled', 'untitled', '未分类', 'none', 'N/A', '默认', '占位'}
PLACEHOLDER_COMPANIES = {'Style', 'TBD', 'titled', 'untitled', '未分类', 'none', 'N/A', '默认', '占位'}
# Diagram-(待补) 是约定占位(2026-09-23),也清掉
DIAGRAM_PLACEHOLDER = 'Diagram-(待补)'


def backup(db_path: str) -> str:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = db_path + f'.pre-clean-{ts}.db'
    shutil.copy2(db_path, bak)
    return bak


def clean_one(db_path: str, dry_run: bool = False) -> dict:
    """清理一个 db 的占位符,返回清理统计"""
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return {'skipped': True, 'reason': 'missing or empty'}

    if not dry_run:
        backup(db_path)

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    cols_in_db = [r[1] for r in db.execute('PRAGMA table_info(images)').fetchall()]
    # project 列在 SpaceDb.db 是 NOT NULL,清掉占位时用 '' 而非 NULL(兼容约束)
    cols_meta = {r[1]: (r[3] == 1) for r in db.execute('PRAGMA table_info(images)').fetchall()}  # notnull=1 → True

    # 占位符 → 空值(NULL 或 '',根据列约束)
    def empty_for(col):
        return 'NULL' if not cols_meta.get(col) else "''"

    stat = {}
    placeholders_sql = ', '.join(f"'{p}'" for p in PLACEHOLDER_PROJECTS)

    if 'project' in cols_in_db:
        e = empty_for('project')
        cur = db.execute(f"UPDATE images SET project = {e} WHERE project IN ({placeholders_sql})")
        stat['project_generic'] = cur.rowcount
        cur = db.execute(f"UPDATE images SET project = {e} WHERE project = '{DIAGRAM_PLACEHOLDER}'")
        stat['project_diagram'] = cur.rowcount

    if 'render_company' in cols_in_db:
        e = empty_for('render_company')
        cur = db.execute(f"UPDATE images SET render_company = {e} WHERE render_company IN ({placeholders_sql})")
        stat['company'] = cur.rowcount

    if 'caption' in cols_in_db:
        e = empty_for('caption')
        cur = db.execute(f"UPDATE images SET caption = {e} WHERE caption IN ({placeholders_sql})")
        stat['caption'] = cur.rowcount

    # ★★★ 原则 8 必加 commit()
    if not dry_run:
        db.commit()
    db.close()
    return stat


def main():
    ap = argparse.ArgumentParser(description='清理 db 错误占位符')
    ap.add_argument('--root', default=DEFAULT_ROOT)
    ap.add_argument('--target', help='只清指定 db(如 DiagramDb / SpaceDb)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    root = args.root
    print(f'=== 占位符清理器 ===')
    print(f'  ROOT: {root}')
    print(f'  MODE: {"DRY-RUN" if args.dry_run else "REAL"}')
    print(f'  通用占位: {", ".join(sorted(PLACEHOLDER_PROJECTS))}')
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
        stat = clean_one(path, dry_run=args.dry_run)
        if stat.get('skipped'):
            print(f'  ⏭ {rel}: {stat["reason"]}')
            continue
        n = sum(stat.values())
        total += n
        details = ', '.join(f'{k}={v}' for k, v in stat.items() if v)
        print(f'  ✓ {rel}: 清掉 {n} 行 ({details})' if n else f'  · {rel}: 干净')

    print()
    print(f'=== 总计清掉 {total} 行 ===')


if __name__ == '__main__':
    main()