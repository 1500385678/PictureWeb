"""daily_pipeline.py · 每天 1 次跑完整 3-Agent 流水线
调度:Windows Task Scheduler 每天 0:00 调
用法:
  python scripts/daily_pipeline.py           # 真跑
  python scripts/daily_pipeline.py --dry-run  # 只看计划

流程:
  1) auto_dispatch.py 扫 GitHub auto-fix issue → 写 .pending/ 队列
  2) Fixer agent(可接 mavis task 启子 session)改代码 + commit + push
  3) auto_tester.py 跑 smoke(本地)
  4) auto_release.py --bump patch → bump version + tag + Release
  5) 写日报到 logs/daily_pipeline.log

依赖:
  GH_TOKEN 环境变量 + git credential.helper(已配)
"""
import datetime
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'daily_pipeline.log')
PENDING_DIR = os.path.join(ROOT, '.pending')
os.makedirs(LOG_DIR, exist_ok=True)


def log(msg):
    ts = datetime.datetime.now().isoformat(timespec='seconds')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def run(cmd, cwd=ROOT, timeout=120, env=None):
    """subprocess wrapper,带超时"""
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8',
        timeout=timeout, env=env or os.environ,
    )


def list_pending():
    """看 .pending/ 队列有多少待办"""
    if not os.path.isdir(PENDING_DIR):
        return []
    return [f for f in os.listdir(PENDING_DIR) if f.startswith('issue-') and f.endswith('.json')]


def step_dispatch(dry):
    """1) 派单"""
    log('1) auto_dispatch.py')
    if dry:
        log('   [DRY-RUN] 跳过')
        return True
    r = run(['python', '-X', 'utf8', 'scripts/auto_dispatch.py'])
    log(r.stdout[:600])
    if r.returncode != 0:
        log(f'   ❌ dispatch 失败: {r.stderr[:300]}')
        return False
    return True


def step_fixer(dry):
    """2) Fixer agent 处理 .pending/ 队列
    当前实现(方案 A):Architect agent 直接当 Fixer
    触发方式:用户在 mavis 跟 Architect 说"处理 .pending/" → 跑 auto_fixer_architect.py
    真实生产(方案 B):mavis task 启子 session(等 mavis CLI 修)
    """
    pending = list_pending()
    log(f'2) Fixer agent: .pending/ 有 {len(pending)} 个待办')
    if not pending:
        log('   (空)跳过 Fixer')
        return True
    for p in pending:
        log(f'   - {p}')

    if dry:
        log('   [DRY-RUN] 不调 Fixer')
        return True

    # 方案 A:让 Architect agent 当 Fixer
    # 检查是否有 "已处理" 标记(.pending/.processed 文件)
    # 如果有,说明用户已经处理过(走 user-driven 模式)
    processed_marker = os.path.join(PENDING_DIR, '.processed')
    if os.path.isfile(processed_marker):
        log('   ✅ .pending/.processed 标记存在,Fixer 已处理(用户驱动模式)')
        return True

    log('   ⚠️ Fixer 待处理 — 触发方式:')
    log('      方案 A(本次):用户跟 Architect 说"处理 .pending/",Architect 跑 auto_fixer_architect.py')
    log('      方案 B(未来):mavis task 启子 session 自动处理')
    log('   → daily_pipeline 继续跑 tester + release(就算代码没改)')
    log('   → 提示:晚上用户说"处理 .pending/",我改完 commit,push')
    log('   → 下次 daily_pipeline 看到 .pending/ 已处理,跑完整流程')
    return True


def step_tester(dry):
    """3) 跑 smoke(本地)
    启 server.py 2 秒 → 跑 auto_tester.py → 杀 server
    """
    log('3) auto_tester.py --local')

    if dry:
        log('   [DRY-RUN] 跳过')
        return True

    # 先杀可能存在的旧 server(用端口 9001/8081 杀,比匹配命令行可靠)
    for p in 8081, 9001:
        try:
            subprocess.run(
                f'Get-NetTCPConnection -LocalPort {p} -State Listen -ErrorAction SilentlyContinue | ForEach-Object {{ taskkill /F /PID $_.OwningProcess 2>$null }}',
                shell=True, capture_output=True, timeout=5,
            )
        except Exception:
            pass
    time.sleep(1)

    # 启 server(用 DEVNULL 避免 buffer block)
    log('   起 server.py ...')
    log_dir = os.path.join(ROOT, 'logs')

    # 2026-07-22:从 server.py 读 port,设 PICTUREWEB_TEST_PORT 给 smoke.py
    port = '8081'  # default
    server_py = os.path.join(ROOT, 'server.py')
    with open(server_py, 'r', encoding='utf-8-sig') as f:
        for line in f:
            m = line.strip().startswith('port = ') and line.strip()
            if m and 'port = ' in line and not 'host' in line and not 'port = ' in line[:line.find('port = ')]:
                port = line.split('=', 1)[1].strip()
                break
    log(f'   server.py 端口:{port}')
    os.environ['PICTUREWEB_TEST_PORT'] = port

    server = subprocess.Popen(
        ['python', '-X', 'utf8', 'server.py'],
        cwd=ROOT,
        stdout=open(os.path.join(log_dir, 'server.out'), 'wb'),
        stderr=open(os.path.join(log_dir, 'server.err'), 'wb'),
    )
    time.sleep(2)

    try:
        r = run(['python', '-X', 'utf8', 'scripts/auto_tester.py', '--local', '--skip-checkout'])
        log(r.stdout[:600])
        if r.returncode != 0:
            log(f'   ❌ smoke 失败: {r.stderr[:300]}')
            return False
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()
    return True


def step_release(dry):
    """4) bump version + tag + Release
    用 GitHub API(已经在 auto_release.py 实现了)
    """
    log('4) auto_release.py --bump patch')
    if dry:
        log('   [DRY-RUN] 跳过')
        return True
    r = run(['python', '-X', 'utf8', 'scripts/auto_release.py', '--bump', 'patch'])
    log(r.stdout[:600])
    if r.returncode != 0:
        log(f'   ❌ release 失败: {r.stderr[:300]}')
        return False
    return True


def main():
    dry = '--dry-run' in sys.argv
    log('=' * 60)
    log(f'Daily Pipeline 启动 · 模式:{"DRY-RUN" if dry else "REAL"}')

    if not step_dispatch(dry):
        log('Pipeline 失败:dispatch')
        return 1
    if not step_fixer(dry):
        log('Pipeline 失败:fixer')
        return 1
    if not step_tester(dry):
        log('Pipeline 失败:tester')
        return 1
    if not step_release(dry):
        log('Pipeline 失败:release')
        return 1

    log('Daily Pipeline 全部完成 ✅')
    log('=' * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
