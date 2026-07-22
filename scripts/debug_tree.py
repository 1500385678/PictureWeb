"""debug_tree.py · 单独 debug Git Data API 的 tree endpoint"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = 'https://api.github.com'
REPO = '1500385678/PictureWebWorkflowtest'
TOKEN = os.environ.get('GH_TOKEN', '')
BRANCH = 'main'


def req(p, method='GET', body=None):
    quoted = urllib.parse.quote(p, safe='/')
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body else None
    r = urllib.request.Request(API + quoted, data=data, method=method,
        headers={'Authorization': 'token ' + TOKEN, 'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {'raw': str(e)}


def main():
    if not TOKEN:
        sys.exit('GH_TOKEN 未设')

    print('=== Debug Git Data API ===')

    # 1. base ref
    s, ref = req(f'/repos/{REPO}/git/refs/heads/{BRANCH}')
    print(f'1. base ref: HTTP {s}')
    if s != 200:
        print(f'   err: {ref}')
        return
    base_sha = ref['object']['sha']
    print(f'   sha: {base_sha}')

    # 2. base commit
    s, c = req(f'/repos/{REPO}/git/commits/{base_sha}')
    print(f'2. base commit: HTTP {s}')
    if s != 200:
        print(f'   err: {c}')
        return
    base_tree = c['tree']['sha']
    print(f'   tree: {base_tree}')

    # 3. blob
    with open('.github/workflows/smoke.yml', 'rb') as f:
        raw = f.read()
    content = base64.b64encode(raw).decode('ascii')
    s, blob = req(f'/repos/{REPO}/git/blobs', method='POST',
                  body={'content': content, 'encoding': 'base64'})
    print(f'3. blob: HTTP {s} sha={blob.get("sha", "?")[:7]}')
    if s not in (200, 201):
        print(f'   err: {blob}')
        return

    # 4. tree:不带 base_tree(干净测试)
    tree_entry = [{'path': '.github/workflows/smoke.yml', 'mode': '100644',
                   'type': 'blob', 'sha': blob['sha']}]
    print(f'4a. tree (NO base_tree):')
    s, t = req(f'/repos/{REPO}/git/trees', method='POST', body={'tree': tree_entry})
    print(f'    HTTP {s}: {t.get("message")}')
    if 'errors' in t:
        print(f'    errors: {t["errors"]}')

    # 4b. tree:带 base_tree
    print(f'4b. tree (WITH base_tree):')
    s, t = req(f'/repos/{REPO}/git/trees', method='POST',
               body={'base_tree': base_tree, 'tree': tree_entry})
    print(f'    HTTP {s}: {t.get("message")}')
    if 'errors' in t:
        print(f'    errors: {t["errors"]}')

    # 5. tree 用 prefix '.github/' 单独试
    print(f'5. tree 路径用绝对路径试,path=.github/workflows/smoke.yml 但 type=tree 包含 .github 父节点?')


if __name__ == '__main__':
    main()
