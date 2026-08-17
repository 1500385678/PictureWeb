"""server/auth.py · 认证 + token + 画布锁 (2026-07-24 加)
PBKDF2-SHA256 密码 hash(无三方依赖)·自签 token(secret + uid + exp + nonce)·
DB 持久化 sessions · 30 分钟画布锁
"""
from __future__ import annotations  # PEP 563 · 让所有 annotation 变 str,Python 3.9 也能用 PEP 604 `dict | None` 语法 (R2026-08-16 P0)

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime

from .config import CANVAS_DB

# ===== 路径 =====
_AUTH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.auth')
os.makedirs(_AUTH_DIR, exist_ok=True)
_SECRET_FILE = os.path.join(_AUTH_DIR, 'secret.key')

# ===== 启动时生成 server 端 secret(用来签 token)=====
def _get_or_create_secret():
    if os.path.isfile(_SECRET_FILE):
        with open(_SECRET_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    secret = secrets.token_urlsafe(48)
    with open(_SECRET_FILE, 'w', encoding='utf-8') as f:
        f.write(secret)
    return secret

_SERVER_SECRET = _get_or_create_secret()

# ===== 配置 =====
_PBKDF2_ITERS = 100_000
_TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 天有效
_LOCK_TTL_SECONDS = 30 * 60         # 画布锁 30 分钟(可续)

# ===== 密码 hash(PBKDF2)=====
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    hkdf = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, _PBKDF2_ITERS)
    return f'pbkdf2_sha256${_PBKDF2_ITERS}${salt.hex()}${hkdf.hex()}'

def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hkdf_hex = stored.split('$')
        if algo != 'pbkdf2_sha256':
            return False
        salt = bytes.fromhex(salt_hex)
        hkdf = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iters))
        return hmac.compare_digest(hkdf.hex(), hkdf_hex)
    except Exception:
        return False

# ===== token 签发 + 校验 =====
def _sign_token(user_id: int, expires_at: int) -> str:
    """签发 token:格式 base64(json_payload).hex(hmac)"""
    payload = {'uid': user_id, 'exp': expires_at, 'n': secrets.token_hex(4)}
    payload_b = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    import base64
    payload_b64 = base64.urlsafe_b64encode(payload_b).rstrip(b'=')
    sig = hmac.new(_SERVER_SECRET.encode('utf-8'), payload_b64, hashlib.sha256).hexdigest()
    return (payload_b64 + b'.' + sig.encode('utf-8')).decode('ascii')

