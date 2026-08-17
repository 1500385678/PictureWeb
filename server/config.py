"""CanvasWeb v3.0 配置 · 路径 / 权限 / 并发 / 常量
被谁调用:server/__main__.py + server/handlers/*(只读)
改前必读:本文件是单一事实源,改 PORT/CLIENT_DIR/ADMIN_IPS 都要同步 _daemon.py 和 _start.ps1
2026-08-17 改:CANVAS_DB 改成 lazy proxy, 实际路径从 db_state.get_canvas_db() 读
  之前所有 from .config import CANVAS_DB 不用改,自动走多 DB 切换
"""
import os
import re
import shutil
from datetime import datetime
from threading import Lock
# 2026-08-17 注:不要在 import 时 from . import db_state
#   那样会死循环(db_state 加载时 config 还在初始化)
#   改成在 _LazyCanvasDB 里 lazy import


# ===== 2026-08-17 加:CANVAS_DB lazy proxy =====
# 让所有 `from .config import CANVAS_DB` 的调用,自动走 db_state.get_canvas_db()
# 用户切画布库后,新连接读新 DB 文件
# 兼容 sqlite3.connect(CANVAS_DB) — 通过 __fspath__ 协议
class _LazyCanvasDB:
    def __fspath__(self):
        # lazy import:首次访问时才 import db_state(避免循环)
        from . import db_state
        return db_state.get_canvas_db()
    def __str__(self):
        from . import db_state
        return db_state.get_canvas_db()
    def __repr__(self):
        try:
            from . import db_state
            return f'<LazyCanvasDB → {db_state.get_canvas_db()}>'
        except Exception:
            return '<LazyCanvasDB (loading)>'

# ===== 路径 =====
# BASE_DIR = _v25/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 2026-07-28 改:硬编码 D:/Mac/... 改 env 变量 + 默认值(以前换机即失效)
# 2026-08-17 修:默认路径从 2 层 Mac 改 3 层 Mac(AGENTS.md 实际工作目录)
#   之前 2 层 Mac 路径下,Windows 大小写不敏感机制导致两个目录共存:
#     - 真实数据在 3 层 Mac 小写 l 的 _architectlib/PictureDb/PictureDb.db
#     - 2 层 Mac 大写 L 的 _ArchitectLib/PictureDb/PictureDb.db 是个 0 字节空文件
#   启 server 时如果 env var 没传,fallback 到 2 层 Mac,会 search 500 + facets 500
# 设环境变量: PICTUREWEB_HOME / CANVASWEB_ANALYSIS_DB / CANVASWEB_ANALYSIS_MOBILE
PICTUREWEB_HOME = os.environ.get('PICTUREWEB_HOME', 'D:/Mac/Mac/Mac/workteam/05_space/03_architect')

# 共用 DB · 兄弟目录 PictureDb/PictureDb.db(与 v1 / v2 共用)
# 2026-07-09 修正:v3.0 在 _ArchitectLib/CanvasWeb-v3.0/ 下(比 v1/v2 多嵌一层),用 1 个 .. 即可
# 2026-07-24 改:DB/IMG_ROOT/THUMB_ROOT 现在是"激活数据库"对应的值
#               实际值由 db_state.get_db() 等函数提供(支持多数据库切换)
#               这里保留为默认(picture)的硬编码,只用于 db_state 初始化 + _inject_ref_features fallback
DB = os.path.join(PICTUREWEB_HOME, '_ArchitectLib', 'PictureDb', 'PictureDb.db')  # 2026-07-22 改用 PICTUREWEB_HOME

