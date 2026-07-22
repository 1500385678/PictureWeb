"""auto_dispatch.py · 3-Agent 流水线调度器
扫 GitHub 上 label=auto-fix 的 open issue,每个 issue 派一个 Fixer agent 处理。

用法:
  python scripts/auto_dispatch.py            # 扫所有 open auto-fix issue,逐一派 Fixer
  python scripts/auto_dispatch.py --dry-run  # 只列出待办,不派
  python scripts/auto_dispatch.py --issue 5  # 只处理指定 issue

设计:
  - 当前实现是骨架:扫 issue + 打印计划,Fixer 派单通过启子 session(用 mavis task)
  - 真实启 Fixer 需要:mavis task <prompt>(当前 mavis CLI 损坏,先用 stub 模式)
  - 后续:接飞书 webhook 通知 / 失败回流 / 多项目并发

依赖:
  - 环境变量 GH_TOKEN(PAT,需要 repo 权限)
  - mavis CLI(后续)
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime

API_BASE = 'https://api.github.com'
REPO = os.environ.get('PICTUREWEB_REPO', '1500385678/PictureWebWorkflowtest')
TOKEN = os.environ.get('GH_TOKEN', '')
LABEL = 'auto-fix'
MAX_RETRIES = 3  # PR 失败回流上限


def _request(path, method='GET', body=None):
    """调 GitHub REST API · 自动加 auth header"""
    if not TOKEN:
        sys.exit('GH_TOKEN 未设。Set-Item Env:GH_TOKEN -Value "ghp_xxx" 后再跑')
    url = API_BASE + path
    data = json.dumps(body).encode('utf-8') if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            'Authorization': 'token ' + TOKEN,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'auto-dispatch-3agent',
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


def list_auto_fix_issues():
    """返回所有 open + label=auto-fix 的 issue 列表"""
    status, data = _request(f'/repos/{REPO}/issues?state=open&labels={LABEL}&per_page=20')
    if status != 200:
        sys.exit(f'列 issue 失败: {data.get("message")}')
    # 排除 PR(PR 也有 issue-style API)
    return [i for i in data if 'pull_request' not in i]


def get_pr_for_issue(issue_number):
    """查 issue 关联的 PR(timeline API)"""
    status, data = _request(f'/repos/{REPO}/issues/{issue_number}/timeline?per_page=30')
    if status != 200:
        return None
    for ev in data:
        if ev.get('event') == 'cross-referenced' and ev.get('source', {}).get('type') == 'issue':
            src = ev['source']['issue']
            if 'pull_request' in src:
                return src
    return None


def count_pr_fix_attempts(pr_number):
    """数 PR 的 fix attempt 次数(用 PR comment 计数 keyword 'attempt N')"""
    status, data = _request(f'/repos/{REPO}/issues/{pr_number}/comments?per_page=100')
    if status != 200:
        return 0
    n = 0
    for c in data:
        body = c.get('body', '') or ''
        # Tester 的 verdict comment 包含 "smoke verdict"
        if 'smoke verdict' in body:
            n += 1
    return n


def dispatch_fix_agent(issue):
    """启 Fixer agent 处理 issue · 当前是 stub(打印 + 写 pending 文件)"""
    issue_num = issue['number']
    issue_title = issue['title']
    issue_body = issue.get('body', '')
    issue_url = issue['html_url']

    print(f'\n=== 派 Fixer agent 处理 #{issue_num}: {issue_title} ===')

    # 1) 检查是否已有 PR 关联
    existing_pr = get_pr_for_issue(issue_num)
    if existing_pr:
        pr_num = existing_pr['number']
        pr_state = existing_pr['state']
        attempts = count_pr_fix_attempts(pr_num)
        print(f'  关联 PR #{pr_num} ({pr_state}) · 已 attempt {attempts}/{MAX_RETRIES} 次')
        if attempts >= MAX_RETRIES:
            print(f'  ⚠️ 达到回流上限({MAX_RETRIES} 次),转人工:在 PR 留 @zhangyong 通知')
            return _escalate_to_human(pr_num, issue)
        print(f'  → Tester 留了 verdict,Fixer 改第 {attempts+1} 轮')
    else:
        attempts = 0
        print(f'  → 首次处理(无关联 PR)')

    # 2) 写 pending 文件(给真实 Fixer agent 看,后续接 mavis task)
    pending_dir = os.path.join(os.path.dirname(__file__), '..', '.pending')
    os.makedirs(pending_dir, exist_ok=True)
    pending_file = os.path.join(pending_dir, f'issue-{issue_num}.json')
    with open(pending_file, 'w', encoding='utf-8') as f:
        json.dump({
            'issue_number': issue_num,
            'issue_title': issue_title,
            'issue_body': issue_body,
            'issue_url': issue_url,
            'attempts': attempts,
            'queued_at': datetime.now().isoformat(timespec='seconds'),
        }, f, ensure_ascii=False, indent=2)
    print(f'  → 写入待办:{pending_file}')

    # 3) stub:打印 Fixer 应做的事(真实环境会启 mavis task)
    if not os.environ.get('STUB_FIXER'):
        print(f'  (生产模式:此处调 mavis task 启 Fixer agent 改代码)')
    else:
        print(f'  (STUB 模式:不真启 Fixer,只把任务写到 .pending/)')

    return {'status': 'queued', 'attempts': attempts}


def _escalate_to_human(pr_num, issue):
    """第 3 次失败:在 PR 留 comment 通知张勇"""
    msg = (
        f'@zhangyong 3-Agent 流水线在 issue #{issue["number"]} 上已达到回流上限 '
        f'({MAX_RETRIES} 次 smoke 失败),需要人工介入。\n\n'
        f'Issue: {issue["html_url"]}\n'
        f'PR:    https://github.com/{REPO}/pull/{pr_num}\n'
    )
    _request(
        f'/repos/{REPO}/issues/{pr_num}/comments',
        method='POST', body={'body': msg}
    )
    print(f'  ✅ @zhangyong 通知已留')
    return {'status': 'escalated'}


def main():
    dry_run = '--dry-run' in sys.argv
    only_issue = None
    for i, arg in enumerate(sys.argv):
        if arg == '--issue' and i + 1 < len(sys.argv):
            only_issue = int(sys.argv[i + 1])

    print(f'=== 3-Agent Dispatcher ===')
    print(f'仓库: {REPO}')
    print(f'扫 label: {LABEL}')
    print(f'模式: {"DRY-RUN" if dry_run else "REAL"}')
    print(f'回流上限: {MAX_RETRIES} 次')
    print()

    issues = list_auto_fix_issues()
    if not issues:
        print('没有待 auto-fix 的 issue。')
        print('  提示:对某个 issue 加 label "auto-fix" 即可被扫到')
        return 0

    if only_issue:
        issues = [i for i in issues if i['number'] == only_issue]
        if not issues:
            print(f'#{only_issue} 不在 auto-fix 列表里')
            return 1

    print(f'找到 {len(issues)} 个待办:')
    for iss in issues:
        print(f'  #{iss["number"]} {iss["title"]}')

    if dry_run:
        return 0

    results = []
    for iss in issues:
        r = dispatch_fix_agent(iss)
        results.append((iss['number'], r.get('status')))

    print(f'\n=== 派单汇总 ===')
    for num, status in results:
        print(f'  #{num}: {status}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
