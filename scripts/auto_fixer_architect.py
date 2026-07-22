"""auto_fixer_architect.py · 方案 A:Architect agent 直接当 Fixer
读取 .pending/ 队列 → 处理已知 issue 模式 → 改代码 → commit → push → 标记 processed

用法:
  python scripts/auto_fixer_architect.py              # 处理所有 .pending/
  python scripts/auto_fixer_architect.py --issue 12   # 处理指定 issue
  python scripts/auto_fixer_architect.py --dry-run    # 只看计划

支持的 issue 模式(可扩展):
  - 'ADMIN_IPS 注释' → 改 server.py 用 f-string 拼 IP
  - 'PICTUREWEB_HOME' / '环境变量' → 改 server.py 用 os.environ.get
  - 'import hashlib' / '死代码' → 删 import 行的某模块名
  - 'WRITE_PATHS 死列表' → 在 do_POST 顶部加 'if path not in WRITE_PATHS: 404'
  - 'start_hidden.vbs 路径' → 改 start_hidden.vbs 用相对路径
  - 默认:print issue body,等 Architect 在 mavis 客户端处理
"""
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PENDING_DIR = os.path.join(ROOT, '.pending')
LOG_FILE = os.path.join(ROOT, 'logs', 'fixer.log')
PROCESSED_MARKER = os.path.join(PENDING_DIR, '.processed')
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


