#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_light_gpt4v.py · PictureWeb 光线字段 GPT-4V 补全脚本

背景:P1 数据质量修复。images.light 89/390 空(22.8%),集中在 中建·玖上琅宸 / 好莱坞山豪宅。
策略:用 GPT-4V(支持图片理解)反推光线标签,优先填 daylight / night / dusk / dawn / overcast。

用法:
    # 1. 试运行(只统计,不发请求,标 ⚠️ 表示无 key)
    python3 tools/fill_light_gpt4v.py --dry-run

    # 2. 真跑(需要 OPENAI_API_KEY 环境变量)
    export OPENAI_API_KEY=sk-xxxxx
    python3 tools/fill_light_gpt4v.py --limit 20

    # 3. 只补某个 project
    python3 tools/fill_light_gpt4v.py --project "中建·玖上琅宸" --limit 50

行为:
- 读 images 表,过滤 light IS NULL OR light=''
- 限速:每个请求间隔 0.5s
- 失败:标记 pending_tag=1,留待前端补录
- 成功:UPDATE light='<value>', pending_tag=0
- 无 API key:打印 ⚠️,列出待补条数和样例

退出码:
- 0:全部成功(或 dry-run)
- 2:部分失败(返回统计)
- 3:无 key 且非 dry-run(仅打印统计)
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

# 允许的光线标签白名单
LIGHT_WHITELIST = {
    "daylight", "night", "dusk", "dawn", "overcast",
    "interior-warm", "interior-cool", "mixed",
}


def get_pending_light_ids(conn, project=None, limit=None):
    sql = """
        SELECT id, project, filename, abs_path, caption
        FROM images
        WHERE (light IS NULL OR light = '')
    """
    args = []
    if project:
        sql += " AND project = ?"
        args.append(project)
    sql += " ORDER BY id LIMIT ?"
    args.append(limit or 9999)
    return conn.execute(sql, args).fetchall()


def call_gpt4v(image_path: str, caption: str) -> str:
    """调用 GPT-4V 反推光线标签。返回小写白名单中的值。"""
    import base64
    import urllib.request
    import json as jsonlib

    api_key = os.environ["OPENAI_API_KEY"]
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    body = {
        "model": "gpt-4-vision-preview",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    f"这张建筑效果图的光线属于下列哪种?只回一个词,小写英文,从白名单里选。\n"
                    f"白名单:{','.join(sorted(LIGHT_WHITELIST))}\n"
                    f"caption 辅助:{caption or '(无)'}\n"
                    f"你的回答:"
                )},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{b64[:100]}..."
                }},
            ],
        }],
        "max_tokens": 10,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=jsonlib.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = jsonlib.loads(resp.read())
    answer = (data["choices"][0]["message"]["content"] or "").strip().lower()
    # 白名单校验
    for w in LIGHT_WHITELIST:
        if w in answer:
            return w
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计不发请求")
    ap.add_argument("--project", help="只补某个 project")
    ap.add_argument("--limit", type=int, default=20, help="最多处理多少条")
    ap.add_argument("--delay", type=float, default=0.5, help="请求间隔(秒)")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = get_pending_light_ids(conn, args.project, args.limit)
        total_pending = conn.execute(
            "SELECT COUNT(*) FROM images WHERE light IS NULL OR light=''"
        ).fetchone()[0]
        print(f"📊 当前 light 空值总数: {total_pending}")
        print(f"🎯 本次将处理: {len(rows)} 条"
              + (f" (project={args.project})" if args.project else "")
              + (f" (limit={args.limit})" if args.limit < 9999 else ""))

        if not rows:
            print("✅ 没有待补条目,退出")
            return

        if args.dry_run:
            print("🧪 dry-run 模式,不修改数据库。样例前 5 条:")
            for r in rows[:5]:
                print(f"  id={r[0]} project={r[1]} file={r[2]}")
            return

        if "OPENAI_API_KEY" not in os.environ:
            print("⚠️ 未设置 OPENAI_API_KEY,无法调 GPT-4V")
            print("   备选:可手动 UPDATE light 字段,或使用 Anthropic Claude 3.5 Sonnet 替代。")
            print(f"   建议:把这 {len(rows)} 条标记 pending_tag=1,留给前端补录")
            # 不改库,只提示
            print(f"\n   列出 project 分布:")
            for proj, cnt in conn.execute(
                "SELECT project, COUNT(*) FROM images "
                "WHERE light IS NULL OR light='' GROUP BY project ORDER BY cnt DESC"
            ).fetchall():
                print(f"     {proj}: {cnt}")
            return

        # 真跑模式
        ok = fail = 0
        for i, r in enumerate(rows, 1):
            try:
                light = call_gpt4v(r[3], r[4])
                if light:
                    conn.execute(
                        "UPDATE images SET light=?, pending_tag=0, updated_at=? WHERE id=?",
                        (light, time.strftime("%Y-%m-%dT%H:%M:%S"), r[0]),
                    )
                    conn.commit()
                    print(f"  [{i}/{len(rows)}] ✅ id={r[0]} → {light}")
                    ok += 1
                else:
                    conn.execute(
                        "UPDATE images SET pending_tag=1 WHERE id=?", (r[0],)
                    )
                    conn.commit()
                    print(f"  [{i}/{len(rows)}] ⚠️ id={r[0]} 模型未给出白名单值,标 pending")
                    fail += 1
                time.sleep(args.delay)
            except Exception as e:
                print(f"  [{i}/{len(rows)}] ❌ id={r[0]} {e}")
                conn.execute(
                    "UPDATE images SET pending_tag=1 WHERE id=?", (r[0],)
                )
                conn.commit()
                fail += 1

        print(f"\n📈 完成:成功 {ok},失败 {fail},总 {len(rows)}")
        sys.exit(0 if fail == 0 else 2)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
