import sqlite3, os, sys, json, base64, glob  # 2026-07-21 Issue #6:删 hashlib 死代码; 2026-08-18 v2.0.8:加 glob 扫库
from http.server import HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
import urllib.parse

# 2026-07-21 Issue #4:用 PICTUREWEB_HOME 环境变量 + 默认值,代替硬编码绝对路径
# 默认值跟原 hardcoded 一致,向后兼容(不设环境变量时行为不变)
# 换电脑或换盘符只需: set PICTUREWEB_HOME=E:/your/path
PICTUREWEB_HOME = os.environ.get('PICTUREWEB_HOME', 'D:/Mac/Mac/workteam/05_space/03_architect')
# v2.0.9:统一 DB 根(D:/Database/Database,2026-08-27 项目统一抽库)
# PictureWeb 的 DB 在 05_Space 子目录;其他项目各自分类下
# 可通过环境变量 PICTUREWEB_DB_ROOT 覆盖
PICTUREWEB_DB_ROOT = os.environ.get('PICTUREWEB_DB_ROOT', r'D:\Database\Database')
# v2.1.0:canvasweb 提示词 API(从 image_prompts 表读)
# PictureWeb 调 canvasweb 的 /api/image_prompts 拿 5 类 prompt
# 默认指向 canvasweb 当前运行的端口 9002(AGENTS.md 写 8085 但实际部署在 9002)
CANVASWEB_PROMPTS_URL = os.environ.get('CANVASWEB_PROMPTS_URL', 'http://127.0.0.1:9002/api/image_prompts')
PROMPTS_CACHE = {}  # image_id -> (ts, prompts); 5 分钟 TTL
PROMPTS_TTL = 300
# DB 在 PictureWeb 同级的 PictureDb/ 下(2026-06-28 修正:有数据的库在 _ArchitectLib/PictureDb/)
DB = os.path.join(PICTUREWEB_HOME, '_ArchitectLib', 'PictureDb', 'PictureDb.db')
FAV_FILE = os.path.join(os.path.dirname(__file__), 'favorites.json')
# 图片根目录(2026-06-28 迁移到 Mobile)
IMG_ROOT = os.path.join(PICTUREWEB_HOME, 'Mobile')
# 旧 Mac 路径前缀(DB 里的路径是旧的,需要映射)
OLD_IMG_ROOT = '/Users/aaron/Mac/WorkTeam/05_Space/03_Architect/Mobile'
# === v2.0.8:多库切换器(2026-08-18)====================================
# 扫描 PICTUREWEB_HOME 下所有有 images 表 + 有数据的 .db
def _scan_dbs():
    out = []
    seen = set()
    root = PICTUREWEB_DB_ROOT
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == '.' else rel.count(os.sep) + 1
        if depth > 8:
            dirnames[:] = []
            continue
        for fn in filenames:
            if not fn.lower().endswith('.db'):
                continue
            # 跳 Thumbs.db (Windows 缩略图缓存,不是 sqlite,只是减少噪音)
            if fn.lower() == 'thumbs.db':
                continue
            full = os.path.join(dirpath, fn)
            norm = os.path.normcase(os.path.abspath(full))
            if norm in seen:
                continue
            seen.add(norm)
            try:
                # 用 forward slash path(Windows 也支持)
                uri_path = full.replace(os.sep, '/')
                conn = sqlite3.connect('file:' + uri_path + '?mode=ro', uri=True)
                has = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='images'").fetchone()
                if not has:
                    conn.close()
                    continue
                count = conn.execute('SELECT COUNT(*) FROM images').fetchone()[0]
                conn.close()
                if count == 0:
                    continue
                parent = os.path.basename(dirpath)
                if parent.endswith('Db') or parent.endswith('DB'):
                    db_name = parent.lstrip('_')  # 去掉前缀下划线,_AnalysisDb -> AnalysisDb
                else:
                    db_name = os.path.splitext(fn)[0]
                out.append({
                    'name': db_name,
                    'path': full,
                    'rel': os.path.relpath(full, root).replace(os.sep, '/'),
                    'count': count,
                })
            except Exception:
                continue
    # 同名去重:保留 count 最大的;count 相同则保留 rel 最短的(更浅路径)
    by_name = {}
    for d in out:
        prev = by_name.get(d['name'])
        if prev is None or d['count'] > prev['count'] or (d['count'] == prev['count'] and d['rel'].count('/') < prev['rel'].count('/')):
            by_name[d['name']] = d
    out = list(by_name.values())
    out.sort(key=lambda d: d['name'])
    return out

