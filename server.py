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
from typing import Optional
from urllib.parse import urlparse, parse_qs

# 路径
DB_PATH = os.environ.get(
    "PICTUREDB_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "PictureDb.db"),
)
PORT = int(os.environ.get("PICTUREDB_PORT", "8081"))

# 路径白名单(P0 收紧,Verifier 批 4 行 237):
# 批 1/批 2 用 `~/Mac/WorkTeam/05_Space`(整 05_Space)和 `~/Pictures`
# 太宽 — 前者把 _ArchitectLib 全开放(任何 .py/.md/.db 都能拉),
# 后者用户相册也漏出。批 4 改为精确白名单,只允许 images.abs_path
# 实际存在的子目录:DB 实测 390 张全在 03_Architect/Mobile/(01-Master/
# 03-Residence/04-Block/07-Rending 四个子目录)。要扩白名单就加环境
# 变量 PICTUREDB_ALLOWED_ROOTS(冒号分隔,Linux/Mac 风格),不要改代码。
_DEFAULT_ALLOWED = (
    "~/Mac/WorkTeam/05_Space/03_Architect/Mobile",
)
ALLOWED_ROOTS = tuple(
    os.path.realpath(os.path.expanduser(p))
    for p in (
        os.environ.get("PICTUREDB_ALLOWED_ROOTS")
        or ":".join(_DEFAULT_ALLOWED)
    ).split(":")
    if p.strip()
)

# 扩展名白名单(P0 防御,Verifier 批 5 行 237 / 2026-08-11):
# 之前 ctype fallback 是 application/octet-stream,意味着库内 abs_path
# 哪怕填了 .ssh/id_rsa 也能 200 流式出去(白名单只管目录,不管后缀)。
# 现在 /image 端点先看后缀是否在白名单,不在直接 403,补上 ctype 兜底
# 漏洞。库 schema 不限扩展名(images.ext 是 TEXT),所以兜底不能省。
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}

# DB 最小尺寸(P0 防御,Verifier 批 5 行 238 / 2026-08-11):
# 4096 字节是 images 表(单行 ~150B 元数据)+ images_fts 元数据 +
# sqlite_master 页头 + headers 的最小尺寸;低于这个值基本是空库
# / .DS_Store / 备份覆盖错版本,启动会留隐患 — 巡检时看不到但
# /search 上来就 503。main() 启动前先校验。
_DB_MIN_SIZE = 4096


def is_under(path: str, roots) -> bool:
    """判断 path 是否在 roots 任意一根目录下。用 os.path.commonpath 防
    startswith 前缀撞车(P1-c 批 2 行 114):"~/Pictures-evil/secret.jpg"
    startswith("~/Pictures") 会放行,但 commonpath 算到 "~/Pictures"
    和 "~/Pictures-evil" 的最近公共祖先是 "/Users/aaron",不等于任一根,
    故不放行。realpath 后两侧都消解 symlink,避免软链方向不一致。

    注意:不能用 `os.path.commonpath([path] + list(roots))` 多根 LCA
    形式 — 多根时它返回所有 path+roots 的最近公共祖先(可能浅到 /),
    而我们要的是"path 是否是任一根的子目录"。所以逐根比。

    防御:内部对 path 再做一次 realpath,防 commonpath 不解析 `..`
    留下隐患;空路径直接 False。
    """
    if not path:
        return False
    real = os.path.realpath(path)
    for r in roots:
        try:
            if os.path.commonpath([real, r]) == r:
                return True
        except ValueError:
            # 不同盘符(Windows)或空路径,commonpath 抛 ValueError → 跳过此根
            continue
    return False


