"""CanvasWeb v3.0 烟雾测试 · 覆盖所有 API 端点
用法:
  python _smoke.py              # 跑全部
  python _smoke.py --quick      # 只跑 3 个核心
  python _smoke.py --precheck   # 只跑 syntax precheck,不连 HTTP(2026-08-17 加)
期望:✅ 17/17 endpoints OK(11 GET + 6 POST,2026-08-06 v3.5.41 加 2 GET + 1 POST:feedback_arch)
"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE = 'http://127.0.0.1:9002'
TIMEOUT = 10


def syntax_precheck():
    """2026-08-17 加 (P2 夜间迭代 R365):启动前 import 关键模块验证语法 + 兼容性
    防止 server/auth.py 一行 PEP 604 `dict | None` 让 server 整个起不来,
    但 smoke 跑出来只显示 16 条 connection refused,根因藏得很深的尴尬(R222/R224/R357 复盘)
    失败直接 exit 1,不继续 HTTP 测试(避免误导)
    """
    # 让 server.* 的相对 import 找得到:加项目根到 sys.path
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        # 关键模块:覆盖 R222 chat_state / R2026-08-16 P0 auth / R363 llm / R363 ai_video
        from server import auth, config, routes, core  # noqa
        from server.handlers import (  # noqa
            chat_state, canvas_history, llm, ai_video, ai_image,
            canvas, search, semantic, tts, music, image2text,
            upload, favorites, users, optimize_prompt, prompt_templates,
        )
        print('✅ syntax precheck OK · 18 个关键模块 import 成功', flush=True)
        return True
    except Exception as e:
        print(f'❌ server 模块 import 失败: {type(e).__name__}: {e}', flush=True)
        # 给常见错误给提示
        msg = str(e)
        if 'dict | None' in msg or 'unsupported operand' in msg:
            print('   💡 提示:Python 3.9 不支持 PEP 604 union syntax,', flush=True)
            print('      修法 1:在文件顶部加 `from __future__ import annotations`', flush=True)
            print('      修法 2:升级 Python 到 3.10+', flush=True)
        elif 'No module named' in msg:
            print(f'   💡 提示:检查 sys.path 或包结构,可能缺 __init__.py', flush=True)
        return False


# 启动时立即 precheck(可在 --precheck 模式后退出)
if '--precheck' in sys.argv:
    sys.exit(0 if syntax_precheck() else 1)
if not syntax_precheck():
    print('❌ 终止 smoke 测试 — 修好 import 错误再跑', flush=True)
    sys.exit(1)


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


def post(path, payload=None):
    """POST · 返回 (status_code, body_dict or error)"""
    url = BASE + path
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST',
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
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
    """GET 端点 + 校验 body 包含 expect_field
    allow_skip=True:404 / 空数据时不算失败
    """
    status, body = get(path)
    if status == 0:
        print(f'❌ {name:18s} {path:35s} 网络错误: {body.get("error")}', flush=True)
        return False
    if status != 200:
        msg = f'status={status} body={json.dumps(body, ensure_ascii=False)[:100]}'
        if allow_skip and status == 404:
            print(f'⚠️  {name:18s} {path:35s} {msg}(无数据,跳过)', flush=True)
            return True
        print(f'❌ {name:18s} {path:35s} {msg}', flush=True)
        return False
    if expect_field and expect_field not in body:
        print(f'❌ {name:18s} {path:35s} body 缺字段 {expect_field}', flush=True)
        return False
    size = len(json.dumps(body, ensure_ascii=False))
    print(f'✅ {name:18s} {path:35s} 200 bytes={size}', flush=True)
    return True


def check_post(name, path, payload, accept_status, expect_field=None):
    """POST 端点:accept_status 是允许的 status 集合(200/201/400/401/403/409/500)
    2026-07-28 加:用 accept_status 区分"业务预期失败"和"端点坏了"
    例如:login 用错密码期望 401,register 重名期望 409
    """
    status, body = post(path, payload)
    if status == 0:
        print(f'❌ {name:18s} {path:35s} 网络错误: {body.get("error")}', flush=True)
        return False
    if status not in accept_status:
        print(f'❌ {name:18s} {path:35s} status={status} 不在预期 {accept_status} · body={json.dumps(body, ensure_ascii=False)[:100]}', flush=True)
        return False
    if expect_field and isinstance(body, dict) and expect_field not in body:
        print(f'❌ {name:18s} {path:35s} body 缺字段 {expect_field}', flush=True)
        return False
    size = len(json.dumps(body, ensure_ascii=False))
    print(f'✅ {name:18s} {path:35s} {status} bytes={size}', flush=True)
    return True


def main():
    quick = '--quick' in sys.argv

    # ===== GET 端点 =====
    tests = [
        # (name, path, expect_field, allow_skip)
        ('ai_styles',  '/api/ai_styles',   'styles',          False),
        ('ai_views',   '/api/ai_views',    'views',           False),   # 2026-07-24 加:多视角模板
        ('facets',     '/api/facets',      'projects',        False),
        ('favorites',  '/api/favorites',   'ids',             False),
        ('llm_status', '/api/llm_status',  'enabled',         False),
        ('llm_config', '/api/llm_config',  'config',          False),
        ('canvases',   '/api/canvases',    'canvases',        False),
        ('search',     '/api/search?limit=3', 'items',        False),
        # 2026-08-06 v3.5.41 加:反馈 issues 反馈模块
        ('fb_arch_list',    '/api/feedback_arch?platform=gitee&state=open', 'items', False),
        ('fb_arch_daily',   '/api/feedback_arch/daily',   'items',         False),
    ]
    # 动态:画布列表非空时测第一个画布
    _, data = get('/api/canvases')
    if data.get('canvases'):
        cid = data['canvases'][0]['id']
        tests.append(('canvas_get', f'/api/canvas/{cid}', 'id', False))
    else:
        print('⚠️  canvas_get         跳过(画布列表为空)', flush=True)

    if quick:
        tests = tests[:3]

    passed = 0
    failed = []
    for name, path, field, allow_skip in tests:
        if check(name, path, field, allow_skip):
            passed += 1
        else:
            failed.append(name)

    # ===== POST 端点(2026-07-28 加)=====
    # 不快速模式才跑
    if not quick:
        post_tests = [
            # users 鉴权(白名单内,任何 IP 都能调)
            # 1. login 错密码 → 期望 401(用户不存在或密码错)
            ('POST_login_bad',  '/api/users/login',
             {'username': '__smoke_test__', 'password': 'wrong_pw_123'},
             {200, 400, 401}, None),
            # 2. favorites toggle(任意 IP 可调,只是切收藏)→ 返 {id, fav}
            ('POST_fav_toggle', '/api/favorites',
             {'id': 1, 'action': 'add'},
             {200, 201, 400}, 'fav'),
            # 3. canvas create(会真建一个画布;软删时清理)→ 返 {id, name, ...}
            ('POST_canvas_new', '/api/canvas',
             {'action': 'create', 'name': '__smoke_test_canvas__'},
             {200, 201}, 'id'),
            # 4. 拿刚建的画布 ID,做软删
            # 注:由第 5 个测试用变量传递
            ('POST_canvas_soft_del', '/api/canvas',
             None,  # 动态填充
             {200, 201}, 'ok'),
            # 5. db switch(任意 IP 可调)→ body 用 'id' 不是 'db_id' → 返 {ok, active_id}
            ('POST_db_switch',  '/api/db',
             {'id': 'picture'},
             {200, 400}, 'ok'),
            # 6. feedback_arch create 空 body → 期望 400(参数缺失,不真打 GitHub/Gitee 污染)
            #    (2026-08-06 v3.5.41 加:反馈 issues 反馈模块)
            ('POST_fb_arch_empty',  '/api/feedback_arch',
             {},
             {400}, 'error'),
        ]

        # 动态:先建画布拿 ID,再传 delete 用
        _, create_body = post('/api/canvas', {'action': 'create', 'name': '__smoke_test_canvas__'})
        canvas_id = create_body.get('id') if isinstance(create_body, dict) else None
        if canvas_id is not None:
            # 找到软删那条,填入
            for i, (n, p, pl, st, ef) in enumerate(post_tests):
                if n == 'POST_canvas_soft_del':
                    post_tests[i] = (n, p, {'action': 'delete', 'id': canvas_id}, st, ef)
                    break
            print(f'   (smoke) 建测试画布 id={canvas_id} 准备做软删', flush=True)
        else:
            # 拿不到 id 就跳过软删
            post_tests = [t for t in post_tests if t[0] != 'POST_canvas_soft_del']
            print(f'⚠️  POST_canvas_soft_del 跳过(创建失败:{create_body})', flush=True)

        for name, path, payload, accept_status, expect_field in post_tests:
            if check_post(name, path, payload, accept_status, expect_field):
                passed += 1
            else:
                failed.append(name)

        # 清理:把刚建的测试画布再删一次(即使软删已跑过也无所谓,重复 delete 是 noop)
        if canvas_id is not None:
            post('/api/canvas', {'action': 'delete', 'id': canvas_id})

    total = len(tests) + (0 if quick else 6)
    print(f'\n{"✅" if not failed else "❌"} {passed}/{total} endpoints OK', flush=True)
    if failed:
        print(f'失败: {", ".join(failed)}', flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