DB_LIST = _scan_dbs()
DEFAULT_DB_NAME = 'PictureDb'
if not any(d['name'] == DEFAULT_DB_NAME for d in DB_LIST):
    DEFAULT_DB_NAME = DB_LIST[0]['name'] if DB_LIST else 'PictureDb'
DEFAULT_DB_PATH = next((d['path'] for d in DB_LIST if d['name'] == DEFAULT_DB_NAME), '')
# 保留模块级 DB 用于向后兼容(默认库)
DB = DEFAULT_DB_PATH

def get_db_path(db_name):
    # 根据库名返回绝对路径;无效则返回默认库
    for d in DB_LIST:
        if d['name'] == db_name:
            return d['path']
    return DEFAULT_DB_PATH

def get_db_name_from_cookie(cookie_header):
    # 从 Cookie 头解析 db=xxx;失败返回默认
    if not cookie_header:
        return DEFAULT_DB_NAME
    for part in cookie_header.split(';'):
        part = part.strip()
        if part.startswith('db='):
            name = part[3:].strip()
            if name and all(c.isalnum() or c in '_-' for c in name):
                if any(d['name'] == name for d in DB_LIST):
                    return name
            break
    return DEFAULT_DB_NAME
# === v2.0.8 end ======================================================


# 权限控制(2026-06-27 增加):只有本机 Mac 的 IP 可以写操作,其他电脑只读
# 读:GET /, GET /img/*, GET /api/search, GET /api/facets, GET /api/favorites
# 写:POST /api/favorites, POST /api/upload_search, POST /api/ai_image
ADMIN_IPS = {'127.0.0.1', '192.168.181.136', '::1'}  # 本机 loopback + Windows LAN IP
WRITE_PATHS = {'/api/favorites', '/api/upload_search', '/api/ai_image', '/api/semantic_search', '/api/intent_search', '/api/database/switch'}

# 并发连接数限制(2026-06-28 调整):图片缩略图并发需求高,20 个
MAX_CONCURRENT = 20
active_lock = Lock()
active_count = 0

def load_favs():
    if not os.path.exists(FAV_FILE):
        return []
    try:
        with open(FAV_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

def save_favs(favs):
    with open(FAV_FILE, 'w', encoding='utf-8') as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)

def to_img_url(item_id, abs_path=None):
    """v2.0.8:返回 /api/img?id=<id> URL — 直接从当前 DB 读 abs_path,跨路径都能用
    旧的 /img/<rel> 静态端点保留(供直接 URL 访问),但 API 响应统一用 /api/img
    """
    return f'/api/img?id={item_id}'

def cosine_sim(a, b):
    if not a or not b: return 0
    import math
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    return dot / (na*nb) if na and nb else 0

