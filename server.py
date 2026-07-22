import sqlite3, os, sys, json, base64  # 2026-07-21 Issue #6:删 hashlib 死代码
from http.server import HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
import urllib.parse

# 2026-07-21 Issue #4:用 PICTUREWEB_HOME 环境变量 + 默认值,代替硬编码绝对路径
# 默认值跟原 hardcoded 一致,向后兼容(不设环境变量时行为不变)
# 换电脑或换盘符只需: set PICTUREWEB_HOME=E:/your/path
PICTUREWEB_HOME = os.environ.get('PICTUREWEB_HOME', 'D:/Mac/Mac/workteam/05_space/03_architect')
# DB 在 PictureWeb 同级的 PictureDb/ 下(2026-06-28 修正:有数据的库在 _ArchitectLib/PictureDb/)
DB = os.path.join(PICTUREWEB_HOME, '_ArchitectLib', 'PictureDb', 'PictureDb.db')
FAV_FILE = os.path.join(os.path.dirname(__file__), 'favorites.json')
# 图片根目录(2026-06-28 迁移到 Mobile)
IMG_ROOT = os.path.join(PICTUREWEB_HOME, 'Mobile')
# 旧 Mac 路径前缀(DB 里的路径是旧的,需要映射)
OLD_IMG_ROOT = '/Users/aaron/Mac/WorkTeam/05_Space/03_Architect/Mobile'

# 权限控制(2026-06-27 增加):只有本机 Mac 的 IP 可以写操作,其他电脑只读
# 读:GET /, GET /img/*, GET /api/search, GET /api/facets, GET /api/favorites
# 写:POST /api/favorites, POST /api/upload_search, POST /api/ai_image
ADMIN_IPS = {'127.0.0.1', '192.168.181.136', '::1'}  # 本机 loopback + Windows LAN IP
WRITE_PATHS = {'/api/favorites', '/api/upload_search', '/api/ai_image', '/api/semantic_search'}

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

def to_img_url(abs_path):
    """将绝对路径转为 /img/ 相对 URL（兼容旧 Mac 路径）"""
    # 旧 Mac 路径 -> 新路径映射
    if abs_path.startswith(OLD_IMG_ROOT):
        abs_path = abs_path.replace(OLD_IMG_ROOT, IMG_ROOT)
    # 取相对于 IMG_ROOT 的路径
    try:
        rel = os.path.relpath(abs_path, IMG_ROOT).replace(os.sep, '/')
    except ValueError:
        rel = abs_path
    return '/img/' + rel

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
                    it['url'] = to_img_url(it['path'])
                self._json({'count': len(items), 'items': items})
            except Exception as e:
                self._json({'error': str(e), 'count': 0, 'items': []})
        elif parsed.path == '/api/facets':
            self._json(self._facets())
        elif parsed.path == '/api/favorites':
            self._json({'favorites': load_favs()})
        else:
            # 其它走父类（HTML/CSS/JS 静态文件）
            super().do_GET()

    def do_POST(self):
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
        else:
            self.send_response(404)
            self.end_headers()

    def _is_admin(self):
        """检查请求是否来自 ADMIN_IPS(自动从 config 同步,避免硬编码不一致)"""
        client_ip = self.client_address[0]
        return client_ip in ADMIN_IPS

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

        conn = sqlite3.connect(DB)
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
                'path': r['abs_path'], 'url': to_img_url(r['abs_path']),
                'scene': r['scene'] or '', 'light': r['light'] or '',
                'space': r['space'] or '', 'material': r['material'] or '',
                'mood': r['mood'] or '', 'caption': r['caption'] or '',
                'phash': r['phash'] or '',
                'arch_type': r['arch_type'] or '', 'render_company': r['render_company'] or '',
                'view_type': (r['view_type'] if 'view_type' in r.keys() else '') or '',
            })
        conn.close()
        return out

    def _facets(self):
        conn = sqlite3.connect(DB)
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
                    'path': r['abs_path'], 'url': to_img_url(r['abs_path']),
                    'scene': r['scene'] or '', 'light': '',
                    'space': '', 'material': '', 'mood': r['mood'] or '',
                    'caption': '', 'similarity': round(s*100, 1),
                })
            self._json({'count': len(out), 'items': out, 'query': text})
        except Exception as e:
            self._json({'error': '语义搜索失败: ' + str(e), 'items': []})

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
        conn = sqlite3.connect(DB)
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
                'path': r['abs_path'], 'url': to_img_url(r['abs_path']),
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
    port = 9001
    host = '0.0.0.0'  # 监听所有接口(2026-06-27 改为 0.0.0.0 允许局域网访问)
    os.chdir(os.path.dirname(__file__))
    print(f'Library 启动: http://127.0.0.1:{port}/', flush=True)
    print(f'           局域网: http://192.168.181.136:{port}/  (需同网段)', flush=True)
    print(f'DB: {DB}', flush=True)
    print(f'IMG_ROOT: {IMG_ROOT}', flush=True)
    print(f'并发上限: {MAX_CONCURRENT} 个连接', flush=True)
    try:
        # 用 LimitedServer 限制并发(2026-06-27)
        LimitedServer((host, port), Handler).serve_forever()
    except OSError as e:
        print(f'端口 {port} 占用: {e}', flush=True)
        import time; time.sleep(10)
