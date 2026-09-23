#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest_directory.py · 从目录入库新图到 SpaceDb + 对应分库

自动推断:
- project = 父目录名(如 `嘉佰道·南京`)
- target_db = 上层分类对应 db(03_Residence → ResidenceDb,自动从 PICTUREWEB_DB_ROOT 找)
- dimension / source 从路径前缀推断(03_Residence → residential / self)

支持 webp / jpg / png / jpeg。
phash 去重(图已在 db 跳过)。

用法:
    # 入库指定目录
    python scripts/ingest_directory.py "G:/_MyDatabase/01_Space_ImageDb/03_Residence/嘉佰道/嘉佰道·南京"

    # DRY-RUN(只看)
    python scripts/ingest_directory.py "<path>" --dry-run

    # 强制项目名(覆盖父目录推断)
    python scripts/ingest_directory.py "<path>" --project "嘉佰道·南京"
"""
import argparse
import hashlib
import os
import sqlite3
import shutil
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_ROOT = os.environ.get('PICTUREWEB_DB_ROOT', r'G:\_MyDatabase\01_Space_ImageDb')

# 分类 → db 名映射(server.py db_name 派生规则:文件名去 .db + 去下划线)
CATEGORY_TO_DB = {
    '01_Master': 'MasterDb',
    '02_WeWork': 'WeWorkDb',
    '03_Residence': 'ResidenceDb',
    '04_Block': 'BlockDb',
    '07_Visualization': 'VisualizationDb',
    '08_Diagram': 'DiagramDb',
}
CATEGORY_TO_DIMENSION = {
    '01_Master': 'community',  # 大师作品源
    '02_WeWork': 'community',
    '03_Residence': 'life',    # 生活
    '04_Block': 'community',  # 社区
    '07_Visualization': 'Visualization',
    '08_Diagram': 'Diagram',
}
SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}


def backup(db_path: str) -> str:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = db_path + f'.pre-ingest-{ts}.db'
    shutil.copy2(db_path, bak)
    return bak


def compute_file_hash(path: str) -> str:
    """MD5(file content),32 字符"""
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def compute_phash(path: str, size: int = 8) -> str:
    """简易 perceptual hash(DCT 简化为 average hash)"""
    try:
        from PIL import Image
    except ImportError:
        return ''
    try:
        img = Image.open(path).convert('L').resize((size, size), Image.LANCZOS)
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        bits = ''.join('1' if p > avg else '0' for p in pixels)
        return ''.join(f'{int(bits[i:i+4], 2):x}' for i in range(0, len(bits), 4))
    except Exception:
        return ''


def infer_target(target_dir: str, root: str) -> tuple:
    """从 target_dir 推断 (category, db_name, project_name)"""
    p = Path(target_dir).resolve()
    rel = p.relative_to(root)
    parts = rel.parts  # ['03_Residence', '嘉佰道', '嘉佰道·南京']
    if not parts:
        raise ValueError(f'目录必须在 {root} 下')
    category = parts[0]
    if category not in CATEGORY_TO_DB:
        raise ValueError(f'未知分类 {category}(已知: {list(CATEGORY_TO_DB.keys())})')
    db_name = CATEGORY_TO_DB[category]
    dimension = CATEGORY_TO_DIMENSION.get(category, '')
    # project = 父目录名(parts[-1])
    project = p.name
    return category, db_name, project, dimension


def is_already_ingested(db_path: str, file_hash: str) -> bool:
    """phash 去重"""
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return False
    c = sqlite3.connect(db_path)
    cur = c.execute('SELECT 1 FROM images WHERE file_hash = ? LIMIT 1', (file_hash,))
    exists = cur.fetchone() is not None
    c.close()
    return exists


def insert_image(db_path: str, row: dict, real: bool = True) -> int:
    """插入一条记录,返回新 id。
    自动补全 NOT NULL 列:rel_path / project_id 等缺失列补默认值。"""
    if not real:
        return 0
    # 读 schema,获取所有列 + 是否 NOT NULL
    db = sqlite3.connect(db_path)
    cols_meta = db.execute('PRAGMA table_info(images)').fetchall()
    db.close()
    all_cols = [r[1] for r in cols_meta]
    notnull_cols = {r[1] for r in cols_meta if r[3] == 1}

    # 补全:行字段没给但列要求 NOT NULL
    for c in all_cols:
        if c not in row and c in notnull_cols:
            # 常见 NOT NULL 列默认值
            if c == 'rel_path':
                row[c] = row.get('abs_path', '')  # 用 abs_path 兜底
            elif c == 'project_id':
                row[c] = 0
            else:
                row[c] = ''

    cols = [c for c in all_cols if c in row]
    placeholders = ', '.join('?' * len(cols))
    qmarks = '(' + ', '.join(f'"{c}"' for c in cols) + ')'
    sql = f'INSERT INTO images {qmarks} VALUES ({placeholders})'

    db = sqlite3.connect(db_path)
    cur = db.execute(sql, [row[c] for c in cols])
    new_id = cur.lastrowid
    # ★★★ 原则 8 必加 commit()
    db.commit()
    db.close()
    return new_id


def ingest(target_dir: str, root: str = DEFAULT_ROOT, project_override: str = None,
           real: bool = False) -> dict:
    """入库 target_dir 下所有图到 SpaceDb + 对应分库"""
    target_dir = target_dir.rstrip('/').rstrip('\\')
    if not os.path.isdir(target_dir):
        return {'error': f'目录不存在: {target_dir}'}

    category, db_name, project_inferred, dimension = infer_target(target_dir, root)
    project = project_override or project_inferred

    target_db_path = os.path.join(root, f'{category}', f'{db_name}.db')
    # 按 server.py 规则派生 db_name:文件名去 .db
    # 实际路径是 03_Residence/ResidenceDb.db(去掉前缀 03_)
    target_db_path = os.path.join(root, category, f'{db_name}.db')
    source_db_path = os.path.join(root, 'SpaceDb.db')

    print(f'=== 入库工具 ===')
    print(f'  TARGET  : {target_dir}')
    print(f'  ROOT    : {root}')
    print(f'  CATEGORY: {category}')
    print(f'  TARGET  : {target_db_path}')
    print(f'  SOURCE  : {source_db_path}')
    print(f'  PROJECT : {project}')
    print(f'  DIMENSION: {dimension}')
    print(f'  MODE    : {"REAL" if real else "DRY-RUN"}')
    print()

    files = []
    for fn in os.listdir(target_dir):
        full = os.path.join(target_dir, fn)
        if os.path.isfile(full) and Path(fn).suffix.lower() in SUPPORTED_EXT:
            files.append(full)

    print(f'  待入库文件: {len(files)} 张')
    print()

    inserted_space = 0
    inserted_target = 0
    skipped = 0
    backup_done = False

    if real:
        if os.path.exists(source_db_path):
            backup(source_db_path)
        if os.path.exists(target_db_path):
            backup(target_db_path)
        backup_done = True

    for fp in files:
        fn = os.path.basename(fp)
        ext = Path(fn).suffix.lstrip('.').lower()
        file_size = os.path.getsize(fp)
        abs_path = fp.replace('\\', '/')
        file_hash = compute_file_hash(fp)
        phash = compute_phash(fp)

        # 去重(用 SpaceDb 查)
        if is_already_ingested(source_db_path, file_hash):
            skipped += 1
            print(f'  ⏭ {fn} (hash={file_hash[:8]}): 已存在,跳过')
            continue

        row = {
            'project': project,
            'filename': fn,
            'abs_path': abs_path,
            'ext': ext,
            'file_size': file_size,
            'file_hash': file_hash,
            'phash': phash,
            'source': 'self',
            'dimension': dimension,
            'scene': None, 'light': None, 'space': None, 'material': None,
            'mood': None, 'caption': fn, 'description': None, 'keywords': None,
            'arch_type': None, 'render_style': None, 'render_company': None,
            'view_type': None, 'color_palette': None, 'scale': None,
        }
        # 列名差异处理:SpaceDb 列(不含 file_size,用 size_bytes)
        row_space = dict(row)
        row_space['size_bytes'] = row_space.pop('file_size')

        # 写 SpaceDb
        space_id = insert_image(source_db_path, row_space, real=real)
        target_id = insert_image(target_db_path, row, real=real)

        if real:
            inserted_space += 1
            inserted_target += 1
            print(f'  ✓ {fn}  SpaceDb id={space_id}  {db_name} id={target_id}')
        else:
            print(f'  · {fn}  (would insert)')

    print()
    print(f'=== 总结 ===')
    print(f'  SpaceDb: +{inserted_space} 条')
    print(f'  {db_name}: +{inserted_target} 条')
    print(f'  跳过(已存在): {skipped}')
    if backup_done:
        print(f'  备份: *.pre-ingest-<ts>.db')


def main():
    ap = argparse.ArgumentParser(description='从目录入库新图')
    ap.add_argument('target_dir', help='目标目录(必填)')
    ap.add_argument('--root', default=DEFAULT_ROOT, help='DB 根目录')
    ap.add_argument('--project', help='强制项目名(覆盖父目录推断)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    real = not args.dry_run
    ingest(args.target_dir, root=args.root, project_override=args.project, real=real)


if __name__ == '__main__':
    main()