# 2026-07-24 加:多数据库配置 · 前端下拉切换"激活"哪个
# 多个 DB 可挂载,运行时切换(全局单例,所有 handler 共享)
# 2026-07-28 改:analysis 库路径改 env 变量可覆盖(以前硬编码 D:/Mac/Mac/Mac/...)
_ANALYSIS_DB = os.environ.get(
    'CANVASWEB_ANALYSIS_DB',
    'D:/Mac/Mac/Mac/workteam/05_space/03_architect/Attack/03-Analysis/_ArchiAttackAnalysisLib/AnalysisWeb/_AnalysisDb/AnalysisDb.db'
)
_ANALYSIS_MOBILE = os.environ.get(
    'CANVASWEB_ANALYSIS_MOBILE',
    'D:/Mac/Mac/Mac/workteam/05_space/03_architect/Attack/03-Analysis/Mobile'
)
DATABASES = {
    'picture': {
        'name': '图片库 (PictureDb)',
        'db_path': DB,                                           # 同上
        'img_root': os.path.join(PICTUREWEB_HOME, 'Mobile'),    # 2026-07-22 改用 PICTUREWEB_HOME
        'thumb_root': os.path.join(PICTUREWEB_HOME, '_ArchitectLib', 'PictureDb', 'thumbs'),
    },
    'analysis': {
        'name': '分析图库 (AnalysisDb)',
        'db_path': _ANALYSIS_DB,
        'img_root': _ANALYSIS_MOBILE,
        'thumb_root': _ANALYSIS_MOBILE,  # AnalysisDb 没单独 thumb 目录,直接用 img_root
    },
}
DEFAULT_DB_ID = 'picture'  # 启动默认激活的 DB

# 独立运行时数据 · 不与 v1 / v2 共享
# 2026-08-17 改:CANVAS_DB 变成 _LazyCanvasDB proxy(支持运行时切换画布库)
CANVAS_DB = _LazyCanvasDB()
FAV_FILE = os.path.join(BASE_DIR, 'favorites.json')
LLM_CONFIG_FILE = os.path.join(BASE_DIR, '_llm_config.json')

# 2026-08-17 加:画布多 DB(按工作类型分库)
# 每个 work-type 一个独立 .db 文件,互不污染
# media 默认指向老的 canvas_state.db(向后兼容, 13 个老画布还在)
# 其它 4 个新 .db(空文件,首次切自动建表)
CANVAS_DATABASES = {
    'media': {
        'name': '🎬 Media(媒体/视频)',
        'db_path': os.path.join(BASE_DIR, 'canvas_state.db'),  # ← 向后兼容:用老 DB
        'icon': '🎬',
        'desc': '视频/影视/动画相关画布',
    },
    'app': {
        'name': '📱 App(应用设计)',
        'db_path': os.path.join(BASE_DIR, 'canvas_state_app.db'),
        'icon': '📱',
        'desc': 'APP UI/UX 画布',
    },
    'game': {
        'name': '🎮 Game(游戏设计)',
        'db_path': os.path.join(BASE_DIR, 'canvas_state_game.db'),
        'icon': '🎮',
        'desc': '游戏场景/角色/剧情画布',
    },
    'robot': {
        'name': '🤖 Robot(机器人)',
        'db_path': os.path.join(BASE_DIR, 'canvas_state_robot.db'),
        'icon': '🤖',
        'desc': '机器人/机械/工业设计',
    },
    'space': {
        'name': '🚀 Space(空间/建筑)',
        'db_path': os.path.join(BASE_DIR, 'canvas_state_space.db'),
        'icon': '🚀',
        'desc': '建筑/室内/景观/规划',
    },
}
DEFAULT_CANVAS_DB_ID = 'media'  # 默认激活(media 用老 DB,无感)

# 上传 / 生成图归档
INPUT_DIR = os.path.join(BASE_DIR, 'Input')
OUTPUT_DIR = os.path.join(BASE_DIR, 'Output')
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 客户端静态资源(HTML / CSS / JS)
CLIENT_DIR = os.path.join(BASE_DIR, 'client')

# 图片根(2026-06-28 迁移):03_architect/Mobile
# 2026-07-09 修正:v3.0 在 _ArchitectLib/CanvasWeb-v3.0/ 下,用 2 个 .. 即可
IMG_ROOT = os.path.join(PICTUREWEB_HOME, 'Mobile')  # 2026-07-22 改用 PICTUREWEB_HOME
# 旧 Mac 路径前缀(数据库里存的旧路径)
OLD_IMG_ROOT = '/Users/aaron/Mac/WorkTeam/05_Space/03_Architect/Mobile'

