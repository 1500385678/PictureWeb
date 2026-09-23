#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_db.py · 数据库健康检查

检查项(8/6 避坑指南 + 8 数据库规范):
1. 所有 db 的 metadata 字段填充度
2. abs_path 实际存在率(应该 100%)
3. 残留的占位符(应该 0)
4. abs_path 是否还是 01_SpaceDb 旧路径(应该 0)
5. 0 字节 db(应该 0)
7. 备份文件数量(应该 0 或只当前 sync 的备份)

用法:
    python scripts/verify_db.py
    python scripts/verify_db.py --json    # JSON 格式输出(给 CI 用)
"""
import argparse
import json
import os
import sqlite3
import sys

DEFAULT_ROOT = os.environ.get('PICTUREWEB_DB_ROOT', r'G:\_MyDatabase\01_Space_ImageDb')

ALL_DBS = ['SpaceDb.db'] + [
    '01_Master/MasterDb.db',
    '02_WeWork/WeWorkDb.db',
    '03_Residence/ResidenceDb.db',
    '04_Block/BlockDb.db',
    '07_Visualization/VisualizationDb.db',
    '08_Diagram/DiagramDb.db',
]

CHECK_COLS = ['project', 'scene', 'light', 'mood', 'arch_type', 'description', 'keywords']

# 占位符(参考 clean_placeholder.py)
PLACEHOLDERS = {'Style', 'TBD', 'titled', 'untitled', '未分类', 'none', 'N/A', '默认', '占位',
                'Diagram-(待补)'}


def check_db(db_path: str) -> dict:
    """检查一个 db,返回报告 dict"""
    rel = os.path.basename(db_path)
    if not os.path.exists(db_path):
        return {'name': rel, 'missing': True}
    size = os.path.getsize(db_path)
    if size == 0:
        return {'name': rel, 'empty': True, 'size': 0}

    db = sqlite3.connect(db_path)
    cur = db.execute('SELECT COUNT(*) FROM images')
    total = cur.fetchone()[0]
    cur = db.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="images"')
    has_images = bool(cur.fetchone())

    # 字段填充
    cols_in_db = [r[1] for r in db.execute('PRAGMA table_info(images)').fetchall()] if has_images else []
    fills = {}
    for col in CHECK_COLS:
        if col in cols_in_db:
            n = db.execute(f'SELECT COUNT(*) FROM images WHERE {col} IS NOT NULL AND {col} != ""').fetchone()[0]
            fills[col] = n

    # abs_path 有效性
    cur = db.execute('SELECT abs_path FROM images WHERE abs_path IS NOT NULL LIMIT 10000')
    paths = [r[0] for r in cur.fetchall()]
    exists = sum(1 for p in paths if os.path.exists(p))
    abs_path_old = sum(1 for p in paths if '01_SpaceDb/' in p)
    abs_path_new = sum(1 for p in paths if '01_Space_ImageDb/' in p)
    abs_path_none = total - len(paths)

    # 占位符
    placeholders = 0
    if 'project' in cols_in_db:
        ph_sql = ', '.join(f"'{p}'" for p in PLACEHOLDERS)
        placeholders = db.execute(f'SELECT COUNT(*) FROM images WHERE project IN ({ph_sql})').fetchone()[0]

    db.close()
    return {
        'name': rel,
        'size': size,
        'total': total,
        'fills': fills,
        'abs_path': {'exists': exists, 'total': len(paths), 'old': abs_path_old,
                     'new': abs_path_new, 'none': abs_path_none},
        'placeholders': placeholders,
    }


def check_backup_pollution(root: str) -> dict:
    """检查备份文件数量(应该 0 或 ≤ 当前 sync 备份)"""
    backups = {'pre-fix': 0, 'pre-sync': 0, 'pre-clean': 0, 'bak': 0}
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            for tag in backups:
                if tag in fn:
                    backups[tag] += 1
                    break
    return backups


def print_report(results: dict, backups: dict):
    print('=== 数据库健康检查 ===\n')
    print(f'{"db":<35} {"rows":>6} {"proj":>5} {"scene":>5} {"light":>5} {"mood":>5} {"desc":>5}')
    print('-' * 80)
    for r in results:
        if r.get('missing') or r.get('empty'):
            print(f'{r["name"]:<35} {"MISSING/EMPTY"}')
        f = r.get('fills', {})
        total = r.get('total', 0)
        print(f'{r["name"]:<35} {total:>6} '
              f'{f.get("project", "-"):>5} {f.get("scene", "-"):>5} '
              f'{f.get("light", "-"):>5} {f.get("mood", "-"):>5} '
              f'{f.get("description", "-"):>5}')

    print('\n=== abs_path 有效性 ===')
    for r in results:
        if r.get('missing') or r.get('empty'):
            continue
        ap = r['abs_path']
        pct = (ap['exists'] / ap['total'] * 100) if ap['total'] else 0
        flag = '✓' if pct == 100 and ap['old'] == 0 and ap['none'] == 0 else '⚠'
        print(f'  {flag} {r["name"]:<30} exists {ap["exists"]}/{ap["total"]} ({pct:.0f}%) '
              f'old={ap["old"]} new={ap["new"]} none={ap["none"]}')

    print('\n=== 占位符 ===')
    for r in results:
        if r.get('missing') or r.get('empty'):
            continue
        flag = '✓' if r.get('placeholders', 0) == 0 else '⚠'
        print(f'  {flag} {r["name"]:<30} placeholders: {r.get("placeholders", 0)}')

    print('\n=== 备份文件 ===')
    total_bk = sum(backups.values())
    flag = '✓' if total_bk == 0 else '⚠'
    print(f'  {flag} 备份文件总数: {total_bk}')
    for k, v in backups.items():
        if v:
            print(f'    {k}: {v}')


def main():
    ap = argparse.ArgumentParser(description='数据库健康检查')
    ap.add_argument('--root', default=DEFAULT_ROOT)
    ap.add_argument('--json', action='store_true', help='JSON 输出')
    args = ap.parse_args()

    root = args.root
    results = []
    for rel in ALL_DBS:
        path = os.path.join(root, rel)
        results.append(check_db(path))

    backups = check_backup_pollution(root)

    if args.json:
        print(json.dumps({'dbs': results, 'backups': backups}, ensure_ascii=False, indent=2))
    else:
        print_report(results, backups)


if __name__ == '__main__':
    main()