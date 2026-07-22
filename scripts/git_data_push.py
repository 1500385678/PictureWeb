"""git_data_push.py · 用 Git Data API 推文件(支持任意路径,含 .github/)
用法:
  python scripts/git_data_push.py <file1> [file2] ...
适用:Contents API 404 的特殊目录(比如 .github/workflows/*.yml)
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = 'https://api.github.com'
REPO = os.environ.get('PICTUREWEB_REPO', '1500385678/PictureWebWorkflowtest')
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
BRANCH = 'main'


def _request(path, method='GET', body=None):
    if not TOKEN:
        sys.exit('GH_TOKEN 未设')
    quoted = urllib.parse.quote(path, safe='/')
    url = API_BASE + quoted
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            'Authorization': 'token ' + TOKEN,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'git-data-push',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read())
        except Exception:
            err = {'message': str(e)}
        return e.code, err
    except Exception as e:
        return 0, {'message': str(e)}


def push_via_git_data(files, commit_msg):
    """一次 commit 推多个文件 · 用 Git Data API(blobs + tree + commit + ref)"""
    # 1) 拿 base commit
    status, ref_data = _request(f'/repos/{REPO}/git/refs/heads/{BRANCH}')
    if status != 200:
        sys.exit(f'拿 base ref 失败: {ref_data.get("message")}')
    base_sha = ref_data['object']['sha']

    status, commit_data = _request(f'/repos/{REPO}/git/commits/{base_sha}')
    if status != 200:
        sys.exit(f'拿 base commit 失败: {commit_data.get("message")}')
    base_tree = commit_data['tree']['sha']
    print(f'  base commit: {base_sha[:7]}')

    # 2) 为每个文件 create blob
    tree_entries = []
    for rel_path in files:
        with open(rel_path, 'rb') as f:
            raw = f.read()
        # 文本文件用 utf-8 编码(避免 base64 解码 + 文件 BOM 复杂化)
        try:
            text = raw.decode('utf-8')
            content_b64 = base64.b64encode(raw).decode('ascii')
            encoding = 'base64'
        except UnicodeDecodeError:
            content_b64 = base64.b64encode(raw).decode('ascii')
            encoding = 'base64'

        status, blob = _request(
            f'/repos/{REPO}/git/blobs',
            method='POST',
            body={'content': content_b64, 'encoding': encoding},
        )
        if status not in (200, 201):
            sys.exit(f'create blob 失败({rel_path}): {blob.get("message")}')
        tree_entries.append({
            'path': rel_path.replace(os.sep, '/'),
            'mode': '100644',
            'type': 'blob',
            'sha': blob['sha'],
        })
        print(f'  blob: {rel_path} → {blob["sha"][:7]}')

    # 3) create tree
    status, tree_data = _request(
        f'/repos/{REPO}/git/trees',
        method='POST',
        body={'base_tree': base_tree, 'tree': tree_entries},
    )
    if status not in (200, 201):
        sys.exit(f'create tree 失败: {tree_data.get("message")}')
    new_tree = tree_data['sha']
    print(f'  tree: {new_tree[:7]}')

    # 4) create commit
    status, new_commit = _request(
        f'/repos/{REPO}/git/commits',
        method='POST',
        body={
            'message': commit_msg,
            'tree': new_tree,
            'parents': [base_sha],
        },
    )
    if status not in (200, 201):
        sys.exit(f'create commit 失败: {new_commit.get("message")}')
    new_sha = new_commit['sha']
    print(f'  commit: {new_sha[:7]}')

    # 5) update ref
    status, ref_resp = _request(
        f'/repos/{REPO}/git/refs/heads/{BRANCH}',
        method='PATCH',
        body={'sha': new_sha},
    )
    if status != 200:
        sys.exit(f'update ref 失败: {ref_resp.get("message")}')
    print(f'  ref: {BRANCH} → {new_sha[:7]}')
    return new_sha


def main():
    if len(sys.argv) < 2:
        sys.exit('用法:python git_data_push.py <file1> [file2] ...')
    files = sys.argv[1:]
    msg = f'phase6: add {", ".join(os.path.basename(f) for f in files)} (via Git Data API)'
    print(f'=== 推 {len(files)} 个文件(Git Data API) ===')
    sha = push_via_git_data(files, msg)
    print(f'\n✅ 完成:{sha}')


if __name__ == '__main__':
    main()
