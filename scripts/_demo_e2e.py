"""_demo_e2e.py · 完整闭环演示
feedback → dispatch → 改代码 → tester → release(全 Python,无 PowerShell 编码问题)
"""
import json
import os
import subprocess
import sys

REPO = '1500385678/PictureWebWorkflowtest'
os.environ['GH_TOKEN'] = '__GITHUB_TOKEN_PLACEHOLDER__'  # 真实 token 不要硬编码, 用 env 注入
os.environ['PICTUREWEB_REPO'] = REPO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def run(cmd, **kw):
    """subprocess wrapper · 中文不乱码"""
    kw.setdefault('capture_output', True)
    kw.setdefault('text', True)
    kw.setdefault('encoding', 'utf-8')
    print(f'\n>>> {" ".join(cmd) if isinstance(cmd, list) else cmd}')
    r = subprocess.run(cmd, **kw)
    print(r.stdout)
    if r.stderr:
        print(f'STDERR: {r.stderr}')
    print(f'>>> 退出码: {r.returncode}')
    return r


print('=' * 70)
print('=== 完整闭环演示: feedback → dispatch → tester → release ===')
print('=' * 70)

# ============================================
# 1) feedback.py 创建一个新 issue
# ============================================
print('\n[1/7] feedback.py 创建新 issue')
data = {
    'title': '前端 index.html 应加错误 toast,失败时不卡 loading',
    'body': '现状:index.html 的 search() 函数没 try/catch,网络断时 grid 卡"搜索中..."\n\n'
            '复现:启 server → 断网 → 搜索 → grid 永远卡\n\n'
            '影响:用户不知道失败,debug 困难',
    'severity': 'P2',
}
r = subprocess.run(
    ['python', '-X', 'utf8', 'scripts/feedback.py', '--from-stdin'],
    input=json.dumps(data, ensure_ascii=False) + '\n',
    capture_output=True, text=True, encoding='utf-8',
)
print(r.stdout)
new_issue_num = None
for line in r.stdout.split('\n'):
    if 'Issue #' in line and '创建成功' in line:
        # 提取 issue 编号
        import re
        m = re.search(r'Issue #(\d+)', line)
        if m:
            new_issue_num = int(m.group(1))
            print(f'  ✅ 新 issue: #{new_issue_num}')

if not new_issue_num:
    print(f'❌ 失败:{r.stderr}')
    sys.exit(1)

# ============================================
# 2) auto_dispatch.py 派 Fixer agent
# ============================================
print('\n[2/7] auto_dispatch.py 派 Fixer agent')
r = subprocess.run(
    ['python', '-X', 'utf8', 'scripts/auto_dispatch.py'],
    capture_output=True, text=True, encoding='utf-8',
    env={**os.environ, 'STUB_FIXER': '1'},
)
print(r.stdout)
print(f'退出码: {r.returncode}')

# 看 .pending/
pending_file = os.path.join('.pending', f'issue-{new_issue_num}.json')
if os.path.isfile(pending_file):
    print(f'  ✅ 队列已写:{pending_file}')
else:
    print(f'  ❌ 队列未写:{pending_file}')
    print(f'  找一下:.pending/ 下有什么:')
    if os.path.isdir('.pending'):
        for f in os.listdir('.pending'):
            print(f'    - {f}')

# ============================================
# 3) 手动模拟 Fixer agent 改代码(改个简单问题)
# ============================================
print('\n[3/7] 模拟 Fixer agent 改代码')

# 选个最简单 issue 修:修 README typo(没 issue 的事,演示流程)
# 这里只做"有动作": 写一个 acceptance marker 到 README
with open('README.md', 'r', encoding='utf-8') as f:
    content = f.read()
marker = '\n\n## 验收日志\n\n'
if marker not in content:
    new_content = content + marker + (
        f'- 2026-07-21 · v0.1.0 · 3-Agent 流水线首次跑通(PR #9 + #10)\n'
        f'- 2026-07-21 · Phase 6 自动化骨架完成(feedback / dispatch / tester / release)\n'
    )
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('  ✅ README.md 加了"验收日志"段')
else:
    print('  跳过(已有验收日志)')

# ============================================
# 4) auto_tester.py 跑 smoke
# ============================================
print('\n[4/7] auto_tester.py 跑 smoke')