def get_conn():
    """每次请求新连接,避免多线程共享问题"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def validate_hex(s, expected_len: int = 16) -> Optional[int]:
    """校验 hex 字符串格式,返 expected_len 表示"合法 N hex (N*4 bit)"。

    判错条件:非 str / 空 / 长度不等于 expected_len / 含非 hex 字符。
    返回值:None = 错(给 /phash 端点用),int = 实际有效 bit 数(成功)。

    P2 (Verifier 批 5 行 241 / 2026-08-11):拆出来便于 row/origin 分别校验,
    把"row 库内 phash 格式错"和"other 用户传格式错"区分开,前端能定位
    到底是 DB 污染还是用户输错。
    """
    if not s or not isinstance(s, str):
        return None
    if len(s) != expected_len:
        return None
    try:
        int(s, 16)
    except ValueError:
        return None
    return expected_len * 4


def hamming_hex(a: str, b: str, expected_len: int = 16) -> Optional[int]:
    """两个 16 进制 phash 字符串的汉明距离 (按 bit 比)。

    返回:
      - int   : 有效汉明距离 (0~expected_len*4),表示"两张图不同 bit 数"
      - None  : 输入格式错 (空 / 长度不匹配 / 非 hex),与"不相似"明确区分

    修史:
    · P0 (Verifier 批 4 行 182,2026-08-10):旧版把'格式错'和'不相似'都塞 -1,
      `int('ZZZZ', 16)` 又抛 ValueError 触发 BaseHTTPRequestHandler 默认
      traceback → 客户端 500 空 body。改返 None 让 /phash 入口自行区分。
    · P2 (Verifier 批 5 行 241 / 2026-08-11):用 validate_hex 拆出格式校验,
      row/origin 各自失败能归因到具体一方(调用方在 /phash 端点比对,
      返 row_format_error / other_format_error 字段,前端分类提示)。
    """
    if validate_hex(a, expected_len) is None or validate_hex(b, expected_len) is None:
        return None
    ba = bin(int(a, 16))[2:].zfill(expected_len * 4)
    bb = bin(int(b, 16))[2:].zfill(expected_len * 4)
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
    def _check_fts_health(self, conn) -> tuple[bool, str]:
        """P1-d (Verifier 批 2 行 115) + P1 合并 (Verifier 批 4 行 184):
        探测 images_fts 是否存在 + 可用。

        早期版每次 /search 开两个 sqlite3 连接:_check_fts_health 自己
        get_conn()+conn.close() 跑 sqlite_master 探测,line 221 又开新
        conn 跑 MATCH。本版改为接受调用方传入的 conn:同一个连接既
        探测又查询,省一次 round-trip,避免"探测 ok 但查询时表被并发
        DROP 状态不一致"。

        探测失败直接 (False, detail),由 /search 入口转 503,
        不进 try/except 静默降级。except 链覆盖 OperationalError +
        DatabaseError + 兜底 sqlite3.Error(InterfaceError 之类)。
        """
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE name = 'images_fts'"
            ).fetchone()
        except sqlite3.OperationalError as e:
            return False, f"images_fts probe failed: {e}"
        except sqlite3.DatabaseError as e:
            return False, f"db error: {e}"
        except sqlite3.Error as e:
            # 兜底非预期家族(InterfaceError 等) — Verifier 批 4 行 184
            return False, f"sqlite error: {e}"
        if not row:
            return False, "images_fts table missing"
        return True, "ok"

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

    def _stream_file(self, status: int, path_abs: str, ctype: str, expected_real: str = None, expected_inode: int = None):
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
          · P1 (批 5 行 240 / 2026-08-11) TOCTOU 二次校验:realpath → is_under →
            exists → _stream_file 之间 4 步无锁,migrate_p1p2.py 跑批替换 symlink
            / 网络盘文件被并发换掉时,白名单可能放过指向 ALLOWED_ROOTS 外的
            新文件。open 之后再 realpath + fstat 比对 inode,任一不等 → 403。
        """
        try:
            f = open(path_abs, "rb")
        except OSError as e:
            return self._json(500, {"error": f"open fail: {e}"})
        try:
            # P1 TOCTOU 二次校验(open 之后,headers 之前,失败时 headers 还没发)
            if expected_real is not None:
                current_real = os.path.realpath(path_abs)
                if current_real != expected_real:
                    return self._json(403, {
                        "error": "path drifted, possible TOCTOU",
                        "real": current_real,
                    })
            inode_now = os.fstat(f.fileno()).st_ino
            if expected_inode is not None and inode_now != expected_inode:
                return self._json(403, {
                    "error": "file replaced, possible TOCTOU",
                    "inode": inode_now,
                })
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

            # P1-d (Verifier 批 2 行 115) + P1 合并 (Verifier 批 4 行 184):
            # 一个 conn 既做健康探测又跑 MATCH,省一次 round-trip,避免
            # 探测 ok 但查询时表被并发 DROP 状态不一致。健康失败转 503,
            # 不静默降级(旧版返 200+warning 让前端以为成功,FTS 真正
            # 失败信号被埋)。
            conn = get_conn()
            try:
                healthy, detail = self._check_fts_health(conn)
                if not healthy:
                    sys.stderr.write(f"[FTS-FAIL] {detail}\n")
                    sys.stderr.flush()
                    return self._json(503, {
                        "error": "service unavailable",
                        "service": "fts5",
                        "detail": detail,
                        "recoverable": True,
                    })

                # P0 (Verifier 批 6 行 312 / 2026-08-12 23:15):
                # query 含 FTS5 操作符(`*"()\:NEAR/AND/OR/NOT` 等)
                # 会触发 sqlite3.OperationalError("fts5: syntax error" 等),
                # 旧版把所有 OperationalError 返 503,语义错位(用户输入错 → 400,
                # 不是服务端故障)。预检命中 FTS5 语法关键字时返 400 + 提示,
                # 其他 OperationalError 仍走 503 兜底。
                try:
                    conn.execute(
                        "SELECT id FROM images_fts WHERE images_fts MATCH ? LIMIT 1",
                        (q,),
                    ).fetchone()
                except sqlite3.OperationalError as e:
                    msg = str(e).lower()
                    fts_syntax_markers = (
                        "fts5: syntax error",
                        "fts5: near",
                        "fts5: parse error",
                        "fts5: unmatched",
                    )
                    if any(mk in msg for mk in fts_syntax_markers):
                        sys.stderr.write(
                            f"[FTS-SYNTAX-ERR] q={q!r} msg={e}\n"
                        )
                        sys.stderr.flush()
                        return self._json(400, {
                            "error": "invalid query syntax",
                            "param": "q",
                            "detail": str(e),
                            "hint": (
                                "FTS5 操作符(* \" ( ) : NEAR AND OR NOT)"
                                "需双引号包或转义"
                            ),
                        })
                    # 非语法错的 OperationalError 留给外层 except 兜 503

                # FTS5:trigram tokenize 支持中文子串匹配(P1 批 4 行 185)
                # ORDER BY bm25(images_fts) 按相关度升序(负数越小越相关)
                sql = """
                    SELECT i.id, i.rel_path, i.abs_path, i.filename,
                           i.caption, i.description, i.project,
                           i.scene, i.light, i.space, i.material, i.mood,
                           i.arch_type, i.render_style, i.phash
                    FROM images_fts f
                    JOIN images i ON i.id = f.id
                    WHERE images_fts MATCH ?
                    ORDER BY bm25(images_fts)
                    LIMIT ?
                """
                rows = conn.execute(sql, (q, limit)).fetchall()
                return self._json(200, {
                    "query": q,
                    "count": len(rows),
                    "results": [self._row_to_dict(r) for r in rows],
                })
            except sqlite3.OperationalError as e:
                # 真正失败(索引表被外部脚本 DROP、tokenize 参数版本不兼容、
                # 表锁)时不再伪装 200,改 503 + errors 数组,前端 5xx retry。
                sys.stderr.write(f"[FTS-FAIL] query OperationalError: {e}\n")
                sys.stderr.flush()
                return self._json(503, {
                    "error": "service unavailable",
                    "service": "fts5",
                    "detail": str(e),
                    "recoverable": True,
                })
            except sqlite3.DatabaseError as e:
                # 兜底 DatabaseError 家族(IntegrityError 等)
                sys.stderr.write(f"[FTS-FAIL] query DatabaseError: {e}\n")
                sys.stderr.flush()
                return self._json(503, {
                    "error": "service unavailable",
                    "service": "fts5",
                    "detail": str(e),
                    "recoverable": True,
                })
            except sqlite3.Error as e:
                # 兜底非预期家族(InterfaceError 等) — Verifier 批 4 行 184
                sys.stderr.write(f"[FTS-FAIL] query sqlite3.Error: {e}\n")
                sys.stderr.flush()
                return self._json(503, {
                    "error": "service unavailable",
                    "service": "fts5",
                    "detail": str(e),
                    "recoverable": True,
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
            # P0-d (Verifier 批 2 行 113):白名单检查前移到文件存在性之前。
            # 旧版先 184-185 exists → 404,再 192-194 白名单 → 403,信息熵可还原
            # DB 内容(404 = 不在 DB 或文件没了,403 = 在 DB 但越界)。现在统一
            # 403 path not allowed,只有白名单通过的路径才报 404 file missing。
            real = os.path.realpath(path_abs) if path_abs else ""
            if not real or not is_under(real, ALLOWED_ROOTS):
                return self._json(403, {"error": "path not allowed", "path": real})
            # P0 (Verifier 批 5 行 237 / 2026-08-11) 扩展名白名单:
            # 库 schema 不限 images.ext(可能是 .ssh/id_rsa 等敏感后缀),
            # ctype fallback 是 application/octet-stream 兜底 → 200 流式发
            # 任意文件 = path traversal 0day。放 exists 之前 — 不泄露"非图
            # 文件是否存在",且即便 file 缺失,也立刻 403 而非 404 让攻击者
            # 区分 "DB 引用了非法后缀" vs "DB 引用了合法后缀但文件没了"。
            from pathlib import Path
            ext_suffix = Path(path_abs).suffix.lower()
            if ext_suffix not in ALLOWED_EXTS:
                return self._json(403, {
                    "error": "extension not allowed",
                    "ext": ext_suffix,
                    "allowed": sorted(ALLOWED_EXTS),
                })
            # 白名单通过后才检查文件实际存在性 + 二次 mtime 校验(P0-c 增强)
            if not os.path.exists(path_abs):
                return self._json(404, {"error": "file missing on disk"})
            ext = (row["ext"] or "jpg").lower()
            ctype = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp",
            }.get(ext, "application/octet-stream")
            # P1 (Verifier 批 5 行 240) TOCTOU 防御:把 realpath 算好的
            # expected_real 传给 _stream_file,内部 open 后再 realpath 比对,
            # 同时记 inode,二次 fstat 比 inode,任一不等 → 403。
            try:
                expected_inode = os.stat(path_abs).st_ino
            except OSError:
                expected_inode = None
            try:
                return self._stream_file(200, path_abs, ctype,
                                         expected_real=real,
                                         expected_inode=expected_inode)
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
                # P2 (Verifier 批 5 行 241 / 2026-08-11) row/other 归因:
                # 用 validate_hex 分别校验 row.phash 和 other,各自失败
                # 给前端不同信号 — row_format_error 提示 DB 污染(运维修),
                # other_format_error 提示用户重传。前端从一锅 None 改成分类。
                row_phash = row["phash"] or ""
                row_bits = validate_hex(row_phash, 16)
                other_bits = validate_hex(other, 16)
                if row_bits is None:
                    payload["row_format_error"] = True
                if other_bits is None:
                    payload["other_format_error"] = True
                d = hamming_hex(row_phash, other)
                # P0 (Verifier 批 4 行 182,2026-08-10):hamming_hex 改返 None
                # 区分'格式错'与'不相似'。前端逻辑:
                #   - d is None  → other_format_error=True,弹 "phash 格式错,请重传"
                #   - d <= 10    → similar=True,展示为相似
                #   - d > 10     → similar=False,展示为不相似
                payload["hamming_distance_to_other"] = d
                payload["similar"] = d is not None and d <= 10
            return self._json(200, payload)

        # 404
        return self._json(404, {"error": "no such endpoint", "path": path})

    def log_message(self, fmt, *args):
        # P2-c (Verifier 批 2 行 116):显式 flush,避免长跑崩溃时 stderr buffer
        # 丢尾部(02-巡检 P2.5 提过未修)。
        msg = "[pictureweb] " + (fmt % args) + "\n"
        sys.stderr.write(msg)
        sys.stderr.flush()


class _ThreadingServer(ThreadingHTTPServer):
    """P2-c (Verifier 批 2 行 116):daemon_threads=True 让工作线程随主进程
    退出,SIGTERM/KeyboardInterrupt 不会被 in-flight 请求拖到 60s+。
    Python 3.7+ 支持此属性,长史 cron 启停 pictureweb 立即生效。"""
    daemon_threads = True


def main():
    # P0 (Verifier 批 5 行 238 / 2026-08-11) 启动前双重校验:
    # 1) size 校验 — < 4096 字节基本是空库 / .DS_Store / 备份覆盖错版本,
    #    images + images_fts 元数据都凑不齐。直接 sys.exit(1) 比跑起来
    #    等 /search 503 强,巡检 / 长史脚本能立刻看到错。
    # 2) PRAGMA quick_check — 即使 size 够,库也可能被外部脚本写坏,
    #    quick_check 返 'ok' 才算完整。返错可能是 page corruption /
    #    journal 问题,直接拒绝启动(避免 FTS5 防御基于坏库失效)。
    if not os.path.exists(DB_PATH):
        sys.stderr.write(f"[pictureweb] DB not found: {DB_PATH}\n")
        sys.stderr.flush()
        sys.exit(1)
    db_size = os.path.getsize(DB_PATH)
    if db_size < _DB_MIN_SIZE:
        sys.stderr.write(
            f"[pictureweb] DB too small or missing: {DB_PATH} (size={db_size}, min={_DB_MIN_SIZE})\n"
        )
        sys.stderr.flush()
        sys.exit(1)
    try:
        _check_conn = sqlite3.connect(DB_PATH)
        _check_row = _check_conn.execute("PRAGMA quick_check").fetchone()
        _check_conn.close()
    except sqlite3.Error as e:
        sys.stderr.write(f"[pictureweb] DB open/check failed: {e}\n")
        sys.stderr.flush()
        sys.exit(1)
    if not _check_row or _check_row[0] != "ok":
        sys.stderr.write(
            f"[pictureweb] DB integrity check failed: {_check_row[0] if _check_row else 'no result'}\n"
        )
        sys.stderr.flush()
        sys.exit(1)
    httpd = _ThreadingServer(("127.0.0.1", PORT), Handler)
    sys.stderr.write(
        f"[pictureweb] listening on http://127.0.0.1:{PORT} "
        f"(db={DB_PATH}, size={db_size}, quick_check=ok)\n"
    )
    sys.stderr.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("[pictureweb] shutting down\n")
        sys.stderr.flush()
        # 显式 shutdown 等 worker 完成,超时 5s 后 server_close
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
