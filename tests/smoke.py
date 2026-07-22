"""PictureWebWorkflowtest 烟雾测试
用法:
  python tests/smoke.py           # 跑全部(默认 8081)
  python tests/smoke.py --quick   # 只跑 3 个核心
  PICTUREWEB_TEST_PORT=9001 python tests/smoke.py   # 改端口
期望:✅ N/N endpoints OK
"""
import json
import os
import sys
import urllib.error
import urllib.request

PORT = os.environ.get('PICTUREWEB_TEST_PORT', '8081')
BASE = f'http://127.0.0.1:{PORT}'
TIMEOUT = 5


def get(path):
    """GET · 返回 (status_code, body_dict or error)"""
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            body = json.loads(r.read())
            return r.status, body
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read())
        except Exception:
            err = {'error': str(e)}
        return e.code, err
    except Exception as e:
        return 0, {'error': str(e)}


def check(name, path, expect_field, allow_skip=False):
    """GET 端点 + 校验 body 包含 expect_field"""
    status, body = get(path)
    if status == 0:
        print(f'❌ {name:25s} {path:35s} 网络错误: {body.get("error")}', flush=True)
        return False
    if status != 200:
        msg = f'status={status} body={json.dumps(body, ensure_ascii=False)[:100]}'
        if allow_skip and status == 404:
            print(f'⚠️  {name:25s} {path:35s} {msg}(无数据,跳过)', flush=True)
            return True
        print(f'❌ {name:25s} {path:35s} {msg}', flush=True)
        return False
    if expect_field and expect_field not in body:
        print(f'❌ {name:25s} {path:35s} body 缺字段 {expect_field}', flush=True)
        return False
    size = len(json.dumps(body, ensure_ascii=False))
    print(f'✅ {name:25s} {path:35s} 200 bytes={size}', flush=True)
    return True


def main():
    quick = '--quick' in sys.argv

    # 测 3 个核心 API(/ 返回 HTML,不在 JSON smoke 范围)
    tests = [
        # (name, path, expect_field, allow_skip)
        ('facets',         '/api/facets',      'projects', False),
        ('favorites',      '/api/favorites',   'favorites', False),
        ('search',         '/api/search?limit=3', 'items', False),
    ]

    if quick:
        tests = tests[:3]

    passed = 0
    failed = []
    for name, path, field, allow_skip in tests:
        if check(name, path, field, allow_skip):
            passed += 1
        else:
            failed.append(name)

    total = len(tests)
    print(f'\n{"✅" if not failed else "❌"} {passed}/{total} endpoints OK', flush=True)
    if failed:
        print(f'失败: {", ".join(failed)}', flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
