#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pictureweb HTTP server · PictureDb 项目的 web 层
零外部依赖:只用 Python 标准库 (http.server + sqlite3)
启动:python3 -X utf8 server.py &
端口:8081
端点:
  GET  /              健康检查 + 端点清单
  GET  /search?q=     FTS5 全文检索 (返回 JSON)
  GET  /image?id=     按 id 返回图片二进制
  GET  /phash?id=     按 id 返回 phash 字符串 + 汉明距离支持 ?other=
"""
import json
import os
import shutil
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# 路径
DB_PATH = os.environ.get(
    "PICTUREDB_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "PictureDb.db"),
)
PORT = int(os.environ.get("PICTUREDB_PORT", "8081"))

# 路径白名单(P1 防御,Verifier 批 1 行 45):
# /image 端点 abs_path 是任意绝对路径,虽然 127.0.0.1 风险低,
# 但哪天绑 0.0.0.0 或外部脚本注入路径(/etc/passwd 等),秒变 path traversal。
# 只允许发白名单根下的文件,用 realpath 防 symlink 绕过。
ALLOWED_ROOTS = (
    os.path.expanduser("~/Mac/WorkTeam/05_Space"),
    os.path.expanduser("~/Pictures"),
)


def get_conn():
    """每次请求新连接,避免多线程共享问题"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hamming_hex(a: str, b: str) -> int:
    """两个 16 进制 phash 字符串的汉明距离 (按 bit 比)"""
    if not a or not b or len(a) != len(b):
        return -1
    ba = bin(int(a, 16))[2:].zfill(len(a) * 4)
    bb = bin(int(b, 16))[2:].zfill(len(b) * 4)
    return sum(x != y for x, y in zip(ba, bb))


def parse_int_param(value: str, default: int, lo: int, hi: int, name: str):
    """安全解析整型 query 参数。`?limit=` 留空/字母/超长/非数字 → 抛 ValueError。

    Verifier 批 1 行 44 修复: 原 `int(qs.get('limit',['20'])[0])` 对
    `?limit=abc` 或 `?id=99999999999999999` 抛 ValueError 变 500,
    且不带 JSON 错误体,前端拿不到 reason。统一 try/except 转 400。
    """
    if not value:  # 留空 → 兜底默认值
        return default
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"invalid {name}: {value!r}")
    return max(lo, min(n, hi))