# 缩略图根(2026-07-09 加)· _ArchitectLib/PictureDb/thumbs/<rel>
# 与 PictureDb.db 同级,共享兄弟目录
THUMB_ROOT = os.path.join(PICTUREWEB_HOME, '_ArchitectLib', 'PictureDb', 'thumbs')  # 2026-07-22 改用 PICTUREWEB_HOME
os.makedirs(THUMB_ROOT, exist_ok=True)
THUMB_SIZE = 240  # 缩略图最大边长(像素)

# 2026-07-09 加:AI 生成图独立数据库 · 放在 Output/ 目录里,不和图库(PictureDb.db)混
AI_IMAGES_DB = os.path.join(OUTPUT_DIR, 'ai_images.db')

# 2026-07-09 加:AI 生成视频独立数据库(同样放 Output/ 目录)
AI_VIDEOS_DB = os.path.join(OUTPUT_DIR, 'ai_videos.db')

# 2026-07-09 加:AI 视频风格预设(简单模式,后续按需扩展)
AI_VIDEO_STYLES = [
    {'id': 'default',  'name': '默认',        'suffix': '', 'desc': '矩阵默认模型'},
    {'id': 'cinematic','name': '电影感',       'suffix': ', cinematic, smooth camera motion, high production value, 8k', 'desc': '电影质感镜头'},
    {'id': 'walk',     'name': '建筑漫步',     'suffix': ', architectural walkthrough, smooth dolly shot, natural lighting', 'desc': '建筑外观环绕'},
    {'id': 'orbit',    'name': '环绕运镜',     'suffix': ', orbital camera, smooth rotation around subject, dramatic', 'desc': '环绕主体'},
    {'id': 'timelapse','name': '延时摄影',     'suffix': ', timelapse, fast motion, day-to-night transition, cloud movement', 'desc': '延时变化'},
]

# 静态资源 MIME(2026-07-14 加:视频/音频扩展,缺这些 <video>/<audio> 不识别)
MIME_MAP = {
    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
    'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp',
    # 视频(matrix 视频生成常用)
    'mp4': 'video/mp4', 'm4v': 'video/mp4',
    'mov': 'video/quicktime', 'webm': 'video/webm',
    'mkv': 'video/x-matroska', 'avi': 'video/x-msvideo',
    # 音频
    'mp3': 'audio/mpeg', 'wav': 'audio/wav',
    'ogg': 'audio/ogg', 'flac': 'audio/flac',
    'm4a': 'audio/mp4', 'aac': 'audio/aac',
}

# ===== 端口(2026-07-08 v3.0)=====
PORT = 9002  # v3.0 端口,避开 v1(8082) / v2(8083)

# ===== 权限(2026-06-27)=====
ADMIN_IPS = {'127.0.0.1', '192.168.181.136', '::1'}

# ===== 并发限制(2026-06-27)=====
MAX_CONCURRENT = 20
active_lock = Lock()
active_count = 0

# ===== 超时常量中心(2026-08-14 加 · 改前必读:这是单一事实源)=====
# 之前 timeout 散在 7-8 个文件, 改一处要全文搜
# 对应前端:client/js/core/constants.js 的 TIMEOUTS
TIMEOUTS = {
    'LLM_CALL_MS': 90,                  # llm.py urllib 调用 LLM(秒, 不是毫秒!)
    'LLM_TEST_MS': 30,                  # llm.py _llm_test 连通测试
    'MATRIX_UPLOAD_MS': 300,            # _matrix_upload._put_bytes_raw
    'MATRIX_GET_URL_MS': 30,            # _matrix_upload.get_upload_url
    'AI_VIDEO_DOWNLOAD_MS': 180,        # ai_video.py 下载 CDN 视频
    'IMAGE2TEXT_DOWNLOAD_MS': 60,       # image2text.py 下载图片
    'TTS_DOWNLOAD_MS': 60,              # tts.py 下载音频
    'MATRIX_RETRY': 3,                  # _matrix_http 重试次数
    'MATRIX_BACKOFF': (2, 4),           # 退避秒数
}

