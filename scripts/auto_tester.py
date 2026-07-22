"""auto_tester.py · 3-Agent 流水线的 Tester
跑 tests/smoke.py,在 PR 留 verdict comment,通过则返 0 退出(让 action merge),失败则返 1。

用法:
  python scripts/auto_tester.py --pr 9            # 跑 PR #9 关联的代码
  python scripts/auto_tester.py --local           # 跑本地 main 头的代码
  python scripts/auto_tester.py --pr 9 --comment  # 跑 + 在 PR 留 verdict

设计:
  - 当前实现是骨架:跑 smoke + 收集结果 + (可选)写 PR comment
  - 跟 GitHub Action 集成:.github/workflows/smoke.yml 调本脚本
  - verdict comment 用 keyword 'smoke verdict' 触发 dispatch 数 attempt
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

API_BASE = 'https://api.github.com'
REPO = os.environ.get('PICTUREWEB_REPO', '1500385678/PictureWebWorkflowtest')
TOKEN = os.environ.get('GH_TOKEN', '')


def _request(path, method='GET', body=None):
    if not TOKEN:
        sys.exit('GH_TOKEN 未设')
    url = API_BASE + path
    data = json.dumps(body).encode('utf-8') if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            'Authorization': 'token ' + TOKEN,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'auto-tester-3agent',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read())
        except Exception:
            err = {'message': str(e)}
        return e.code, err
    except Exception as e:
        return 0, {'message': str(e)}


def checkout_pr_locally(pr_number):
    """git fetch + checkout PR · 用 ref refs/pull/<n>/head"""
    print(f'  fetch PR #{pr_number} ...')
    rc = subprocess.run(
        ['git', 'fetch', 'origin', f'pull/{pr_number}/head:pr-{pr_number}'],
        capture_output=True, text=True, timeout=60,
    )
    if rc.returncode != 0:
        print(f'  ❌ fetch 失败: {rc.stderr.strip()}')
        return False
    rc = subprocess.run(
        ['git', 'checkout', f'pr-{pr_number}'],
        capture_output=True, text=True, timeout=10,
    )
    if rc.returncode != 0:
        print(f'  ❌ checkout 失败: {rc.stderr.strip()}')
        return False
    print(f'  ✅ 切到 pr-{pr_number}')
    return True


def run_smoke():
    """跑 tests/smoke.py,返 (passed:int, total:int, log:str)"""
    proc = subprocess.run(
        ['python', '-X', 'utf8', 'tests/smoke.py'],
        capture_output=True, text=True, timeout=60,
    )
    log = proc.stdout + '\n' + proc.stderr
    # 解析 ✅ N/M endpoints OK
    import re
    m = re.search(r'(\d+)/(\d+) endpoints OK', proc.stdout)
    if m:
        return int(m.group(1)), int(m.group(2)), log
    return 0, 0, log


def post_verdict_comment(pr_number, passed, total, log):
    """在 PR 留 verdict comment,dispatch 用 'smoke verdict' keyword 数 attempt"""
    status_emoji = '✅' if passed == total else '❌'
    body = f'''## smoke verdict #{int(time.time())}

{status_emoji} **{passed}/{total} endpoints OK**

```
{log[:2000]}
```

> 自动由 `auto_tester.py` 生成 · 触发 dispatch 数 attempt,达到上限自动 @zhangyong
'''
    status, data = _request(
        f'/repos/{REPO}/issues/{pr_number}/comments',
        method='POST', body={'body': body}
    )
    if status == 201:
        print(f'  ✅ verdict comment 已留')
        return True
    print(f'  ❌ 留 comment 失败: {data.get("message")}')
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pr', type=int, help='测试指定 PR')
    p.add_argument('--local', action='store_true', help='测试本地 main 头')
    p.add_argument('--comment', action='store_true', help='在 PR 留 verdict comment')
    p.add_argument('--skip-checkout', action='store_true', help='不切 PR,直接在当前分支跑')
    args = p.parse_args()

    print('=== 3-Agent Tester ===')
    print(f'仓库: {REPO}')

    # 1) 切到目标代码
    if args.pr and not args.skip_checkout:
        if not checkout_pr_locally(args.pr):
            return 1
    elif args.local:
        print('  测试当前 working tree')

    # 2) 跑 smoke
    print('\n[跑 smoke]')
    passed, total, log = run_smoke()
    print(log)
    print(f'\n结果: {passed}/{total}')

    # 3) 可选:在 PR 留 verdict
    if args.pr and args.comment:
        print(f'\n[留 verdict]')
        post_verdict_comment(args.pr, passed, total, log)

    # 4) exit code:smoke 全过 = 0,有失败 = 1
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
