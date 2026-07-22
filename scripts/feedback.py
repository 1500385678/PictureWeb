"""feedback.py · 交互式反馈入口
收集用户意见 → 直接推到 GitHub Issue
用法:
  python scripts/feedback.py                          # 交互式(从 stdin 读)
  echo '{"title":"...","severity":"P0","body":"..."}' | python scripts/feedback.py --from-stdin
  python scripts/feedback.py --title "..." --severity P1 --body "..."
设计:
  - 默认是 PowerShell/cmd 交互式 CLI(最简单,无依赖)
  - 也支持 --from-stdin(从 stdin 读 JSON)· --title/--body/--severity 直接传
  - 后续可以扩展:Web UI / 飞书 bot / VSCode 插件(都走 push_issue 函数)
  - 默认加 label auto-fix(P0/P1/P2 自动加),被 dispatcher 扫到自动派 Fixer
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = os.environ.get('PICTUREWEB_REPO', '1500385678/PictureWebWorkflowtest')
TOKEN = os.environ.get('GH_TOKEN', '')


def _request(path, method='GET', body=None):
    if not TOKEN:
        sys.exit('GH_TOKEN 未设。Set-Item Env:GH_TOKEN -Value "ghp_xxx"')
    quoted = urllib.parse.quote(path, safe='/')
    url = 'https://api.github.com' + quoted
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            'Authorization': 'token ' + TOKEN,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'feedback-3agent',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {'message': str(e)}


def push_issue(title, body, labels):
    """推一个 issue 到 GitHub"""
    payload = {'title': title, 'body': body, 'labels': labels}
    status, data = _request(f'/repos/{REPO}/issues', method='POST', body=payload)
    if status == 201:
        return data
    raise RuntimeError(f'GitHub 返 {status}: {data.get("message")}')


def build_labels(severity, kind=None, extra=None):
    """根据 severity 自动算 labels"""
    sev = severity.upper()
    if kind is None:
        kind = 'bug' if sev in ('P0', 'P1') else ('enhancement' if sev == 'P2' else 'discussion')
    labels = [kind, f'priority:{sev.lower()}']
    if sev != 'P3':
        labels.append('auto-fix')
    if extra:
        labels.extend(extra)
    return labels


def interactive_input():
    """交互式收集用户输入"""
    print('=' * 60)
    print('📝 意见反馈 → GitHub Issue')
    print('=' * 60)

    print()
    title = input('标题(一句话描述): ').strip()
    if not title:
        sys.exit('❌ 标题必填')

    print()
    print('严重度:')
    print('  1) 🟢 P2 - 优化/小修')
    print('  2) 🟡 P1 - 功能问题/可移植性')
    print('  3) 🔴 P0 - 功能失效/启动失败')
    print('  4) ⚪ P3 - 想法/讨论(不算 bug)')
    sev_choice = input('选 [1-4,默认 2]: ').strip() or '2'
    sev_map = {'1': 'P2', '2': 'P1', '3': 'P0', '4': 'P3'}
    severity = sev_map.get(sev_choice, 'P1')

    print()
    print('详细描述(可空,输入 EOF 或两次回车结束):')
    body_lines = []
    empty_count = 0
    while True:
        try:
            line = input('  | ')
        except EOFError:
            break
        if line == 'EOF':
            break
        if not line:
            empty_count += 1
            if empty_count >= 2:
                break
            body_lines.append(line)
        else:
            empty_count = 0
            body_lines.append(line)
    body = '\n'.join(body_lines).rstrip()

    print()
    suggested = input('建议修法(可空): ').strip()

    labels = build_labels(severity)
    print()
    print(f'默认标签: {" ".join(labels)}')
    extra = input('追加标签(空格分隔,可空): ').strip()
    if extra:
        labels.extend(extra.split())

    full_title = f'[{severity}] {title}'
    full_body = body
    if suggested:
        full_body += f'\n\n---\n\n## 建议修法\n\n{suggested}\n'
    full_body += '\n\n---\n\n> 由 `scripts/feedback.py` 创建 · 自动被 3-Agent 流水线扫到'

    print()
    print('=' * 60)
    print('预览:')
    print(f'  标题: {full_title}')
    print(f'  标签: {labels}')
    print(f'  描述({len(body)} 字):')
    for line in (body.split('\n')[:6] if body else ['(空)']):
        print(f'    {line}')
    if body and len(body.split('\n')) > 6:
        print(f'    ... ({len(body.split(chr(10))) - 6} more lines)')
    print('=' * 60)
    confirm = input('确认提交? [y/N]: ').strip().lower()
    if confirm != 'y':
        sys.exit('❌ 取消')

    return full_title, full_body, labels


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--title', help='issue 标题')
    p.add_argument('--body', help='issue 详细描述')
    p.add_argument('--severity', choices=['P0', 'P1', 'P2', 'P3'], help='严重度')
    p.add_argument('--labels', help='追加标签(逗号分隔)')
    p.add_argument('--no-auto-fix', action='store_true', help='不加 auto-fix label')
    p.add_argument('--from-stdin', action='store_true', help='从 stdin 读 JSON')
    return p.parse_args()


def main():
    args = parse_args()

    # 模式 1: stdin JSON
    if args.from_stdin:
        try:
            sys.stdin.reconfigure(encoding='utf-8')
        except Exception:
            pass
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            sys.exit(f'❌ stdin JSON 解析失败: {e}')
        title = payload.get('title', '').strip()
        body = payload.get('body', '').strip()
        severity = payload.get('severity', 'P1')
        labels = build_labels(severity, extra=payload.get('labels'))
        full_title = f'[{severity}] {title}' if title else title
        full_body = body + '\n\n---\n\n> 由 feedback.py --from-stdin 创建'
    # 模式 2:命令行参数
    elif args.title and args.severity:
        title = args.title.strip()
        body = (args.body or '').strip()
        severity = args.severity
        labels = build_labels(severity)
        if args.labels:
            labels.extend(args.labels.split(','))
        if args.no_auto_fix and 'auto-fix' in labels:
            labels.remove('auto-fix')
        full_title = f'[{severity}] {title}'
        full_body = body + '\n\n---\n\n> 由 feedback.py 创建'
    # 模式 3:交互式
    else:
        if not sys.stdin.isatty():
            sys.exit('❌ 非交互模式必须传 --title + --severity 或 --from-stdin')
        try:
            sys.stdin.reconfigure(encoding='utf-8')
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
        full_title, full_body, labels = interactive_input()

    if not full_title:
        sys.exit('❌ 标题必填')

    print(f'推到 GitHub: https://github.com/{REPO}/issues ...')
    try:
        issue = push_issue(full_title, full_body, labels)
    except RuntimeError as e:
        sys.exit(f'❌ {e}')

    print(f'✅ Issue #{issue["number"]} 创建成功')
    print(f'   {issue["html_url"]}')
    if 'auto-fix' in labels:
        print('   已标 auto-fix,下次跑 auto_dispatch.py 会被自动派单')


if __name__ == '__main__':
    main()
