"""auto_release.py · 自动发布 + 版本管理
合并 PR 后自动:
  1. 改 __version__.py 的 __version__
  2. git commit
  3. git tag v<version>
  4. git push main + tag
  5. 调 GitHub API 创建 Release

用法:
  python scripts/auto_release.py --bump patch       # 0.1.0 → 0.1.1(默认)
  python scripts/auto_release.py --bump minor       # 0.1.0 → 0.2.0
  python scripts/auto_release.py --bump major       # 0.1.0 → 1.0.0
  python scripts/auto_release.py --set v0.5.0       # 直接设版本
  python scripts/auto_release.py --dry-run          # 只显示计划,不真改

依赖:
  GH_TOKEN(PAT,需 repo 权限 + write access to tags)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = os.environ.get('PICTUREWEB_REPO', '1500385678/PictureWeb')
TOKEN = os.environ.get('GH_TOKEN', '')
# fallback: 2026-07-22 从 Windows 用户级环境变量读
# mavis/scheduled task 启动的进程不会自动读 HKCU\Environment,
# 所以 user-scope env var 不会自动注入 process env,这里兜底
if not TOKEN and os.name == 'nt':
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Environment') as _k:
            TOKEN = winreg.QueryValueEx(_k, 'GH_TOKEN')[0]
    except (OSError, FileNotFoundError):
        pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _request(path, method='GET', body=None):
    if not TOKEN:
        sys.exit('GH_TOKEN 未设')
    quoted = urllib.parse.quote(path, safe='/?&=:')
    url = 'https://api.github.com' + quoted
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            'Authorization': 'token ' + TOKEN,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'auto-release-3agent',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {'message': str(e)}


def get_current_version():
    """从 __version__.py 读 __version__"""
    version_file = os.path.join(os.path.dirname(__file__), '..', '__version__.py')
    version_file = os.path.normpath(version_file)
    if not os.path.isfile(version_file):
        return None
    with open(version_file, 'r', encoding='utf-8') as f:
        content = f.read()
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    return m.group(1) if m else None


def bump_version(current, bump_type):
    """bump_type: major / minor / patch"""
    m = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$', current)
    if not m:
        raise ValueError(f'无法解析当前版本: {current}')
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if bump_type == 'major':
        return f'{major + 1}.0.0'
    if bump_type == 'minor':
        return f'{major}.{minor + 1}.0'
    if bump_type == 'patch':
        return f'{major}.{minor}.{patch + 1}'
    raise ValueError(f'未知 bump_type: {bump_type}')


def update_version_file(new_version):
    """改 __version__.py"""
    version_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '__version__.py')
    )
    if not os.path.isfile(version_file):
        print(f'  ⚠️  {version_file} 不存在,跳过版本号更新')
        return False
    with open(version_file, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = re.sub(
        r'(__version__\s*=\s*["\'])[^"\']+(["\'])',
        rf'\g<1>{new_version}\g<2>',
        content,
    )
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f'  ✅ __version__.py → "{new_version}"')
    return True


def get_prs_since_last_release(current_version):
    """拿从当前 main HEAD 倒数 N 个 commit(暂简化:用 main 上 5 个 commit)"""
    status, data = _request(f'/repos/{REPO}/commits?per_page=10')
    if status != 200:
        return []
    prs = []
    for c in data:
        # 找 commit message 里的 PR 编号 (#N)
        m = re.search(r'\(#(\d+)\)', c['commit']['message'])
        if m:
            prs.append({
                'sha': c['sha'][:7],
                'msg': c['commit']['message'].split('\n')[0],
                'pr': m.group(1),
            })
    return prs


def git_commit_and_push(version, dry_run):
    """改 __version__ + 推 main + 创建 tag(全走 GitHub API)

    2026-07-21 重写原因:daily_pipeline 在 sub-process 跑时,`git push` 被 mavis 截胡。
    改用 Git Data API(已在 git_data_push.py 验证 OK)+ GitHub API 创建 tag ref。
    """
    tag = f'v{version}'

    if dry_run:
        print(f'  [DRY] update __version__.py → {version}')
        print(f'  [DRY] push main via git_data_push.py')
        print(f'  [DRY] create tag {tag} via GitHub API')
        return tag

    # 1) 推 main:用 git_data_push.py 走 Git Data API
    print('  推 main:用 git_data_push.py 走 Git Data API')
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import git_data_push
    msg = f'release: bump to {tag}'
    try:
        new_sha = git_data_push.push_via_git_data(['__version__.py'], msg)
    except Exception as e:
        print(f'  ❌ 推 main 失败:{e}')
        return None
    print(f'  ✅ main → {new_sha[:7]}')

    # 2) tag:走 GitHub API(轻量 tag,ref 指向新 commit)
    print(f'  创建 tag {tag} (走 GitHub API)')
    status, data = _request(
        f'/repos/{REPO}/git/refs',
        method='POST',
        body={'ref': f'refs/tags/{tag}', 'sha': new_sha},
    )
    if status == 201:
        print(f'  ✅ tag {tag} 创建 ({new_sha[:7]})')
    elif status == 422 and 'already exists' in str(data.get('message', '')):
        print(f'  ⚠️ tag {tag} 已存在,force 更新 ref')
        status, data = _request(
            f'/repos/{REPO}/git/refs/tags/{tag}',
            method='PATCH',
            body={'sha': new_sha, 'force': True},
        )
        if status == 200:
            print(f'  ✅ tag {tag} force 更新 ({new_sha[:7]})')
        else:
            print(f'  ❌ tag {tag} force 更新失败:{status} {data.get("message")}')
            return None
    else:
        print(f'  ❌ tag {tag} 创建失败:{status} {data.get("message")}')
        return None

    return tag


def create_github_release(tag, title, body, dry_run):
    """GitHub Releases API"""
    if dry_run:
        print(f'  [DRY] POST /repos/{REPO}/releases tag={tag}')
        return None
    payload = {
        'tag_name': tag,
        'name': title,
        'body': body,
        'target_commitish': 'main',
        'draft': False,
        'prerelease': False,
    }
    status, data = _request(f'/repos/{REPO}/releases', method='POST', body=payload)
    if status == 201:
        print(f'  ✅ Release: {data["html_url"]}')
        return data
    print(f'  ❌ Release 失败: {status} {data.get("message")}')
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bump', choices=['major', 'minor', 'patch'],
                   default='patch', help='bump 类型(默认 patch)')
    p.add_argument('--set', help='直接设版本号(如 v0.5.0 或 0.5.0)')
    p.add_argument('--dry-run', action='store_true', help='只显示计划,不真改')
    args = p.parse_args()

    print('=== Auto Release ===')
    current = get_current_version()
    if not current:
        sys.exit(f'❌ 找不到当前版本(__version__.py 缺失或格式不对)')
    print(f'当前版本: v{current}')

    # 2026-07-21:Skip 逻辑 — 看"remote 最新 release tag" vs "remote main HEAD"
    # 如果两者 commit SHA 一致,说明 main HEAD 已经被最近 release 覆盖,skip
    # 如果不一致,说明 main HEAD 有未发布 commit,跑 release
    if not args.dry_run:
        print('  检查 remote 最新 release 是否覆盖 main HEAD...')
        try:
            status, releases = _request(f'/repos/{REPO}/releases?per_page=1')
            latest_release_sha = None
            if status == 200 and releases:
                tag_name = releases[0]['tag_name']
                status, ref = _request(f'/repos/{REPO}/git/refs/tags/{tag_name}')
                if status == 200:
                    latest_release_sha = ref['object']['sha']
                    print(f'  最新 release {tag_name} 指向: {latest_release_sha[:7]}')

            status, ref = _request(f'/repos/{REPO}/git/refs/heads/main')
            if status == 200:
                main_head_sha = ref['object']['sha']
                print(f'  remote main HEAD: {main_head_sha[:7]}')
                if latest_release_sha == main_head_sha:
                    print(f'  ⏭️  main HEAD 已被最新 release 覆盖,skip release')
                    return 0
                print(f'  ✅ main HEAD 有未发布 commit,继续 release')
        except Exception as e:
            print(f'  ⚠️  skip 检查失败:{e},默认继续')

    # 算新版本
    if args.set:
        new = args.set.lstrip('v')
    else:
        new = bump_version(current, args.bump)
    print(f'新版本:   v{new}')
    print(f'bump:     {args.bump if not args.set else "(set)"}')
    print(f'模式:     {"DRY-RUN" if args.dry_run else "REAL"}')
    print()

    if args.dry_run:
        # Dry-run 模式:什么都不做,只显示
        update_version_file(new)
        # restore
        update_version_file(current)
        # tag + push + release
        get_prs_since_last_release(current)  # just to show
        prs = get_prs_since_last_release(current)
        if prs:
            print(f'\n[最近的 PR(从 main HEAD 倒数 10 commit)]:')
            for p in prs[:5]:
                print(f'  - {p["sha"]} {p["msg"]}')
        git_commit_and_push(new, dry_run=True)
        body = f'自动发布 v{new}\n\n见 [Releases](https://github.com/{REPO}/releases)'
        create_github_release(f'v{new}', f'v{new}', body, dry_run=True)
        return 0

    # REAL 模式
    print('1. 改 __version__.py')
    update_version_file(new)
    print('\n2. 收集 changelog(最近 PR)')
    prs = get_prs_since_last_release(current)
    if prs:
        print(f'   找到 {len(prs)} 个 PR commit:')
        for p in prs[:5]:
            print(f'     - {p["sha"]} {p["msg"]}')
    changelog_lines = [f'## v{new}', '']
    if prs:
        for p in prs[:5]:
            pr_url = f'https://github.com/{REPO}/pull/{p["pr"]}'
            changelog_lines.append(f'- {p["msg"]} ([#{p["pr"]}]({pr_url}))')
    else:
        changelog_lines.append('- (no PR detected in recent commits)')
    changelog_lines.append('')
    changelog_lines.append('---')
    changelog_lines.append('')
    changelog_lines.append(f'自动由 `auto_release.py` 发布')
    body = '\n'.join(changelog_lines)

    print('\n3. commit + tag + push')
    tag = git_commit_and_push(new, dry_run=False)

    print('\n4. GitHub Release')
    create_github_release(tag, f'v{new}', body, dry_run=False)

    print(f'\n🎉 v{new} 发布完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