LIMITS = {
    'PROMPT_MAX_LEN': 8000,             # AI 节点 prompt 最大字符(防 10MB 攻击)
    'MATRIX_MAX_UPLOAD_BYTES': 500 * 1024 * 1024,  # 500MB
    'CHAT_IMAGES_MAX': 3,
    'CHAT_IMG_SIZE': 512,
}

# ===== LLM 默认配置 =====
DEFAULT_LLM_CONFIG = {
    'enabled': False,
    'provider': 'openai',
    'base_url': 'https://api.minimaxi.com/v1',
    'api_key': '',
    'model': 'Minimax-M3',
    'system_prompt': '你是建筑外立面方案设计助手。回答简洁专业,避免套话,不要 Markdown 标题。',
    'last_test_ok': False,
    'last_test_msg': '',
}
LLM_STATE = {'loaded': False, 'last_error': '', 'last_call_at': 0}

# ===== AI 生图风格(2026-07-01)=====
AI_STYLES = [
    {'id': 'default',    'name': '默认',     'suffix': '', 'desc': '矩阵默认模型,无风格偏向'},
    {'id': 'photo',      'name': '写实摄影', 'suffix': ', photorealistic, high detail, 8k, sharp focus, natural lighting', 'desc': '照片级真实感'},
    {'id': 'arch',       'name': '建筑渲染', 'suffix': ', architectural visualization, soft daylight, clean lines, neutral palette, octane render, 8k', 'desc': '建筑可视化、柔和日光'},
    {'id': 'anime',      'name': '动漫插画', 'suffix': ', anime style, cel shading, vibrant colors, detailed', 'desc': '二次元、cel shading'},
    {'id': 'sketch',     'name': '手绘草图', 'suffix': ', pencil sketch, hand-drawn, architectural drawing, monochrome', 'desc': '铅笔手绘风'},
    {'id': 'watercolor', 'suffix': ', watercolor painting, soft edges, artistic, paper texture', 'name': '水彩艺术', 'desc': '水彩画、柔边'},
    {'id': 'noir',       'name': '暗黑未来', 'suffix': ', dark cinematic, noir lighting, futuristic, moody atmosphere, high contrast', 'desc': '暗黑、电影感'},
]

# ===== 画布 =====
EMPTY_LAYOUT = {'nodes': [], 'camera': {'x': 0, 'y': 0, 'zoom': 1}}


# ===== 工具函数 =====
def today_dir(base):
    today = datetime.now().strftime('%Y-%m-%d')
    d = os.path.join(base, today)
    os.makedirs(d, exist_ok=True)
    return d


def save_bytes(raw, base_dir, prefix, ext):
    today = today_dir(base_dir)
    ts = int(datetime.now().timestamp() * 1000)
    if not ext:
        ext = 'png'
    ext = ext.lstrip('.').lower()
    safe = re.sub(r'[^\w\-.]', '_', prefix)[:40] or 'file'
    name = f'{safe}_{ts}.{ext}'
    full = os.path.join(today, name)
    with open(full, 'wb') as f:
        f.write(raw)
    return full


def local_to_upload_url(absolute_path):
    rel = os.path.relpath(absolute_path, BASE_DIR).replace(os.sep, '/')
    return '/upload/' + rel


def seed_from_v1():
    """首次启动时,从 v1(8082)复制 favorites / LLM config(独立副本,不回写)
    被谁调用:server/__main__.py
    """
    src_dir = os.path.normpath(os.path.join(BASE_DIR, '..'))
    for fname in ['favorites.json', '_llm_config.json']:
        src = os.path.join(src_dir, fname)
        dst = os.path.join(BASE_DIR, fname)
        if not os.path.exists(dst) and os.path.exists(src):
            shutil.copy2(src, dst)
            print(f'[seed] {fname} ← {src}', flush=True)