def _verify_token(token: str) -> dict | None:
    """校验 token 签名 + 过期时间,返 payload 或 None"""
    try:
        import base64
        payload_b64, sig = token.split('.', 1)
        expected = hmac.new(_SERVER_SECRET.encode('utf-8'), payload_b64.encode('ascii'),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        # 补回 padding + decode + 验 exp
        pad = 4 - len(payload_b64) % 4
        if pad != 4:
            payload_b64 += '=' * pad
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return None if payload.get('exp', 0) < int(time.time()) else payload
    except Exception:
        return None

# ===== session 表(用 CANVAS_DB,避免新开 DB 文件)=====
def init_auth_db():
    conn = sqlite3.connect(CANVAS_DB)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            last_login_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS canvas_locks (
            canvas_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_locks_user ON canvas_locks(user_id)')
    conn.commit()
    conn.close()

def create_session(user_id: int, user_agent: str = '') -> dict:
    """签发新 token + 写 sessions 表 · 返 {token, expires_at}"""
    expires_at = int(time.time()) + _TOKEN_TTL_SECONDS
    token = _sign_token(user_id, expires_at)
    now = datetime.now().isoformat(timespec='seconds')
    conn = sqlite3.connect(CANVAS_DB)
    conn.execute(
        'INSERT INTO sessions (token, user_id, created_at, expires_at, user_agent) VALUES (?, ?, ?, ?, ?)',
        (token, user_id, now, expires_at, user_agent[:200])
    )
    conn.commit()
    conn.close()
    return {'token': token, 'expires_at': expires_at, 'user_id': user_id}

def get_user_by_token(token: str) -> dict | None:
    """从 token 取 user 信息(含 id/username/display_name/is_admin)"""
    payload = _verify_token(token)
    if not payload:
        return None
    conn = sqlite3.connect(CANVAS_DB)
    conn.row_factory = sqlite3.Row
    # 同时查 session 是否存在(防止被注销)
    sess = conn.execute(
        'SELECT user_id FROM sessions WHERE token = ? AND expires_at > ?',
        (token, int(time.time()))
    ).fetchone()
    if not sess:
        conn.close()
        return None
    user = conn.execute(
        'SELECT id, username, display_name, is_admin, created_at, last_login_at FROM users WHERE id = ?',
        (sess['user_id'],)
    ).fetchone()
    conn.close()
    if not user:
        return None
    return {k: user[k] for k in user.keys()}

def delete_session(token: str) -> bool:
    conn = sqlite3.connect(CANVAS_DB)
    cur = conn.execute('DELETE FROM sessions WHERE token = ?', (token,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0

# ===== 画布锁(简单悲观锁,30 分钟 TTL)=====
def acquire_canvas_lock(canvas_id: int, user_id: int) -> dict:
    """抢占画布编辑锁。返回:
    { ok: True, expires_at, user }     抢到锁
    { ok: False, current_user, expires_at, reason }  被别人锁
    """
    now_ts = int(time.time())
    expires_at = now_ts + _LOCK_TTL_SECONDS
    now = datetime.now().isoformat(timespec='seconds')
    conn = sqlite3.connect(CANVAS_DB)
    conn.row_factory = sqlite3.Row
    cur_lock = conn.execute(
        'SELECT user_id, expires_at FROM canvas_locks WHERE canvas_id = ?', (canvas_id,)
    ).fetchone()
    # 已存在锁
    if cur_lock:
        if cur_lock['expires_at'] > now_ts and cur_lock['user_id'] != user_id:
            other = conn.execute(
                'SELECT username, display_name FROM users WHERE id = ?', (cur_lock['user_id'],)
            ).fetchone()
            conn.close()
            return {'ok': False, 'reason': 'locked_by_other',
                    'current_user': dict(other) if other else None,
                    'expires_at': cur_lock['expires_at']}
        # 自己锁过期/或原本是自己的锁 → 续
        conn.execute(
            '''INSERT INTO canvas_locks (canvas_id, user_id, acquired_at, expires_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(canvas_id) DO UPDATE SET user_id=excluded.user_id,
                   acquired_at=excluded.acquired_at, expires_at=excluded.expires_at''',
            (canvas_id, user_id, now, expires_at)
        )
    else:
        conn.execute(
            'INSERT INTO canvas_locks (canvas_id, user_id, acquired_at, expires_at) VALUES (?, ?, ?, ?)',
            (canvas_id, user_id, now, expires_at)
        )
    conn.commit()
    conn.close()
    return {'ok': True, 'expires_at': expires_at}

def release_canvas_lock(canvas_id: int, user_id: int) -> bool:
    conn = sqlite3.connect(CANVAS_DB)
    cur = conn.execute(
        'DELETE FROM canvas_locks WHERE canvas_id = ? AND user_id = ?',
        (canvas_id, user_id)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0

def get_canvas_lock(canvas_id: int) -> dict | None:
    now_ts = int(time.time())
    conn = sqlite3.connect(CANVAS_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        '''SELECT l.user_id, l.expires_at, u.username, u.display_name
           FROM canvas_locks l JOIN users u ON u.id = l.user_id
           WHERE l.canvas_id = ? AND l.expires_at > ?''',
        (canvas_id, now_ts)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def list_active_collaborators(canvas_id: int) -> list:
    """返回画布的当前协作者(锁持有者)。空列表表示没人编辑"""
    lock = get_canvas_lock(canvas_id)
    if not lock:
        return []
    return [{'user_id': lock['user_id'],
             'username': lock.get('username'),
             'display_name': lock.get('display_name'),
             'expires_at': lock['expires_at']}]