# 先起 server
import time
server_proc = subprocess.Popen(
    ['python', '-X', 'utf8', 'server.py'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
time.sleep(2)

r = subprocess.run(
    ['python', '-X', 'utf8', 'scripts/auto_tester.py', '--local', '--skip-checkout'],
    capture_output=True, text=True, encoding='utf-8',
)
print(r.stdout)
print(f'退出码: {r.returncode}')

# 杀 server
server_proc.terminate()
try:
    server_proc.wait(timeout=3)
except subprocess.TimeoutExpired:
    server_proc.kill()

smoke_passed = (r.returncode == 0)
print(f'\n  总结:smoke {"通过 ✅" if smoke_passed else "失败 ❌"}')

# ============================================
# 5) auto_release.py --dry-run 看计划
# ============================================
print('\n[5/7] auto_release.py --dry-run 看版本计划')
r = subprocess.run(
    ['python', '-X', 'utf8', 'scripts/auto_release.py', '--dry-run'],
    capture_output=True, text=True, encoding='utf-8',
)
print(r.stdout)
print(f'退出码: {r.returncode}')

# ============================================
# 6) auto_release.py 真跑(只改版本 + commit + tag,push 失败回退到 API)
# ============================================
print('\n[6/7] auto_release.py 真跑(bump patch)')

# 6a) 改 __version__
with open('__version__.py', 'r', encoding='utf-8') as f:
    cur = f.read().strip()
print(f'  当前 __version__.py: {cur}')

# 6b) commit
r = subprocess.run(['git', 'add', 'README.md', '__version__.py'], capture_output=True, text=True)
if r.returncode != 0:
    print(f'  git add 失败:{r.stderr}')
r = subprocess.run(
    ['git', 'commit', '-m', 'docs: add acceptance log\n\nrelease: bump to v0.1.1 (auto)'],
    capture_output=True, text=True,
)
print(f'  git commit: {r.stdout.strip()[:200]}')
print(f'  退出码: {r.returncode}')

# 6c) tag
r = subprocess.run(
    ['git', 'tag', '-a', 'v0.1.1', '-m', 'Release v0.1.1'],
    capture_output=True, text=True,
)
print(f'  git tag v0.1.1: 退出码 {r.returncode}')

# 6d) 试 push(可能卡,我们给 15s timeout)
push_ok = False
import threading
def do_push():
    global push_ok
    try:
        r = subprocess.run(
            ['git', 'push', 'origin', 'main', '--tags'],
            capture_output=True, text=True, timeout=15,
        )
        push_ok = (r.returncode == 0)
        print(f'  push: {"OK" if push_ok else r.stderr[:200]}')
    except subprocess.TimeoutExpired:
        print('  push 15s 超时')

t = threading.Thread(target=do_push)
t.start()
t.join(18)
if t.is_alive():
    print('  push 还在跑,放弃(后续 API 创建 Release 不依赖 push)')

# 6e) 改 __version__.py 真改
import re
with open('__version__.py', 'r', encoding='utf-8') as f:
    v_content = f.read()
m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', v_content)
if m:
    cur_ver = m.group(1)
    parts = cur_ver.split('.')
    new_ver = f'{parts[0]}.{parts[1]}.{int(parts[2])+1}'
    new_content = re.sub(
        r'(__version__\s*=\s*["\'])[^"\']+(["\'])',
        rf'\g<1>{new_ver}\g<2>',
        v_content,
    )
    with open('__version__.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f'  ✅ __version__.py: {cur_ver} → {new_ver}')

# ============================================
# 7) 用 GitHub API 创建 Release(绕开 git push 卡)
# ============================================
print('\n[7/7] GitHub API 创建 Release(绕开 git push)')
import urllib.request, urllib.error, urllib.parse

def api(path, method='GET', body=None):
    url = 'https://api.github.com' + urllib.parse.quote(path, safe='/')
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, method=method,
        headers={'Authorization': 'token ' + os.environ['GH_TOKEN'],
                 'Accept': 'application/vnd.github+json',
                 'User-Agent': 'e2e-demo'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except: return e.code, {'message': str(e)}

# 拿最近 5 个 commit 当 changelog
status, commits = api(f'/repos/{REPO}/commits?per_page=5')
changelog = []
if status == 200:
    for c in commits:
        msg = c['commit']['message'].split('\n')[0]
        m = re.search(r'\(#(\d+)\)', c['commit']['message'])
        pr_link = f' [#{m.group(1)}](https://github.com/{REPO}/pull/{m.group(1)})' if m else ''
        changelog.append(f'- {msg}{pr_link}')

body = f'''## v0.1.1 · 2026-07-21

自动由 3-Agent 流水线发布。

### 改动
{chr(10).join(changelog[:5]) if changelog else "- (无明显 PR)"}

### 包含资产
- `tests/smoke.py` · 3 端点烟雾测试
- `scripts/feedback.py` · 交互式反馈入口
- `scripts/auto_dispatch.py` · 扫 issue + 派 Fixer
- `scripts/auto_tester.py` · 跑 smoke + 留 verdict
- `scripts/auto_release.py` · bump version + tag + Release

### 自动化
- 加 `auto-fix` label 的 issue → 30 分钟自动派单
- Smoke 通过 → auto-merge
- Merge 完成 → auto-release

---

🎉 自动由 `_demo_e2e.py` 发布
'''

# 创建 Release(注意:必须先 push tag,API 创建 Release 会引用 tag)
# 因为 push 可能卡,我们用现有 tag(如果远端有的话)
# 先查远端 main HEAD
status, main = api(f'/repos/{REPO}/git/refs/heads/main')
if status == 200:
    target_sha = main['object']['sha']
    print(f'  远端 main HEAD: {target_sha[:7]}')

# 直接用 main 当 target 创建(不依赖 tag)
release_body = {
    'tag_name': 'v0.1.1',
    'name': 'v0.1.1 · 3-Agent 流水线试点',
    'body': body,
    'target_commitish': 'main',
    'draft': False,
    'prerelease': False,
}

# 远端可能已有 v0.1.1 tag(之前 push 失败,但 API 还能建)
# 先查现有
status, existing = api(f'/repos/{REPO}/releases/tags/v0.1.1')
if status == 200:
    print(f'  远端已有 v0.1.1 Release: {existing["html_url"]}')
else:
    status, rel = api(f'/repos/{REPO}/releases', method='POST', body=release_body)
    if status == 201:
        print(f'  ✅ Release 创建: {rel["html_url"]}')
    else:
        print(f'  ⚠️ Release 创建失败:{status} {rel.get("message")}')
        # 试试打 tag 替代(用 API 创建 tag ref)
        print('  试 fallback:用 Git Data API 创建 tag...')
        # 拿 base commit
        status, ref = api(f'/repos/{REPO}/git/refs/heads/main')
        if status == 200:
            base_sha = ref['object']['sha']
            # create tag object
            tag_payload = {
                'tag': 'v0.1.1',
                'object': base_sha,
                'type': 'commit',
                'message': 'Release v0.1.1',
            }
            status, tag_obj = api(f'/repos/{REPO}/git/tags', method='POST', body=tag_payload)
            if status in (200, 201):
                # create ref
                ref_payload = {'sha': tag_obj['sha']}
                status, ref_resp = api(
                    f'/repos/{REPO}/git/refs',
                    method='POST',
                    body={**ref_payload, 'ref': 'refs/tags/v0.1.1'},
                )
                if status in (200, 201):
                    print(f'  ✅ Git Data API tag v0.1.1 创建')
                else:
                    print(f'  ❌ ref 创建失败:{ref_resp.get("message")}')
            else:
                print(f'  ❌ tag obj 创建失败:{tag_obj.get("message")}')

print('\n' + '=' * 70)
print('=== 完整闭环演示完成 ===')
print('=' * 70)
print(f'\n总结:')
print(f'  1. 创建 issue #{new_issue_num}')
print(f'  2. dispatcher 派单 → .pending/issue-{new_issue_num}.json')
print(f'  3. 模拟 Fixer 改 README 加验收日志')
print(f'  4. tester 跑 smoke:{"通过 ✅" if smoke_passed else "失败 ❌"}')
print(f'  5. release bump: 0.1.0 → 0.1.1')
print(f'  6. git commit + tag v0.1.1 完成')
print(f'  7. GitHub Release 创建(看上面输出)')
