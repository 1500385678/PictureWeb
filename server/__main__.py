"""CanvasWeb v3.0 入口 · 启动 + 静态资源 + 路由分发
依赖:./config ./core ./img ./routes ./handlers/canvas
被谁调用:python -m server(从 _v25/ 目录跑)
改前必读:API 端点完整契约见 _v25/api_contract.md
"""
import json
import os
import sys
import urllib.parse

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .config import (
    DB, IMG_ROOT, MAX_CONCURRENT, PORT, CLIENT_DIR, BASE_DIR,
    seed_from_v1,
)
from .core import BaseHandler, LimitedCanvasServer
from . import auth  # 2026-07-24 加:用户/会话/锁
from . import logging_setup  # 2026-07-26 加:日志配置(写到 logs/canvasweb.log + stdout)
logging_setup.setup()
from .handlers.canvas import init_db as init_canvas_db
from .handlers.ai_image import init_ai_db   # 2026-07-09 加:AI 独立 DB
from .handlers.ai_video import init_ai_videos_db   # 2026-07-09 加:AI 视频独立 DB
from .handlers.image2text import init_i2t_db   # 2026-07-15 加:图生文独立 DB
from .handlers.tts import init_tts_db   # 2026-07-15 加:TTS 独立 DB(共享 ai_images.db)
from . import routes, img


# ===== 静态资源 MIME(扩展 config.MIME_MAP)=====
_EXTRA_MIME = {
    'html': 'text/html; charset=utf-8',
    'js':   'application/javascript; charset=utf-8',
    'mjs':  'application/javascript; charset=utf-8',
    'css':  'text/css; charset=utf-8',
    'json': 'application/json; charset=utf-8',
    'svg':  'image/svg+xml',
    'ico':  'image/x-icon',
    'txt':  'text/plain; charset=utf-8',
    'map':  'application/json; charset=utf-8',
}


class CanvasHandler(BaseHandler):
    """主 handler · GET 静态资源 / 图片 / API;POST 全部走路由"""

    def do_GET(self):
        # 2026-07-14 修:self.path 在 SimpleHTTPRequestHandler 已 latin-1 unquote,
        # 中文字符 percent-encoded 后被错误解码。重新用 UTF-8 unquote 一次。
        if any(ord(c) > 127 for c in self.path):
            try:
                self.path = urllib.parse.unquote(self.path, encoding='utf-8', errors='strict')
            except UnicodeDecodeError:
                pass
        parsed = urllib.parse.urlparse(self.path)
        # 1) /img/thumbs/ 缩略图(2026-07-09 加 · 优先匹配,必须在 /img/ 之前)
        if parsed.path.startswith('/img/thumbs/'):
            img.serve_thumb(self, parsed)
            return
        # 2) /img/ /upload/ 走图片服务
        if parsed.path.startswith('/img/'):
            img.serve_img(self, parsed)
            return
        if parsed.path.startswith('/upload/'):
            img.serve_upload(self, parsed)
            return
        # 3) /api/* 走路由
        if parsed.path.startswith('/api/'):
            routes.dispatch(self, 'GET', parsed, None)
            return
        # 4) 其它 → 静态资源(client/)
        serve_static(self, parsed)

    def do_POST(self):
        # 2026-07-14 修:中文路径 UTF-8 二次 unquote(同 do_GET 注释)
        if any(ord(c) > 127 for c in self.path):
            try:
                self.path = urllib.parse.unquote(self.path, encoding='utf-8', errors='strict')
            except UnicodeDecodeError:
                pass
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length else b''
        try:
            data = json.loads(raw or b'{}')
        except Exception:
            data = {}
        routes.dispatch(self, 'POST', parsed, data)

    # 2026-07-24 加:DELETE 支持(canvas_lock 释放锁用)
    def do_DELETE(self):
        if any(ord(c) > 127 for c in self.path):
            try:
                self.path = urllib.parse.unquote(self.path, encoding='utf-8', errors='strict')
            except UnicodeDecodeError:
                pass
        parsed = urllib.parse.urlparse(self.path)
        routes.dispatch(self, 'DELETE', parsed, None)


