#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
phash_check_dups.py · 用 phash 找重复图(疑似放错文件夹)

给一个目录,对比 SpaceDb 里所有图的 phash,找出该目录下"跟其他项目重复"的图。
pHash 重复 = 同一张图已存在别的项目下,放错文件夹的强证据。

用法:
    python scripts/phash_check_dups.py "G:/_MyDatabase/01_Space_ImageDb/03_Residence/嘉佰道/嘉佰道·南京"
"""
import argparse
import os
import sqlite3
import sys

DEFAULT_ROOT = os.environ.get('PICTUREWEB_DB_ROOT', r'G:\_MyDatabase\01_Space_ImageDb')


def compute_phash(path: str, size: int = 8) -> str:
    try:
        from PIL import Image
    except ImportError:
        print('❌ 需要 Pillow:pip install Pillow', file=sys.stderr)
        sys.exit(1)
    img = Image.open(path).convert('L').resize((size, size), Image.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = ''.join('1' if p > avg else '0' for p in pixels)
    return ''.join(f'{int(bits[i:i+4], 2):x}' for i in range(0, len(bits), 4))


def load_space_phash_index(root: str) -> dict:
    """返回 {phash: [(db_name, filename, abs_path, project)]}"""
    idx = {}
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if not fn.endswith('.db'):
                continue
            if any(m in fn.lower() for m in ('.pre-', '.bak.', '.backup.')):
                continue
            full = os.path.join(dirpath, fn)
            try:
                c = sqlite3.connect(full)
                c.row_factory = sqlite3.Row
                cur = c.execute("SELECT phash, filename, abs_path, project FROM images WHERE phash IS NOT NULL AND phash != ''")
                for r in cur.fetchall():
                    if r['phash']:
                        idx.setdefault(r['phash'], []).append(
                            (os.path.basename(full), r['filename'], r['abs_path'], r['project']))
                c.close()
            except Exception:
                pass
    return idx


def main():
    ap = argparse.ArgumentParser(description='用 phash 找重复图')
    ap.add_argument('target_dir', help='要检查的目录')
    ap.add_argument('--root', default=DEFAULT_ROOT)
    args = ap.parse_args()

    target = args.target_dir.rstrip('/').rstrip('\\')
    if not os.path.isdir(target):
        print(f'❌ 目录不存在: {target}', file=sys.stderr)
        sys.exit(2)

    print(f'=== Phash 查重 ===')
    print(f'  TARGET : {target}')
    print(f'  ROOT   : {args.root}')
    print()

    print('1) 加载 SpaceDb 全部 phash 索引...')
    idx = load_space_phash_index(args.root)
    print(f'   索引了 {len(idx)} 个唯一 phash,共 {sum(len(v) for v in idx.values())} 条记录')

    print()
    print('2) 扫描 target 目录文件,逐个查重:')
    print()

    files = sorted([f for f in os.listdir(target) if os.path.isfile(os.path.join(target, f))])
    dups = []
    unique = []
    for fn in files:
        fp = os.path.join(target, fn)
        ph = compute_phash(fp)
        if not ph:
            print(f'  ⚠ {fn}: phash 算不出来(非图片)')
            continue
        if ph in idx:
            other = idx[ph][0]
            print(f'  ✗ {fn}  phash={ph[:8]} 重复 → 已在 {other[0]} ({other[1]}) 标 {other[3]}')
            dups.append((fn, ph, other))
        else:
            print(f'  ✓ {fn}  phash={ph[:8]} 唯一')
            unique.append((fn, ph))

    print()
    print('=== 总结 ===')
    print(f'  唯一: {len(unique)} 张')
    print(f'  重复(疑似放错): {len(dups)} 张')

    if dups:
        print()
        print('⚠ 建议从 db 删掉的(文件名):')
        for fn, ph, other in dups:
            print(f'  - {fn}  (跟 {other[0]}/{other[1]} 撞图)')


if __name__ == '__main__':
    main()