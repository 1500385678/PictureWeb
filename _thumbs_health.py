"""CanvasWeb v3.5.53 缩略图健康检查 · 扫 Input/ + Output/ 全量坏图清单
用法:
  python _thumbs_health.py           # 扫 Input/ + Output/ 默认目录
  python _thumbs_health.py --root D:/pic  # 扫指定目录
  python _thumbs_health.py --json    # JSON 格式输出
2026-08-17 加 (P1 夜间迭代 R365):canvasweb-verifier P1 row 154 提到用户看不到哪些图坏了,
扫描全量给用户决定删/重传,补充 server/thumbs.py 的 logs/thumb_errors.json(只记录实际生成时碰到的)
"""
import json
import os
import sys
import time
from PIL import Image

DEFAULT_ROOTS = ['Input', 'Output']
EXT = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif')


def scan(root, max_seconds=60):
    """扫 root 下所有图片,挑出打不开的(坏图/截断/编码异常)。带时间上限,避免大型库死循环。
    返回 [{abs_path, size, error}, ...]
    """
    bad = []
    deadline = time.time() + max_seconds
    n_total = 0
    if not os.path.isdir(root):
        print(f'❌ root 不存在: {root}', file=sys.stderr)
        return bad, n_total
    for dirpath, _, filenames in os.walk(root):
        if time.time() > deadline:
            print(f'⚠ 超过 {max_seconds}s,提前结束扫描(已扫到 {dirpath})', file=sys.stderr)
            break
        for fn in filenames:
            if not fn.lower().endswith(EXT):
                continue
            n_total += 1
            abs_path = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(abs_path)
                with Image.open(abs_path) as img:
                    img.verify()  # 校验文件完整性,不改文件
            except Exception as e:
                bad.append({
                    'abs_path': abs_path,
                    'size': os.path.getsize(abs_path) if os.path.isfile(abs_path) else 0,
                    'error': f'{type(e).__name__}: {e}',
                })
    return bad, n_total


def main():
    args = sys.argv[1:]
    json_mode = '--json' in args
    args = [a for a in args if a != '--json']
    custom_root = None
    if '--root' in args:
        i = args.index('--root')
        custom_root = args[i + 1] if i + 1 < len(args) else None

    # 默认跟 server.config 走 BASE_DIR,落 Input/Output
    here = os.path.dirname(os.path.abspath(__file__))
    roots = [custom_root] if custom_root else [os.path.join(here, r) for r in DEFAULT_ROOTS]

    t0 = time.time()
    all_bad = []
    for r in roots:
        print(f'📂 扫描 {r} ...')
        bad, n = scan(r)
        all_bad.extend(bad)
        print(f'   总文件 {n} · 坏 {len(bad)}')
    elapsed = time.time() - t0

    # 写到 logs/thumb_health.json 留痕
    log_dir = os.path.join(here, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'thumb_health.json')
    report = {
        'ts': time.time(),
        'elapsed_s': round(elapsed, 2),
        'roots': roots,
        'n_total': sum(1 for r in roots for _ in ()),
        'n_bad': len(all_bad),
        'bad': all_bad,
    }
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    if json_mode:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print()
        print(f'=== 健康检查完成 · 用时 {elapsed:.1f}s ===')
        print(f'坏图总数: {len(all_bad)}')
        if all_bad:
            print(f'详细清单(头 20):')
            for b in all_bad[:20]:
                print(f'  {b["size"]:>10} B  {b["abs_path"]}  →  {b["error"]}')
            if len(all_bad) > 20:
                print(f'  ... 还有 {len(all_bad) - 20} 条,见 logs/thumb_health.json')
        print()
        print(f'完整清单写入 {log_file}')
        print(f'用户决定:删/重传 — bad 列表可用 `cat logs/thumb_health.json | jq .bad[]` 查看')


if __name__ == '__main__':
    main()