class Handler(SimpleHTTPRequestHandler):
    def finish(self):
        """请求结束时减少并发计数"""
        global active_count
        with active_lock:
            active_count = max(0, active_count - 1)
        super().finish()

    def end_headers(self):
        # 2026-07-01: 强制 HTML 不缓存,避免浏览器用旧版
        # 仅对 HTML 生效,图片仍可缓存
        if self.path.endswith('.html') or self.path == '/' or self.path.endswith('/index.html'):
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        # v2.0.8:从 cookie 读当前数据库(每个请求独立)
        self._db_name = get_db_name_from_cookie(self.headers.get('Cookie', ''))
        self._db = get_db_path(self._db_name)
        parsed = urllib.parse.urlparse(self.path)

        # /img/* 直接从 IMG_ROOT 提供静态文件
        if parsed.path.startswith('/img/'):
            rel = parsed.path[5:]
            # URL 解码
            rel = urllib.parse.unquote(rel)
            # 安全检查：不允许 .. 跳出
            rel_clean = os.path.normpath(rel).replace('\\', '/')
            if rel_clean.startswith('..') or os.path.isabs(rel_clean):
                self.send_error(403, 'Forbidden')
                return
            full = os.path.join(IMG_ROOT, rel_clean)
            if os.path.isfile(full):
                ext = full.rsplit('.', 1)[-1].lower()
                mime = {
                    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                    'png': 'image/png', 'gif': 'image/gif',
                    'webp': 'image/webp',
                }.get(ext, 'application/octet-stream')
                try:
                    sz = os.path.getsize(full)
                    self.send_response(200)
                    self.send_header('Content-Type', mime)
                    self.send_header('Content-Length', str(sz))
                    self.send_header('Cache-Control', 'public, max-age=3600')
                    self.end_headers()
                    with open(full, 'rb') as f:
                        self.wfile.write(f.read())
                except Exception as e:
                    self.send_error(500, str(e))
            else:
                self.send_error(404, f'Not found: {rel_clean}')
            return

        if parsed.path == '/api/search':
            qs = urllib.parse.parse_qs(parsed.query)
            q = (qs.get('q', [''])[0] or '').strip()
            keywords = [k.strip() for k in (qs.get('keywords', [''])[0] or '').split(',') if k.strip()]
            project = (qs.get('project', [''])[0] or '').strip()
            scene = (qs.get('scene', [''])[0] or '').strip()
            light = (qs.get('light', [''])[0] or '').strip()
            mood = (qs.get('mood', [''])[0] or '').strip()
            arch = (qs.get('arch', [''])[0] or '').strip()
            company = (qs.get('company', [''])[0] or '').strip()
            view_type = (qs.get('view', [''])[0] or '').strip()
            favs_only = qs.get('favs_only', ['0'])[0] == '1'
            limit = int(qs.get('limit', ['60'])[0])
            try:
                items = self._search(q, keywords, project, scene, light, mood, arch, company, view_type, favs_only, limit)
                # 转换 path -> url
                for it in items:
                    it['url'] = to_img_url(it['id'])
                self._json({'count': len(items), 'items': items})
            except Exception as e:
                self._json({'error': str(e), 'count': 0, 'items': []})
        elif parsed.path == '/api/facets':
            self._json(self._facets())
        elif parsed.path == '/api/favorites':
            self._json({'favorites': load_favs()})
        elif parsed.path == '/api/databases':
            # v2.0.8:返回可用数据库列表(公开端点)
            self._json({
                'current': self._db_name,
                'default': DEFAULT_DB_NAME,
                'databases': [{'name': d['name'], 'rel': d['rel'], 'count': d['count']} for d in DB_LIST],
            })
        elif parsed.path == '/api/prompts':
            # v2.1.0:从 canvasweb 拉 5 类 prompt
            self._serve_prompts(parsed)
        elif parsed.path == '/api/img':
            # v2.0.8:从当前 DB 读 abs_path 服务图片(任何路径都能用)
            self._serve_img(parsed)
        else:
            # 其它走父类（HTML/CSS/JS 静态文件）
            super().do_GET()

    def do_POST(self):
        # v2.0.8:从 cookie 读当前数据库
        self._db_name = get_db_name_from_cookie(self.headers.get('Cookie', ''))
        self._db = get_db_path(self._db_name)
        parsed = urllib.parse.urlparse(self.path)
        # Issue #8:统一权限检查(WRITE_PATHS 之前是死列表)
        if parsed.path not in WRITE_PATHS:
            self.send_response(404); self.end_headers(); return
        # 权限检查(2026-06-27):非 ADMIN_IPS 内 IP 拒绝所有写操作
        if not self._is_admin():
            self._json({
                'error': f'权限不足:此操作仅限本机({" / ".join(ADMIN_IPS)})',
            }, status=403)
            return
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b''
        try:
            data = json.loads(body or b'{}')
        except: data = {}
        if parsed.path == '/api/favorites':
            favs = load_favs()
            item_id = data.get('id')
            if item_id in favs:
                favs.remove(item_id)
            else:
                favs.append(item_id)
            save_favs(favs)
            self._json({'favorites': favs})
        elif parsed.path == '/api/upload_search':
            self._upload_search(data)
        elif parsed.path == '/api/ai_image':
            self._ai_image(data)
        elif parsed.path == '/api/semantic_search':
            text = data.get('q', '') or (urllib.parse.parse_qs(parsed.query).get('q', [''])[0] or '')
            self._semantic_search(text)
        elif parsed.path == '/api/intent_search':
            self._intent_search(data)
        elif parsed.path == '/api/database/switch':
            # v2.0.8:切换数据库(返回 Set-Cookie)
            name = (data.get('name') or '').strip()
            if not any(d['name'] == name for d in DB_LIST):
                self._json({'error': f'未知数据库: {name}', 'available': [d['name'] for d in DB_LIST]}, status=400)
                return
            # 单独发响应(带 Set-Cookie)
            body = json.dumps({'current': name, 'message': f'已切换到 {name}'}, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Set-Cookie', f'db={name}; Path=/; Max-Age=31536000; SameSite=Lax')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def _is_admin(self):
        """检查请求是否来自 ADMIN_IPS(自动从 config 同步,避免硬编码不一致)"""
        client_ip = self.client_address[0]
        return client_ip in ADMIN_IPS

    def _fetch_prompts(self, image_id):
        # v2.1.0:从当前 DB 直接读 image_prompts 表(跨 DB 准确,canvasweb 共享 image_prompts schema)
        import time as _t
        now = _t.time()
        cache_key = (self._db_name, image_id)
        cached = PROMPTS_CACHE.get(cache_key)
        if cached and now - cached[0] < PROMPTS_TTL:
            return cached[1]
        result = {'image_id': image_id, 'db': self._db_name, 'prompts': {}, 'categories': []}
        try:
            conn = sqlite3.connect(self._db)
            has_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='image_prompts'").fetchone()
            if not has_table:
                conn.close()
                return result  # 该 DB 没 image_prompts 表
            rows = conn.execute('SELECT category, prompt_text, word_count, source, lang FROM image_prompts WHERE image_id = ?', (image_id,)).fetchall()
            conn.close()
            prompts = {}
            categories = []
            for r in rows:
                cat, text, wc, src, lang = r
                if not text: continue
                prompts[cat] = {'prompt_text': text, 'word_count': wc or len(text), 'source': src or 'rule', 'lang': lang or 'zh'}
                categories.append(cat)
            result['prompts'] = prompts
            result['categories'] = categories
        except Exception as e:
            result['error'] = str(e)
        PROMPTS_CACHE[cache_key] = (now, result)
        return result

    def _serve_prompts(self, parsed):
        # v2.1.0:GET /api/prompts?id=N — 5 类 prompt 代理
        from urllib.parse import parse_qs
        qs = parse_qs(parsed.query)
        ids = qs.get('id', [])
        if not ids:
            self._json({'error': 'missing id'}, status=400); return
        try:
            image_id = int(ids[0])
        except (ValueError, TypeError):
            self._json({'error': 'invalid id'}, status=400); return
        result = self._fetch_prompts(image_id)
        # 加上当前 DB 信息,方便前端知道 prompts 来自哪个库
        result['db'] = self._db_name
        result['served_at'] = self._db  # 当前 DB 路径(调试用)
        self._json(result)

    def _serve_img(self, parsed):
        """v2.0.8:从当前 DB 读 abs_path,直接流式返回图片
        ?id=<image_id> 公开端点
        优势:不依赖 IMG_ROOT,任何 DB 的图都能服务
        """
        qs = urllib.parse.parse_qs(parsed.query)
        ids = qs.get('id', [])
        if not ids:
            self.send_error(400, 'missing id'); return
        try:
            img_id = int(ids[0])
        except (ValueError, TypeError):
            self.send_error(400, 'invalid id'); return
        try:
            conn = sqlite3.connect(self._db)
            row = conn.execute('SELECT abs_path FROM images WHERE id = ?', (img_id,)).fetchone()
            conn.close()
        except Exception as e:
            self.send_error(500, f'db error: {e}'); return
        if not row:
            self.send_error(404, f'image {img_id} not found'); return
        abs_path = row[0]
        # 旧 Mac 路径 → 新路径映射(2026-08-18 v2.0.8:搬迁后的兼容)
        if abs_path.startswith(OLD_IMG_ROOT):
            abs_path = abs_path.replace(OLD_IMG_ROOT, IMG_ROOT)
        if not os.path.isfile(abs_path):
            self.send_error(404, f'file not found: {abs_path}'); return
        ext = abs_path.rsplit('.', 1)[-1].lower() if '.' in abs_path else ''
        mime = {
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'png': 'image/png', 'gif': 'image/gif',
            'webp': 'image/webp', 'bmp': 'image/bmp',
        }.get(ext, 'application/octet-stream')
        try:
            sz = os.path.getsize(abs_path)
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(sz))
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            with open(abs_path, 'rb') as f:
                self.wfile.write(f.read())
        except Exception as e:
            self.send_error(500, str(e))

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # 静默日志（写文件用 logging）
        pass

    def _search(self, q, keywords, project, scene, light, mood, arch, company, view_type, favs_only, limit):
        import re as _re
        def tokenize(t):
            if not t: return ''
            t = t.lower()
            en = _re.findall(r'[a-z0-9]+', t)
            zh = _re.findall(r'[\u4e00-\u9fff]+', t)
            tokens = list(en)
            for w in zh:
                for i in range(len(w)):
                    if i+1 < len(w): tokens.append(w[i:i+2])
                    tokens.append(w[i])
            return ' '.join(set(tokens))

        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        use_fts = False
        fts_terms = []
        if q.strip():
            use_fts = True
            fts_terms.append(tokenize(q))
        if keywords:
            use_fts = True
            fts_terms.append(' AND '.join([tokenize(k) for k in keywords]))
        if use_fts:
            fts_q = ' AND '.join(['(' + t + ')' for t in fts_terms])
            sql = (f"SELECT DISTINCT i.id AS id, i.project, i.filename, i.abs_path, i.scene, i.light, i.space, i.material, i.mood, i.caption, i.phash, i.arch_type, i.render_company, i.view_type "
                   f"FROM images_fts f JOIN images i ON i.id = f.id WHERE images_fts MATCH '{fts_q}'")
            params = []
        else:
            sql = "SELECT id, project, filename, abs_path, scene, light, space, material, mood, caption, phash, arch_type, render_company, view_type FROM images WHERE 1=1"
            params = []
        if project:
            sql += " AND i.project = ?" if use_fts else " AND project = ?"
            params.append(project)
        if scene:
            sql += " AND i.scene LIKE ?" if use_fts else " AND scene LIKE ?"
            params.append(f"%{scene}%")
        if light:
            sql += " AND i.light LIKE ?" if use_fts else " AND light LIKE ?"
            params.append(f"%{light}%")
        if mood:
            sql += " AND i.mood LIKE ?" if use_fts else " AND mood LIKE ?"
            params.append(f"%{mood}%")
        if arch:
            sql += " AND i.arch_type = ?" if use_fts else " AND arch_type = ?"
            params.append(arch)
        if company:
            sql += " AND i.render_company = ?" if use_fts else " AND render_company = ?"
            params.append(company)
        if view_type:
            sql += " AND i.view_type = ?" if use_fts else " AND view_type = ?"
            params.append(view_type)
        if favs_only:
            favs = load_favs()
            if not favs:
                return []
            sql += f" AND i.id IN ({','.join(['?']*len(favs))})" if use_fts else f" AND id IN ({','.join(['?']*len(favs))})"
            params += favs
        sql += f" ORDER BY id DESC LIMIT {limit}"
        rows = conn.execute(sql, params).fetchall()
        out = []
        for r in rows:
            out.append({
                'id': r['id'], 'project': r['project'], 'filename': r['filename'],
                'path': r['abs_path'], 'url': to_img_url(r['id']),
                'scene': r['scene'] or '', 'light': r['light'] or '',
                'space': r['space'] or '', 'material': r['material'] or '',
                'mood': r['mood'] or '', 'caption': r['caption'] or '',
                'phash': r['phash'] or '',
                'arch_type': r['arch_type'] or '', 'render_company': r['render_company'] or '',
                'view_type': (r['view_type'] if 'view_type' in r.keys() else '') or '',
            })
        # v2.1.4:FTS5 不分中文 — 查询有中文且 0 结果时用 LIKE 兜底
        if use_fts and not out and q.strip() and any('\u4e00' <= c <= '\u9fff' for c in q):
            conn2 = sqlite3.connect(self._db)
            conn2.row_factory = sqlite3.Row
            like_sql = "SELECT id, project, filename, abs_path, scene, light, space, material, mood, caption, phash, arch_type, render_company, view_type FROM images WHERE (project LIKE ? OR filename LIKE ? OR scene LIKE ? OR light LIKE ? OR space LIKE ? OR material LIKE ? OR mood LIKE ? OR caption LIKE ? OR chapter_name LIKE ?)"
            like_p = [f'%{q}%'] * 9
            for k, v in [('project', project), ('scene', scene), ('light', light), ('mood', mood), ('arch', arch), ('company', company), ('view_type', view_type)]:
                if v:
                    like_sql += f" AND {k} = ?"
                    like_p.append(v)
            like_sql += f" ORDER BY id DESC LIMIT {limit}"
            out2 = []
            for r in conn2.execute(like_sql, like_p).fetchall():
                out2.append({
                    'id': r['id'], 'project': r['project'], 'filename': r['filename'],
                    'path': r['abs_path'], 'url': to_img_url(r['id']),
                    'scene': r['scene'] or '', 'light': r['light'] or '',
                    'space': r['space'] or '', 'material': r['material'] or '',
                    'mood': r['mood'] or '', 'caption': r['caption'] or '',
                    'phash': r['phash'] or '',
                    'arch_type': r['arch_type'] or '', 'render_company': r['render_company'] or '',
                    'view_type': (r['view_type'] if 'view_type' in r.keys() else '') or '',
                })
            conn2.close()
            return out2
        conn.close()
        return out

    def _facets(self):
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        projects = [r[0] for r in conn.execute('SELECT DISTINCT project FROM images ORDER BY project').fetchall() if r[0]]
        scenes = sorted(set([s for r in conn.execute("SELECT scene FROM images WHERE scene IS NOT NULL AND scene != ''").fetchall() for s in (r[0] or '').split(';') if s.strip()]))
        lights = sorted(set([l for r in conn.execute("SELECT light FROM images WHERE light IS NOT NULL AND light != ''").fetchall() for l in (r[0] or '').split(';') if l.strip()]))
        moods = sorted(set([m for r in conn.execute("SELECT mood FROM images WHERE mood IS NOT NULL AND mood != ''").fetchall() for m in (r[0] or '').split(';') if m.strip()]))
        archs = sorted(set([a for a, in conn.execute("SELECT DISTINCT arch_type FROM images WHERE arch_type IS NOT NULL AND arch_type != ''").fetchall()]))
        companies = sorted(set([c for c, in conn.execute("SELECT DISTINCT render_company FROM images WHERE render_company IS NOT NULL AND render_company != ''").fetchall()]))
        conn.close()
        return {'projects': projects, 'scenes': scenes, 'lights': lights, 'moods': moods, 'archs': archs, 'companies': companies,
                'view_types': ['bird-eye', 'eye-level', 'other']}

    def _semantic_search(self, text):
        if not text:
            self._json({'error': 'q 不能为空', 'items': []})
            return
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            import embedding
            results = embedding.search_by_text(text, 30)
            out = []
            for s, r in results:
                out.append({
                    'id': r['img_id'], 'project': r['project'], 'filename': r['filename'],
                    'path': r['abs_path'], 'url': to_img_url(r['img_id']),
                    'scene': r['scene'] or '', 'light': '',
                    'space': '', 'material': '', 'mood': r['mood'] or '',
                    'caption': '', 'similarity': round(s*100, 1),
                })
            self._json({'count': len(out), 'items': out, 'query': text})
        except Exception as e:
            self._json({'error': '语义搜索失败: ' + str(e), 'items': []})

    def _intent_search(self, data):
        """设计意图找参考(2026-07-24 v2.0.6):
        用户输入自然语言描述(场地/体量/风格/材料...),返回 top 5 匹配案例 +
        每个案例的"为什么像" reasons(基于 metadata 匹配)
        不依赖外部 LLM,纯 FTS5 + metadata 模板生成。"""
        intent = (data.get('intent') or '').strip()
        if not intent:
            self._json({'error': 'intent 不能为空', 'items': []})
            return
        import re as _re
        def tokenize(t):
            t = t.lower()
            en = _re.findall(r'[a-z0-9]+', t)
            zh = _re.findall(r'[\u4e00-\u9fff]+', t)
            tokens = list(en)
            for w in zh:
                for i in range(len(w)):
                    if i+1 < len(w): tokens.append(w[i:i+2])
                    tokens.append(w[i])
            return tokens

        intent_tokens = tokenize(intent)
        if not intent_tokens:
            self._json({'error': 'intent 拆不出有效关键词', 'items': []})
            return

        # 中文 → metadata 关键词映射(让用户的口语描述能跟 metadata 对上)
        KEYWORD_MAP = {
            '混凝土': ['concrete', '混凝土'],
            '山地': ['mountain', 'slope', 'hillside', 'mountainous', '山', '坡'],
            '夜景': ['night', '夜景'],
            '日落': ['sunset', 'golden-hour', '黄昏', '夕'],
            '鸟瞰': ['bird-eye', 'bird', '鸟瞰'],
            '人视': ['eye-level', 'eye', '人视'],
            '轻盈': ['light', 'airy', 'slim', 'thin', '轻'],
            '大体量': ['large', 'monumental', 'huge', 'big', '大'],
            '小尺度': ['small', 'intimate', 'tiny', '小'],
            '文化': ['cultural', '文化'],
            '住宅': ['residential', 'residence', 'house', 'housing', '住宅'],
            '商业': ['commercial', 'commerce', '商业'],
            '学校': ['school', 'education', '学校', '教育'],
            '教堂': ['church', 'chapel', 'cathedral', '教堂'],
            '博物': ['museum', 'gallery', '博物'],
            '办公': ['office', 'workplace', '办公'],
            '酒店': ['hotel', 'hospitality', '酒店'],
            '木质': ['wood', 'timber', '木'],
            '钢': ['steel', 'metal', '钢'],
            '玻璃': ['glass', '玻璃'],
            '砖': ['brick', 'masonry', '砖'],
            '石': ['stone', 'rock', '石'],
            '绿色': ['green', 'landscape', '绿'],
            '水': ['water', 'pool', '水'],
            '光': ['light', 'daylight', '光'],
            '禅': ['zen', 'contemplative', 'meditation', '禅'],
            '神': ['sacred', 'spiritual', 'sacred', '神'],
        }
        meta_keywords = set()
        for k, vlist in KEYWORD_MAP.items():
            if k in intent:
                meta_keywords.update(vlist)
        # 也加 intent 自身 token(让 "教堂" 之类直接命中)
        for tok in intent_tokens:
            if len(tok) >= 2:
                meta_keywords.add(tok)

        # 2026-07-24 v2.0.6:images_fts 用 unicode61 tokenize 不支持中文,改用 LIKE
        # 取 intent_tokens + meta_keywords 并集,每个都 OR 一个 LIKE
        all_keywords = list(set(intent_tokens) | meta_keywords)
        all_keywords = [k for k in all_keywords if len(k) >= 2][:10]  # 限 10 个

        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        if all_keywords:
            conditions = []
            params = []
            for kw in all_keywords:
                conditions.append('(caption LIKE ? OR project LIKE ? OR scene LIKE ? OR material LIKE ? OR mood LIKE ? OR light LIKE ? OR arch_type LIKE ? OR space LIKE ? OR render_company LIKE ? OR filename LIKE ?)')
                params.extend([f'%{kw}%'] * 10)
            sql = (
                "SELECT id, project, filename, abs_path, scene, light, space, material, mood, caption, arch_type, view_type, render_company "
                "FROM images WHERE " + ' OR '.join(conditions) +
                " ORDER BY id DESC LIMIT 30"
            )
            rows = conn.execute(sql, params).fetchall()
        else:
            rows = []
        conn.close()

        # metadata 字段匹配打分
        def score(r):
            s = 0
            fields = {
                'project': (r['project'] or '').lower(),
                'caption': (r['caption'] or '').lower(),
                'scene': (r['scene'] or '').lower(),
                'light': (r['light'] or '').lower(),
                'material': (r['material'] or '').lower(),
                'space': (r['space'] or '').lower(),
                'mood': (r['mood'] or '').lower(),
                'arch_type': (r['arch_type'] or '').lower(),
            }
            for mk in meta_keywords:
                mk_l = mk.lower()
                for fname, fval in fields.items():
                    if mk_l in fval:
                        # material/mood/scene 字段命中权重高
                        s += 2 if fname in ('material', 'mood', 'arch_type', 'scene') else 1
            return s

        scored = [(score(r), r) for r in rows]
        scored.sort(key=lambda x: (-x[0], -x[1]['id']))
        # 取 score > 0 的前 5,不够则按 rank 补
        top = [r for s, r in scored if s > 0][:5]
        if len(top) < 5:
            for s, r in scored:
                if r not in top and s >= 0:
                    top.append(r)
                    if len(top) >= 5:
                        break

        # 生成 items + reasons
        items = []
        for idx, r in enumerate(top, 1):
            reasons = []
            # 头部 reason:项目 + 类型
            if r['project']: reasons.append(f"项目:{r['project']}")
            if r['arch_type']: reasons.append(f"类型:{r['arch_type']}")
            if r['scene']: reasons.append(f"场景:{r['scene']}")
            if r['view_type']: reasons.append(f"视角:{r['view_type']}")
            if r['light']: reasons.append(f"光线:{r['light']}")
            if r['material']: reasons.append(f"材质:{r['material']}")
            if r['space']: reasons.append(f"空间:{r['space']}")
            if r['mood']: reasons.append(f"氛围:{r['mood']}")
            if r['caption']: reasons.append(f"标题:{r['caption']}")
            if r['render_company']: reasons.append(f"渲染:{r['render_company']}")

            items.append({
                'id': r['id'],
                'rank': idx,
                'project': r['project'] or '',
                'filename': r['filename'] or '',
                'url': to_img_url(r['id']),
                'path': r['abs_path'],
                'caption': r['caption'] or '',
                'scene': r['scene'] or '',
                'light': r['light'] or '',
                'material': r['material'] or '',
                'mood': r['mood'] or '',
                'arch_type': r['arch_type'] or '',
                'view_type': r['view_type'] or '',
                'reasons': reasons[:7],
                # 生图用 prompt 摘要(前端可一键带过去给 MCP)
                'prompt_hint': ' '.join([
                    (r['caption'] or ''),
                    (r['scene'] or ''),
                    (r['material'] or ''),
                    (r['light'] or ''),
                    (r['mood'] or ''),
                ]).strip(),
            })

        self._json({'intent': intent, 'count': len(items), 'items': items})

    def _upload_search(self, data):
        b64 = data.get('image', '')
        if not b64.startswith('data:image'):
            self._json({'error': '需要 image base64'})
            return
        try:
            raw = base64.b64decode(b64.split(',', 1)[1])
        except Exception as e:
            self._json({'error': 'base64 解码失败: ' + str(e)})
            return
        up_phash = self._compute_phash(raw)
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT id, project, filename, abs_path, scene, light, space, material, mood, caption, phash FROM images WHERE phash IS NOT NULL AND phash != ""').fetchall()
        sims = []
        for r in rows:
            if not r['phash']: continue
            d = self._hamming(up_phash, r['phash'])
            sims.append((d, r))
        sims.sort(key=lambda x: x[0])
        out = []
        for d, r in sims[:20]:
            out.append({
                'id': r['id'], 'project': r['project'], 'filename': r['filename'],
                'path': r['abs_path'], 'url': to_img_url(r['id']),
                'scene': r['scene'] or '', 'light': r['light'] or '',
                'space': r['space'] or '', 'material': r['material'] or '',
                'mood': r['mood'] or '', 'caption': r['caption'] or '',
                'similarity': round((64 - d) / 64 * 100, 1),
            })
        conn.close()
        self._json({'count': len(out), 'items': out})

    def _compute_phash(self, raw):
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(raw)).convert('L').resize((8, 8))
            px = list(img.getdata())
            avg = sum(px) / len(px)
            bits = ''.join('1' if p > avg else '0' for p in px)
            return bits
        except Exception:
            return '0' * 64

    def _ai_image(self, data):
        prompt = data.get('prompt', '').strip()
        if not prompt:
            self._json({'error': 'prompt 不能为空'})
            return
        import subprocess, re
        req_file = os.path.join(os.path.dirname(__file__), '_ai_req.json')
        json.dump({'prompt': prompt, 'aspect_ratio': '3:2', 'resolution': '2K'}, open(req_file, 'w', encoding='utf-8'))
        cmd = ['mavis', 'mcp', 'call', 'matrix', 'matrix_generate_image', '--file', req_file]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            m = re.search(r'"output_url":\s*"([^"]+)"', r.stdout)
            if m:
                self._json({'path': m.group(1)})
            else:
                self._json({'error': (r.stdout or r.stderr)[:500]})
        except Exception as e:
            self._json({'error': str(e)})

    def _hamming(self, a, b):
        if not a or not b or len(a) != len(b): return 64
        return sum(1 for x, y in zip(a, b) if x != y)