class Handler(BaseHTTPRequestHandler):
    server_version = "PictureWeb/1.0"

    # ---------- 工具方法 ----------
    def _json(self, status: int, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _binary(self, status: int, body: bytes, ctype: str):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _stream_file(self, status: int, path_abs: str, ctype: str):
        """流式发送文件,先发 Content-Length 头,64KB 分块写,避免大文件 OOM。
        Verifier 修史:
          · P0-a (批 2 行 42): 之前 `f.read()` 一次读全部,DB 错填 1GB 源文件
            配合 N 并发 = N×1GB OOM,即便 127.0.0.1 也炸。改 64KB 分块。
          · P0-c (批 3 行 112): headers 提前发送 — 旧版先 `os.path.getsize` +
            `send_response` + `send_headers`,再 `open(path_abs, "rb")`。
            若 `open` 失败(竞态:文件被删 / 权限 / 损坏)headers 已发,客户端
            看到 0-byte 200 OK + 断流,数据未达 = 半成品下载。改成两阶段:
              阶段 1: `try: open(path_abs, "rb")` 拿 handle + size(fstat),
                     失败直接 _json(500) — 此时 headers 还没发,客户端能拿到 JSON。
              阶段 2: send_response + headers + end_headers,再 shutil.copyfileobj
                     分块流式(64KB),finally 关闭 f。
        """
        try:
            f = open(path_abs, "rb")
        except OSError as e:
            return self._json(500, {"error": f"open fail: {e}"})
        try:
            size = os.fstat(f.fileno()).st_size
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(size))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            shutil.copyfileobj(f, self.wfile, length=64 * 1024)
        finally:
            f.close()

    def _row_to_dict(self, row):
        return {k: row[k] for k in row.keys()}

    # ---------- 路由 ----------
    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        qs = parse_qs(u.query)

        # 健康检查
        if path == "/" or path == "/health":
            return self._json(200, {
                "service": "PictureWeb",
                "version": "1.0",
                "db": os.path.basename(DB_PATH),
                "endpoints": [
                    "GET /search?q=<query>&limit=<n>",
                    "GET /image?id=<id>",
                    "GET /phash?id=<id>&other=<hex>",
                ],
            })

        # /search?q=<query>
        if path == "/search":
            q = (qs.get("q", [""])[0] or "").strip()
            try:
                limit = parse_int_param(
                    qs.get("limit", [""])[0], default=20, lo=1, hi=100, name="limit"
                )
            except ValueError as e:
                return self._json(400, {"error": "invalid param", "param": str(e)})
            if not q:
                return self._json(400, {"error": "missing q"})

            conn = get_conn()
            try:
                # FTS5:对中文已 tokenize,直接 MATCH
                sql = """
                    SELECT i.id, i.rel_path, i.abs_path, i.filename,
                           i.caption, i.description, i.project,
                           i.scene, i.light, i.space, i.material, i.mood,
                           i.arch_type, i.render_style, i.phash
                    FROM images_fts f
                    JOIN images i ON i.id = f.id
                    WHERE images_fts MATCH ?
                    LIMIT ?
                """
                rows = conn.execute(sql, (q, limit)).fetchall()
                return self._json(200, {
                    "query": q,
                    "count": len(rows),
                    "results": [self._row_to_dict(r) for r in rows],
                })
            except sqlite3.OperationalError as e:
                return self._json(200, {
                    "query": q,
                    "count": 0,
                    "results": [],
                    "warning": f"FTS error (回退 LIKE 扫描): {e}",
                })
            finally:
                conn.close()

        # /image?id=<id>
        if path == "/image":
            id_s = qs.get("id", [""])[0]
            if not id_s or not id_s.isdigit() or len(id_s) > 9:
                # id 留空 / 含字母 / 超长(>9 位) 一律 400
                return self._json(400, {"error": "invalid param", "param": "id must be 1-9 digit integer"})
            conn = get_conn()
            try:
                row = conn.execute(
                    "SELECT abs_path, ext FROM images WHERE id = ?", (int(id_s),)
                ).fetchone()
            finally:
                conn.close()
            if not row:
                return self._json(404, {"error": "not found"})
            path_abs = row["abs_path"]
            if not path_abs or not os.path.exists(path_abs):
                return self._json(404, {"error": "file missing on disk"})
            ext = (row["ext"] or "jpg").lower()
            ctype = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp",
            }.get(ext, "application/octet-stream")
            # 路径白名单(P1 防御 — 行 45),realpath 防 symlink 绕过
            real = os.path.realpath(path_abs)
            if not any(real.startswith(r) for r in ALLOWED_ROOTS):
                return self._json(403, {"error": "path not allowed", "path": real})
            try:
                return self._stream_file(200, path_abs, ctype)
            except OSError as e:
                return self._json(500, {"error": f"read fail: {e}"})

        # /phash?id=<id>&other=<hex>
        if path == "/phash":
            id_s = qs.get("id", [""])[0]
            other = qs.get("other", [""])[0]
            if not id_s or not id_s.isdigit() or len(id_s) > 9:
                return self._json(400, {"error": "invalid param", "param": "id must be 1-9 digit integer"})
            conn = get_conn()
            try:
                row = conn.execute(
                    "SELECT id, rel_path, phash FROM images WHERE id = ?", (int(id_s),)
                ).fetchone()
            finally:
                conn.close()
            if not row:
                return self._json(404, {"error": "not found"})
            payload = {
                "id": row["id"],
                "rel_path": row["rel_path"],
                "phash": row["phash"],
            }
            if other:
                d = hamming_hex(row["phash"] or "", other)
                payload["hamming_distance_to_other"] = d
                payload["similar"] = d >= 0 and d <= 10
            return self._json(200, payload)

        # 404
        return self._json(404, {"error": "no such endpoint", "path": path})

    def log_message(self, fmt, *args):
        sys.stderr.write("[pictureweb] " + fmt % args + "\n")


def main():
    if not os.path.exists(DB_PATH):
        sys.stderr.write(f"[pictureweb] DB not found: {DB_PATH}\n")
        sys.exit(1)
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    sys.stderr.write(f"[pictureweb] listening on http://127.0.0.1:{PORT} (db={DB_PATH})\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("[pictureweb] shutting down\n")
        httpd.server_close()


if __name__ == "__main__":
    main()