def log(msg):
    ts = datetime.datetime.now().isoformat(timespec='seconds')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def load_issue(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_pending():
    if not os.path.isdir(PENDING_DIR):
        return []
    return [f for f in os.listdir(PENDING_DIR) if f.startswith('issue-') and f.endswith('.json')]


# ============= 已知 issue 处理器 =============

def fix_admin_ips_comment(issue):
    """修 ADMIN_IPS 注释和错误消息不一致(Issue #3)"""
    server_py = os.path.join(ROOT, 'server.py')
    with open(server_py, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    # 1) 修错误消息用 f-string
    new = content.replace(
        "'error': '权限不足:此操作仅限本机 Mac (127.0.0.1 / 192.168.0.100)'",
        """'error': f'权限不足:此操作仅限本机({\" / \".join(ADMIN_IPS)})'"""
    )
    # 2) 修 docstring
    new = new.replace(
        '"""检查请求是否来自本机 Mac(127.0.0.1 / 192.168.0.100)"""',
        '"""检查请求是否来自 ADMIN_IPS(自动从 config 同步)"""'
    )
    if new == content:
        return False, '没找到目标字符串(可能已修过)'
    with open(server_py, 'w', encoding='utf-8-sig') as f:
        f.write(new)
    return True, 'server.py 改了 2 处 IP 注释'


def fix_import_hashlib(issue):
    """删 import hashlib(死代码)"""
    server_py = os.path.join(ROOT, 'server.py')
    with open(server_py, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    new = re.sub(
        r'import\s+sqlite3,\s*os,\s*sys,\s*json,\s*base64,\s*hashlib',
        'import sqlite3, os, sys, json, base64  # 2026-07-21 Issue #6:删 hashlib 死代码',
        content
    )
    if new == content:
        return False, '没找到目标 import'
    with open(server_py, 'w', encoding='utf-8-sig') as f:
        f.write(new)
    return True, 'server.py 删了 hashlib 死 import'


def fix_write_paths(issue):
    """在 do_POST 顶部加 'if path not in WRITE_PATHS: 404'"""
    server_py = os.path.join(ROOT, 'server.py')
    with open(server_py, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    if 'if parsed.path not in WRITE_PATHS' in content:
        return False, '已修过'
    # 在 do_POST 顶部
    pattern = r'(    def do_POST\(self\):\n        parsed = urllib\.parse\.urlparse\(self\.path\)\n)'
    new = re.sub(
        pattern,
        r'\1        # Issue #8:统一权限检查(WRITE_PATHS 之前是死列表)\n        if parsed.path not in WRITE_PATHS:\n            self.send_response(404); self.end_headers(); return\n',
        content
    )
    if new == content:
        return False, '没找到 do_POST 入口'
    with open(server_py, 'w', encoding='utf-8-sig') as f:
        f.write(new)
    return True, 'server.py do_POST 顶部加 WRITE_PATHS 校验'


def fix_start_hidden_vbs(issue):
    """修 start_hidden.vbs 用相对路径(Issue #1)"""
    vbs = os.path.join(ROOT, 'start_hidden.vbs')
    if not os.path.isfile(vbs):
        return False, 'start_hidden.vbs 不存在'
    new_content = '''' PictureWeb 自动启动(用相对路径,跟 vbs 所在目录)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir
WshShell.Run "python.exe -X utf8 """ & scriptDir & "\\server.py""", 0, False
Set WshShell = Nothing
'''
    with open(vbs, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return True, 'start_hidden.vbs 改用 GetParentFolderName 拿脚本目录'


def default_handler(issue):
    """默认:不自动改,print 提示"""
    title = issue.get('issue_title', '')
    body = issue.get('issue_body', '')[:500]
    log(f'   缺自动改逻辑(manual mode):')
    log(f'   标题:{title}')
    log(f'   body(前 500 字):{body}')
    return False, '需要 Architect 手工改(目前未实现自动改逻辑)'


# 关键词 → 处理器
HANDLERS = [
    (re.compile(r'ADMIN_IPS|权限不足|本机 Mac|错误消息.*不一致', re.I), fix_admin_ips_comment),
    (re.compile(r'import\s+hashlib|死代码|死 import', re.I), fix_import_hashlib),
    (re.compile(r'WRITE_PATHS|死列表|do_POST.*统一', re.I), fix_write_paths),
    (re.compile(r'start_hidden\.vbs|启动器|隐藏窗口', re.I), fix_start_hidden_vbs),
]


def dispatch(issue):
    title = issue.get('issue_title', '')
    body = issue.get('issue_body', '')
    text = title + '\n' + body
    for pattern, handler in HANDLERS:
        if pattern.search(text):
            log(f'   匹配:{handler.__name__}')
            return handler(issue)
    return default_handler(issue)


# ============= 主流程 =============

def commit_and_push(message):
    """本地 commit + push(走 GitHub API,因为 git push 在 sub-shell 失败)"""
    log(f'   commit + push:{message[:60]}...')
    # 1) add + commit
    subprocess.run(['git', 'add', '-A'], check=True, capture_output=True, text=True)
    subprocess.run(
        ['git', 'commit', '-m', message],
        check=True, capture_output=True, text=True,
    )
    # 2) push(走 git_data_push.py)
    log('   推:用 git_data_push.py 推本次改动文件')
    # 看 diff 哪些文件改了
    r = subprocess.run(['git', 'diff', '--name-only', 'HEAD~1'], capture_output=True, text=True)
    changed = [f for f in r.stdout.strip().split('\n') if f and not f.startswith('?')]
    log(f'   改动文件:{changed}')
    for f in changed:
        try:
            r = subprocess.run(
                ['python', '-X', 'utf8', 'scripts/git_data_push.py', f],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                log(f'   ❌ 推 {f} 失败:{r.stderr[:200]}')
            else:
                log(f'   ✅ 推 {f} OK')
        except Exception as e:
            log(f'   ❌ 推 {f} 异常:{e}')


def mark_processed():
    """写 .pending/.processed 标记"""
    with open(PROCESSED_MARKER, 'w', encoding='utf-8') as f:
        f.write(f'processed_at={datetime.datetime.now().isoformat(timespec="seconds")}\n')


def main():
    dry = '--dry-run' in sys.argv
    only_issue = None
    for i, arg in enumerate(sys.argv):
        if arg == '--issue' and i + 1 < len(sys.argv):
            only_issue = int(sys.argv[i + 1])

    log('=' * 60)
    log(f'Auto Fixer (方案 A · Architect) · 模式:{"DRY-RUN" if dry else "REAL"}')

    pending = list_pending()
    if only_issue:
        pending = [f'issue-{only_issue}.json']
    if not pending:
        log('  .pending/ 空,无待办')
        return 0

    log(f'  找到 {len(pending)} 个待办:')

    for p in pending:
        log('')
        log(f'>>> 处理 {p}')
        path = os.path.join(PENDING_DIR, p)
        try:
            issue = load_issue(path)
        except Exception as e:
            log(f'   ❌ 读 issue 失败:{e}')
            continue

        log(f'   标题:{issue.get("issue_title", "")}')

        if dry:
            log('   [DRY-RUN] 跳过改')
            continue

        ok, msg = dispatch(issue)
        log(f'   {msg}')
        if ok:
            commit_and_push(f'fix({p.replace(".json", "")}): {issue.get("issue_title", "")[:50]}')

    mark_processed()
    log('')
    log('✅ .pending/.processed 标记写好,daily_pipeline 下次跑会跳过 Fixer stub')
    log('=' * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