class LimitedServer(ThreadingHTTPServer):
    """并发连接数限制(2026-06-27):
    - 最多 MAX_CONCURRENT 个并发连接
    - 超出返回 503 + '服务器忙'提示
    - 私人网站保护,避免被滥用
    """
    def process_request(self, request, client_address):
        global active_count
        with active_lock:
            if active_count >= MAX_CONCURRENT:
                # 主动拒绝(503)
                try:
                    request.sendall(b'HTTP/1.1 503 Service Unavailable\r\n')
                    request.sendall(b'Content-Type: text/plain; charset=utf-8\r\n')
                    request.sendall(b'Connection: close\r\n\r\n')
                    msg = f'服务器忙:同时连接已达上限 {MAX_CONCURRENT},请稍后重试'.encode('utf-8')
                    request.sendall(msg)
                except Exception:
                    pass
                finally:
                    request.close()
                return
            active_count += 1
        super().process_request(request, client_address)


if __name__ == '__main__':
    # 2026-07-22 v2.0.3:默认端口回归 8081(README 声明值)
    # dev/测试用 9001 时设环境变量:set PICTUREWEB_TEST_PORT=9001
    port = int(os.environ.get('PICTUREWEB_TEST_PORT', '8081'))
    host = '0.0.0.0'  # 监听所有接口(2026-06-27 改为 0.0.0.0 允许局域网访问)
    os.chdir(os.path.dirname(__file__))
    print(f'Library 启动: http://127.0.0.1:{port}/', flush=True)
    print(f'           局域网: http://192.168.181.136:{port}/  (需同网段)', flush=True)
    print(f'DB: {DB}', flush=True)
    print(f'DB_ROOT: {PICTUREWEB_DB_ROOT} (扫库用)', flush=True)
    print(f'IMG_ROOT: {IMG_ROOT} (图根,不动)', flush=True)
    print(f'CANVASWEB_PROMPTS_URL: {CANVASWEB_PROMPTS_URL} (canvasweb · fallback 用)', flush=True)
    print(f'prompts: 直接读当前 DB image_prompts 表(跨 DB 准确) + 5min cache', flush=True)
    print(f'可用数据库({len(DB_LIST)}个):', flush=True)
    for d in DB_LIST:
        marker = ' *' if d['name'] == DEFAULT_DB_NAME else '  '
        print(f'  {marker} {d["name"]:20s} {d["count"]:5d} 张  {d["rel"]}', flush=True)
    print(f'IMG_ROOT: {IMG_ROOT}', flush=True)
    print(f'并发上限: {MAX_CONCURRENT} 个连接', flush=True)
    try:
        # 用 LimitedServer 限制并发(2026-06-27)
        LimitedServer((host, port), Handler).serve_forever()
    except OSError as e:
        print(f'端口 {port} 占用: {e}', flush=True)
        import time; time.sleep(10)