def serve_static(handler, parsed):
    """从 CLIENT_DIR 服务 HTML / CSS / JS · 0 缓存(AI 改完即生效)
    路径安全:不允许 .. 跳出 CLIENT_DIR
    """
    rel = parsed.path.lstrip('/').split('?', 1)[0].split('#', 1)[0]
    if not rel or rel.endswith('/'):
        rel = 'index.html'
    # 友好短链:/board → board.html
    if rel == 'board':
        rel = 'board.html'
    full = os.path.normpath(os.path.join(CLIENT_DIR, rel))
    # 路径安全
    client_root = os.path.normpath(CLIENT_DIR)
    if not full.startswith(client_root + os.sep) and full != client_root:
        handler.safe_error(403, 'Forbidden')
        return
    if not os.path.isfile(full):
        handler.safe_error(404, f'Not found: {rel}')
        return
    ext = full.rsplit('.', 1)[-1].lower()
    mime = _EXTRA_MIME.get(ext, 'application/octet-stream')
    try:
        sz = os.path.getsize(full)
        with open(full, 'rb') as f:
            body = f.read()
        handler.send_response(200)
        handler.send_header('Content-Type', mime)
        handler.send_header('Content-Length', str(len(body)))
        # HTML / CSS / JS 不缓存 · AI 改完即生效
        handler.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        handler.send_header('Pragma', 'no-cache')
        handler.send_header('Expires', '0')
        handler.end_headers()
        handler.wfile.write(body)
    except Exception as e:
        # 2026-07-23 改:Windows OSError 消息可能含中文(拒绝访问 / 文件正被使用 等)
        # 之前直接 send_error(500, str(e)) 会在含中文时让进程死
        handler.safe_error(500, f'static serve failed: {e}')


if __name__ == '__main__':
    # 首次启动 · 从 v1 复制 favorites / LLM config(独立副本,不回写)
    seed_from_v1()
    init_canvas_db()
    auth.init_auth_db()   # 2026-07-24 加:用户/会话/画布锁表(共享 canvas_state.db)
    init_ai_db()   # 2026-07-09 加:AI 图独立 DB(Output/ai_images.db)
    init_ai_videos_db()   # 2026-07-09 加:AI 视频独立 DB(Output/ai_videos.db)
    init_i2t_db()   # 2026-07-15 加:图生文任务表(共享 ai_images.db)
    init_tts_db()   # 2026-07-15 加:TTS 任务表(共享 ai_images.db)
    # 2026-08-17 加:启动时预建 5 个画布 DB(避免前端下拉显示 5 个但磁盘只有 1 个)
    # 之前是首次切到才建,新部署/新机器会让用户看到"文件不存在"假象
    try:
        from . import config as _cfg
        for _did, _info in _cfg.CANVAS_DATABASES.items():
            _p = _info['db_path']
            if not os.path.isfile(_p):
                import sqlite3 as _sq
                _c = _sq.connect(_p)
                _c.execute('''CREATE TABLE IF NOT EXISTS canvases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    layout_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )''')
                _c.execute('ALTER TABLE canvases ADD COLUMN owner_id INTEGER')
                _c.execute('ALTER TABLE canvases ADD COLUMN is_deleted INTEGER DEFAULT 0')
                _c.execute('CREATE INDEX IF NOT EXISTS idx_canvases_owner ON canvases(owner_id)')
                _c.commit()
                _c.close()
                print(f'[startup] 预建画布 DB: {_did} → {_p}', flush=True)
    except Exception as _e:
        print(f'[startup] 预建画布 DB 失败(不影响启动): {_e}', flush=True)
    os.chdir(BASE_DIR)
    print(f'=== CanvasWeb v3.0 启动 ===', flush=True)
    print(f'本地:   http://127.0.0.1:{PORT}/', flush=True)
    print(f'局域网: http://192.168.181.136:{PORT}/', flush=True)
    print(f'DB:       {DB}', flush=True)
    print(f'IMG_ROOT: {IMG_ROOT}', flush=True)
    print(f'CLIENT:   {CLIENT_DIR}', flush=True)
    print(f'并发上限: {MAX_CONCURRENT}', flush=True)
    print(f'(v1=8082 留对照 · v2=8083 留对照 · v3.0={PORT})', flush=True)
    # 2026-07-09 加:后台预生成缩略图(不阻塞启动)
    try:
        from .thumbs import pregenerate_async
        pregenerate_async()
    except Exception as e:
        print(f'[thumbs] pregenerate skipped: {e}', flush=True)
    try:
        LimitedCanvasServer(('0.0.0.0', PORT), CanvasHandler).serve_forever()
    except OSError as e:
        print(f'端口 {PORT} 占用: {e}', flush=True)
        import time
        time.sleep(10)
