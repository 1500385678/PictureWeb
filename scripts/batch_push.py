"""batch_push.py · 批量把本地文件推到 GitHub(用 Contents API,绕开 git 协议)
用法:
  python scripts/batch_push.py <file1> <file2> ...
例:
  python scripts/batch_push.py docs/phase6-design.md scripts/auto_dispatch.py
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
BRANCH = 'main'
COMMIT_MSG_PREFIX = 'phase6: add automation skeleton'


def _request(path, method='GET', body=None):
    if not TOKEN:
        sys.exit('GH_TOKEN 未设')
    # 路径里的中文/特殊字符必须 quote
    quoted_path = urllib.parse.quote(path, safe='/')
    url = API_BASE + quoted_path
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            'Authorization': 'token ' + TOKEN,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'batch-push',
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


def push_file(rel_path, commit_msg=None):
    """推一个文件(覆盖 if exists)"""
    if not os.path.isfile(rel_path):
        print(f'  ❌ 本地不存在:{rel_path}')
        return False
    with open(rel_path, 'rb') as f:
        raw = f.read()
    content_b64 = base64.b64encode(raw).decode('ascii')
    name = os.path.basename(rel_path)
    api_path = rel_path.replace(os.sep, '/')

    # 查现有 SHA(避免覆盖冲突)
    status, data = _request(f'/repos/{REPO}/contents/{api_path}')
    payload = {
        'message': commit_msg or f'{COMMIT_MSG_PREFIX} · {name}',
        'content': content_b64,
        'branch': BRANCH,
    }
    if status == 200 and 'sha' in data:
        payload['sha'] = data['sha']
        print(f'  覆盖: {rel_path} (sha {data["sha"][:7]})')
    elif status == 404:
        print(f'  创建: {rel_path}')
    else:
        print(f'  创建: {rel_path} (查 SHA 返 {status})')

    status, data = _request(
        f'/repos/{REPO}/contents/{api_path}',
        method='PUT', body=payload
    )
    if status in (200, 201):
        print(f'    ✅ {data["commit"]["sha"][:7]} · {data["content"]["html_url"]}')
        return True
    # 详细错误
    msg = data.get('message') or ''
    if 'errors' in data:
        msg += ' · ' + json.dumps(data['errors'], ensure_ascii=False)
    print(f'    ❌ {status}: {msg}')
    return False


def main():
    if len(sys.argv) < 2:
        sys.exit('用法:python batch_push.py <file1> [file2] ...')
    files = sys.argv[1:]
    print(f'=== 批量推 {len(files)} 个文件到 {REPO}/{BRANCH} ===')
    ok = 0
    for f in files:
        if push_file(f):
            ok += 1
    print(f'\n=== {ok}/{len(files)} 成功 ===')
    return 0 if ok == len(files) else 1


if __name__ == '__main__':
    sys.exit(main())
