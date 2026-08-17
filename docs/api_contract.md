# CanvasWeb v3.5.40 · API 契约

> **AI 改前必读**。改任何端点前,先看这里有没有相关定义,改完同步更新本文件。
>
> **基础 URL**:`http://127.0.0.1:9002`(端口见 `server/config.py:PORT`)
> **静态资源**:`http://127.0.0.1:9002/<path>`(从 `client/` 提供,0 缓存)
> **DB**:共用 `_ArchitectLib/PictureDb/PictureDb.db`(与 v1/v2 一致)
> **权限**:POST 限本机 + 局域网 `127.0.0.1` / `192.168.181.136` / `::1`,其它 403

---

## 0. 全局约定

| 项 | 值 |
|---|---|
| 编码 | UTF-8 |
| JSON | `Content-Type: application/json; charset=utf-8` |
| 错误格式 | `{"error": "<message>"}` |
| 并发上限 | 20(超出返 503) |
| Cache-Control | API 全部 `no-store`,图片 `public, max-age=3600` |

---

## 1. 搜索 / 收藏

### `GET /api/search`

按维度筛选缩略图。供主页 + 画布页的左侧图库用。

**Query 参数**(全部可选):
- `q` — 关键词(匹配文件名 / 项目 / 标签)
- `project` — 项目名(空 = 全部)
- `scene` / `light` / `mood` / `arch` / `company` / `view` — 维度
- `favs_only` — `1` = 只看收藏
- `limit` — 默认 100,上限 500

**响应**:
```json
{
  "items": [
    {"id": 123, "thumb": "/img/2026/01/foo_thumb.jpg", "name": "foo", "project": "X", "fav": false}
  ],
  "total": 42
}
```

> **字段说明**:
> - `thumb` — 缩略图 URL。**v3.0 临时 = `url`(原图)**,v2.6 真实生成缩略图(见 `server/handlers/search.py` TODO)
> - `url` — 原图 URL(全分辨率)
> - `fav` — 是否收藏(从 `favorites.json` 读)

### `GET /api/facets`

返回各维度统计(给左侧过滤器用)。

**响应**:
```json
{
  "projects": [{"name": "X", "count": 12}, ...],
  "scenes": [...], "lights": [...], ...
}
```

### `GET /api/favorites`

返回当前收藏列表(从 `favorites.json` 读)。

**响应**:
```json
{"ids": [123, 456, ...]}
```

### `POST /api/favorites`

切换收藏。

**Body**:`{"id": 123}`
**响应**:`{"id": 123, "fav": true}`

---

## 2. 上传 / 生成

### `POST /api/upload_image`

上传图,落 `Input/YYYY-MM-DD/<prefix>_<ts>.<ext>`,返回 URL。

**Body**:`multipart/form-data`,字段名 `file`
**响应**:
```json
{"ok": true, "url": "/upload/Input/2026-07-08/foo_1783550000.png", "name": "foo.png"}
```

### `POST /api/upload_search`

以图找图(base64 → phash → 相似度搜索)。

**Body**:`{"image_base64": "data:image/png;base64,..."}`
**响应**:`{"items": [...], "method": "phash"}`

### `POST /api/ai_image`

调用 matrix MCP 生图,落 `Output/YYYY-MM-DD/`。

**Body**:
```json
{
  "prompt": "...",
  "style_id": "arch",
  "input_urls": ["https://...", ...],  // 参考图
  "aspect_ratio": "16:9",
  "resolution": "2K"
}
```

**响应**:
```json
{"ok": true, "url": "/upload/Output/2026-07-08/xxx.png", "style": "arch"}
```
**耗时**:30-180s(矩阵 MCP 限速)

### `GET /api/ai_styles`

7 种风格列表(见 `server/config.py:AI_STYLES`)。

**响应**:
```json
{
  "styles": [
    {"id": "default", "name": "默认", "suffix": "", "desc": "..."},
    ...
  ]
}
```

### `GET /api/ai_views` *(2026-07-24 加)*

6 个多视角批生成的视角模板。供前端渲染"勾选要哪些视角"UI。

**响应**:
```json
{
  "views": [
    {"id": "aerial",      "name": "鸟瞰",     "prefix": "aerial bird's-eye view, ...", "aspect": "1:1"},
    {"id": "perspective", "name": "人视透视",  "prefix": "eye-level architectural perspective, ...", "aspect": "3:2"},
    {"id": "site",        "name": "总图",     "prefix": "architectural site plan, ...", "aspect": "16:9"},
    {"id": "elevation",   "name": "立面",     "prefix": "front elevation view, ...", "aspect": "16:9"},
    {"id": "section",     "name": "剖面",     "prefix": "building cross-section cut, ...", "aspect": "16:9"},
    {"id": "axonometric", "name": "轴测",     "prefix": "isometric axonometric architectural view, ...", "aspect": "1:1"}
  ]
}
```

### `POST /api/ai_image_batch_start` *(2026-07-24 加)*

**多视角批生成**:一次提交,后端并行起 N 个独立 task,各自走 matrix MCP。
每个 task 的 prompt = `VIEW_TEMPLATES.prefix · 用户 prompt`,aspect 用模板默认。

**Body**:
```json
{
  "prompt": "现代博物馆,玻璃幕墙",
  "style_id": "default",
  "resolution": "2K",
  "views": ["aerial", "perspective", "elevation"],
  "reference_images": ["/img/xxx.jpg", ...]   // 可选,所有视角共用
}
```

**响应**(立即返,不等生成):
```json
{
  "batch_id": "d0ab9bbda6e3",
  "tasks": [
    {"task_id": "d63eccb1f20a", "view_id": "aerial",      "view_name": "鸟瞰",    "aspect_ratio": "1:1",  "full_prompt": "aerial ... · 现代博物馆,玻璃幕墙"},
    {"task_id": "ebf4d9f90068", "view_id": "perspective", "view_name": "人视透视", "aspect_ratio": "3:2",  "full_prompt": "eye-level ... · 现代博物馆,玻璃幕墙"},
    {"task_id": "16ac4a6e2c5a", "view_id": "elevation",   "view_name": "立面",    "aspect_ratio": "16:9", "full_prompt": "front elevation ... · 现代博物馆,玻璃幕墙"}
  ],
  "poll_url_template": "/api/ai_batch/d0ab9bbda6e3",
  "poll_interval_ms": 3000
}
```

**限制**:views 数组去重后最多 6 个;reference_images 所有视角共用(不每视角独立)。

### `GET /api/ai_batch/{batch_id}` *(2026-07-24 加)*

查整个批次的任务状态。整体 status:
- `pending` — 至少一个还在跑
- `done` — 全部 done
- `partial` — 至少一个 done + 至少一个 error(部分失败)
- `error` — 全部失败
- `not_found` — batch_id 不存在

**响应**:
```json
{
  "batch_id": "d0ab9bbda6e3",
  "status": "partial",
  "pending": 1, "done": 1, "error": 1,
  "tasks": [
    {"task_id": "...", "view_id": "aerial", "status": "done",   "local_url": "/upload/Output/2026-07-24/...", ...},
    {"task_id": "...", "view_id": "perspective", "status": "pending", ...},
    {"task_id": "...", "view_id": "elevation",   "status": "error",  "error": "matrix: ...", ...}
  ]
}
```

**前端使用**:3 秒轮询一次,直到 status ∈ {done, partial, error},更新 6 格子 UI。

### `POST /api/ai_styles` *(兼容 v1)*

同 GET 响应(老前端用了 POST)。

---

## 3. 语义搜索

### `POST /api/semantic_search`

**Body**:`{"q": "现代玻璃幕墙", "limit": 20}`
**响应**:`{"items": [...]}`
**依赖**:`_ArchitectLib/_index/embedding.py`(路径待稳定,见 `canvasControl.md` 待办)

---

## 4. 大模型(LLM)

### `GET /api/llm_status`

运行时状态(前端状态灯轮询用,每 5s 一次)。

**响应**:
```json
{
  "enabled": true,
  "loaded": true,
  "model": "Minimax-M3",
  "base_url": "https://api.minimaxi.com/v1",
  "last_error": "",
  "last_call_at": 1783550000
}
```

### `GET /api/llm_config`

读配置(API Key 脱敏,前 4 + 后 4)。

**响应**:
```json
{
  "enabled": true,
  "provider": "openai",
  "base_url": "https://api.minimaxi.com/v1",
  "api_key_masked": "sk-a...xyz",
  "model": "Minimax-M3",
  "system_prompt": "..."
}
```

### `POST /api/llm_config`

保存配置。**空 `api_key` = 保留旧值**(不会误清)。

**Body**:同 GET 响应结构(可只传部分字段)
**响应**:`{"ok": true, "saved_fields": [...]}`

### `POST /api/llm_test`

连通性测试。

**Body**:可选覆盖字段(不传 = 用当前配置)
**响应**:`{"ok": true, "model": "...", "latency_ms": 1234}`

### `POST /api/llm`

调用 LLM。

**Body**:
```json
{
  "messages": [{"role": "user", "content": "..."}],
  "temperature": 0.7,
  "max_tokens": 2048
}
```

**响应**:
```json
{"content": "...", "model": "Minimax-M3", "usage": {...}}
```

---

### `POST /api/optimize_prompt` · 2026-08-05 v3.5.22 加

AI 节点 prompt 优化 — 调 LLM 生成中/英/反向词 4 段对比,专攻建筑外观方向。

**请求 body**:
```json
{
  "canvas_id": 123,
  "node_id": "ai_xxxxx",
  "mode": "architecture"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `canvas_id` | 是 | 画布数字 ID |
| `node_id` | 是 | 节点 ID(必须是有 `prompt` 字段的节点:ai / ai-video / music / tts) |
| `mode` | 否 | 优化方向,默认 `architecture`(目前唯一) |

**响应**:
```json
{
  "ok": true,
  "node_id": "ai_xxxxx",
  "canvas_id": 123,
  "mode": "architecture",
  "original": "用户原 prompt",
  "cn": "中文版 prompt(详细 ≥40 字)",
  "en": "English version(not machine translation, must be architecturally informed rewording)",
  "negative_cn": "模糊,变形,低分辨率,...",
  "negative_en": "blurry, deformed, lowres, watermark, text, signature, ...",
  "prompt_history": ["原版 prompt", "..."],
  "prompt_history_size": 3
}
```

> **内部行为**:自动把当前 `node.prompt` 推到 `node.prompt_history`(FIFO 5 版),不直接覆盖(等用户在前端弹窗确认后调 `_replace`)
> **错误**:400 节点没有 prompt / 404 画布或节点不存在 / 500 LLM 调用失败

### `POST /api/optimize_prompt_replace` · 2026-08-05 v3.5.22 加

用户在弹窗里点"用这版"后调用,把 LLM 生成的某段写回 `node.prompt` / `node.prompt_en`,并把旧版推到 history。

**请求 body**:
```json
{
  "canvas_id": 123,
  "node_id": "ai_xxxxx",
  "prompt": "新 prompt 完整内容",
  "lang": "cn"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `canvas_id` | 是 | 画布 ID |
| `node_id` | 是 | 节点 ID |
| `prompt` | 是 | 新 prompt 文本(trim 后非空) |
| `lang` | 是 | `cn` = 写 `node.prompt` · `en` = 写 `node.prompt_en` · `both` = 自动按行拆(中文/ASCII)分别写 |

**响应**:
```json
{
  "ok": true,
  "node_id": "ai_xxxxx",
  "canvas_id": 123,
  "new_prompt": "写回的中文 prompt",
  "new_prompt_en": "写回的英文 prompt",
  "prompt_history": [...],
  "prompt_history_size": 4
}
```

### `POST /api/optimize_prompt_rollback` · 2026-08-05 v3.5.22 加

把 `node.prompt` 回滚到 `prompt_history` 数组里某一版。

**请求 body**:
```json
{
  "canvas_id": 123,
  "node_id": "ai_xxxxx",
  "version_index": 2
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `canvas_id` | 是 | 画布 ID |
| `node_id` | 是 | 节点 ID |
| `version_index` | 是 | 整数,范围 0..len(history)-1(0 = 最早, N-1 = 最新) |

**响应**:
```json
{
  "ok": true,
  "node_id": "ai_xxxxx",
  "canvas_id": 123,
  "restored_to": "回滚到的 prompt 文本",
  "prompt_history": [...]
}
```

> **内部行为**:把当前 prompt 推到 history 末尾 + 把 target 移到末尾(标记为"当前"),整个 history 截断到 5 版
> **错误**:400 version_index 越界 / 404 节点不存在

### chat 历史服务端持久化 · 2026-08-05 v3.5.39 加

数据落 `_chat_state.json`,按 `user_id` 分块。单用户最多保存 200 条。

#### `GET /api/chat_state?user_id=X`

拉取用户 chat 历史。

**Query**:
- `user_id` — 必填(没填则用 client IP)

**响应**:
```json
{
  "ok": true,
  "user_id": "127.0.0.1",
  "history": [
    {"role": "user", "text": "..."},
    {"role": "assistant", "text": "...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "name": "...", "text": "..."}
  ],
  "count": 12
}
```

#### `POST /api/chat_state`

写入历史(覆盖式)。前端 `_saveHistory` 每次改 history 都调一次。

**Body**:
```json
{
  "user_id": "127.0.0.1",
  "history": [{"role": "user", "text": "..."}]
}
```

**响应**:
```json
{"ok": true, "user_id": "127.0.0.1", "count": 1}
```

#### `DELETE /api/chat_state?user_id=X`

清空某用户历史。

**响应**:
```json
{"ok": true, "user_id": "127.0.0.1", "cleared": true}
```

> **内部行为**:服务端进程内缓存 + 线程锁 + `.tmp` 原子写
> **客户端策略**:`chat-runtime.js` 先 localStorage 速恢,再异步拉服务端覆盖;写入时写 localStorage 立即 + 异步推服务端

### 画布版本快照(2026-07-28 加) · 4 个端点

> 每个画布保留最近 20 份快照,存到 `_canvas_history/<canvas_id>/<timestamp>.json`
> 客户端:工具栏 `历史` 按钮(走 `client/js/modules/canvas-history.js`)

#### `GET /api/canvas_history?canvas_id=X`

列快照(新→旧,默认 20 条)。
**响应**:
```json
{
  "canvas_id": 9,
  "count": 3,
  "items": [
    {"timestamp": "20260807T143012_345", "node_count": 12, "layout_size": 4582, "note": "改完色"},
    ...
  ]
}
```

#### `GET /api/canvas_history/{cid}/{ts}`

拿单份快照(原始 layout JSON)。
**响应**:`{"canvas_id": 9, "timestamp": "...", "layout": {"nodes": [...], "connections": [...], "camera": {...}}}`

#### `POST /api/canvas_history`

save / restore / delete。
**Body**:
```json
{"action": "save",    "canvas_id": 9, "layout": {...}, "note": "改完色"}
{"action": "restore", "canvas_id": 9, "timestamp": "20260807T143012_345"}
{"action": "delete",  "canvas_id": 9, "timestamp": "20260807T143012_345"}
```
**响应**:
```json
{"ok": true, "action": "save", "timestamp": "20260807T143012_345", "kept": 18}  // 自动保留最近 20
```

> **写盘**: `.tmp` 原子写 → 改名 → 删除旧(超过 20)
> **restore**: 备份当前为快照(防回退丢数据) → 写新 layout

---

## 5. 画布(多画布)

### `GET /api/canvases`

画布列表(轻量,不含完整 layout)。

**响应**:
```json
{
  "canvases": [
    {"id": "default", "name": "默认", "updated_at": 1783550000, "node_count": 12}
  ]
}
```

### `GET /api/canvas/{id}`

单个画布(含 nodes + camera)。

**响应**:
```json
{
  "id": "default",
  "name": "默认",
  "layout": {
    "nodes": [...],
    "camera": {"x": 0, "y": 0, "zoom": 1}
  }
}
```

### `POST /api/canvas`

CRUD。

**Body**:
```json
{"action": "create"}                           // 创建(自动给 id)
{"action": "update", "id": "default", "layout": {...}}
{"action": "delete", "id": "old"}
{"action": "rename", "id": "default", "name": "新名"}
```

**响应**:`{"ok": true, "id": "...", "name": "..."}`

---

## 6. 静态资源

| 路径 | 来源 | 缓存 |
|---|---|---|
| `/` | `client/index.html` | no-store |
| `/board` 或 `/board.html` | `client/board.html` | no-store |
| `/js/<file>` | `client/js/<file>` | no-store(AI 改完即生效) |
| `/css/<file>` | `client/css/<file>` | no-store |
| `/img/<rel>` | `Mobile/<rel>` | `max-age=3600` |
| `/upload/Input/<rel>` | `_v25/Input/<rel>` | `max-age=3600` |
| `/upload/Output/<rel>` | `_v25/Output/<rel>` | `max-age=3600` |

---

## 7. 错误码

| 状态 | 触发 |
|---|---|
| 200 | OK |
| 403 | POST 来自非本机 / 路径 `..` 跳出 / 越权 |
| 404 | 静态资源 / 图片 / 画布不存在 |
| 500 | 服务器内部错误(看 `server.err`) |
| 503 | 并发超出 20(给 matrix MCP 留缓冲) |

---

## 6.5. 数据库切换(2026-08-17 v3.5.53 加画布 DB)

> v3.0 早期(2026-07-24)已有图片库切换(picture / analysis),v3.5.53 扩展为**双轴切换**:
> 1. **图片库**(共享 PictureDb / AnalysisDb)· 跟 PictureWeb 共享
> 2. **画布 DB**(Media / App / Game / Robot / Space)· 独立 .db,按工作类型分库,互不污染

### `GET /api/db`

列所有可用图片库 + 当前激活(默认 `picture`)。

**响应**:
```json
{
  "databases": [
    {
      "id": "picture",
      "name": "图片库 (PictureDb)",
      "db_path": "D:/Mac/Mac/Mac/workteam/05_space/03_architect/_ArchitectLib/PictureDb/PictureDb.db",
      "img_root": "D:/Mac/Mac/Mac/workteam/05_space/03_architect/Mobile",
      "exists": true,
      "image_count": 390
    },
    {
      "id": "analysis",
      "name": "分析图库 (AnalysisDb)",
      "db_path": "...",
      "img_root": "...",
      "exists": true,
      "image_count": 11
    }
  ],
  "active_id": "picture"
}
```

### `POST /api/db`

切换激活图片库(立刻生效,所有 handler 跟着切)。

**Body**:
```json
{"id": "picture" | "analysis"}
```

**响应**:`{"ok": true, "type": "image", "active_id": "...", "active_name": "...", "db_path": "...", "img_root": "..."}`

### `GET /api/db?type=canvas`

列所有可用画布 DB + 当前激活(默认 `media`)。**v3.5.53 新加**。

**响应**:
```json
{
  "databases": [
    {
      "id": "media",
      "name": "🎬 Media(媒体/视频)",
      "db_path": "D:/Mac/.../canvasweb/canvas_state.db",
      "icon": "🎬",
      "desc": "视频/影视/动画相关画布",
      "exists": true,
      "canvas_count": 15
    },
    {"id": "app",   "name": "📱 App(应用设计)",    "db_path": ".../canvas_state_app.db",   "icon": "📱", "desc": "APP UI/UX 画布",        "exists": false, "canvas_count": 0},
    {"id": "game",  "name": "🎮 Game(游戏设计)",   "db_path": ".../canvas_state_game.db",  "icon": "🎮", "desc": "游戏场景/角色/剧情画布","exists": false, "canvas_count": 0},
    {"id": "robot", "name": "🤖 Robot(机器人)",    "db_path": ".../canvas_state_robot.db", "icon": "🤖", "desc": "机器人/机械/工业设计",  "exists": false, "canvas_count": 0},
    {"id": "space", "name": "🚀 Space(空间/建筑)", "db_path": ".../canvas_state_space.db", "icon": "🚀", "desc": "建筑/室内/景观/规划",    "exists": false, "canvas_count": 0}
  ],
  "active_id": "media"
}
```

> 5 个工作类型名字固定为 `media` / `app` / `game` / `robot` / `space`(2026-08-17 用户拍板)
> `media` 默认指向老的 `canvas_state.db`(向后兼容,14 个老画布还在)
> 其它 4 个新 .db 首次切到时自动建表(`init_canvases_db`)

### `POST /api/db` body `type: "canvas"`

切换画布 DB。**v3.5.53 新加**。

**Body**:
```json
{
  "id": "media" | "app" | "game" | "robot" | "space",
  "type": "canvas"
}
```

**响应**:
```json
{
  "ok": true,
  "type": "canvas",
  "active_id": "app",
  "active_name": "📱 App(应用设计)",
  "db_path": "D:/Mac/.../canvasweb/canvas_state_app.db"
}
```

> 切完画布 DB 后,**前端 `client/js/modules/db-switcher.js` 监听 `canvas-db:switched` 事件,自动 `location.reload()` 刷整个页面**(所有 client 缓存的 canvases 数据要重新拉)

### 切换原理(`server/db_state.py`)

- 2026-08-17 改:**thread-local 隔离**(`threading.local()`)替代全局单例 + Lock
  - 避免跟 `thumbs.py` 抢锁导致 D-001 那种"5 个端点 404"症状
  - 切换后**当前请求的 thread 立刻生效**,新请求按自己的 thread-local 状态
- `_LazyCanvasDB` proxy(`server/config.py`)
  - 通过 `__fspath__` 协议让所有 `from .config import CANVAS_DB` 自动走 `db_state.get_canvas_db()`
  - 老代码 `sqlite3.connect(CANVAS_DB)` 不用改,自动走多 DB 切换

### 切换 UI 位置

顶部工具栏,跟"图片库下拉"并排,新加"画布库下拉"(v3.5.53)。`client/js/modules/db-switcher.js` 渲染两个独立 `<select>`。

---

## 8. 反馈 issues(双平台镜像)· 2026-08-06 v3.5.41 加

把用户对画布/项目的反馈自动转 GitHub + Gitee 双平台 issue。
**踩坑提醒**:
- GitHub POST `/repos/{owner}/{repo}/issues` → 带 `{repo}`
- Gitee POST `/v5/repos/{owner}/issues` → **不带** `{repo}`,repo 在 body(2026-08-04 踩坑)
- 本机 `127.0.0.1:21081` HTTP_PROXY 阻断 urllib,必 `ProxyHandler({})` 绕开

### `POST /api/feedback_arch`

并行创建 GitHub + Gitee issue(任一成功即返 `ok: true`)。
Body:
```json
{
  "title": "图片节点 IO-port 散落",
  "body": "画布 1 加载后 IO-port 位置不对,跟节点边缘错开",
  "labels": ["bug", "ui"]    // 可选,最多 5 个
}
```

响应(200 / 502):
```json
{
  "ok": true,                  // 任一平台成功
  "title": "图片节点 IO-port 散落",
  "results": {
    "github": {"ok": true,  "number": 42, "html_url": "https://github.com/.../issues/42", "platform": "github"},
    "gitee":  {"ok": false, "status": 401, "error": "..."}  // 失败细节
  }
}
```

**不真打示例**(smoke 测试用):空 body → 400 `{"ok": false, "error": "title 必填"}`。

### `GET /api/feedback_arch?platform=both|github|gitee&state=open|closed`

列双平台 issues(实时,无缓存)。
- `platform=both` (默认) — 双平台都列
- `platform=github` / `platform=gitee` — 只列一个
- `state=open` (默认) / `closed` / `all`

响应:
```json
{
  "platform": "both",
  "state": "open",
  "count": 5,
  "items": {
    "github": [{"number": 42, "title": "...", "html_url": "...", "labels": [...], "platform": "github", ...}],
    "gitee":  [{"number": 38, "title": "...", "html_url": "...", "labels": [...], "platform": "gitee",  ...}]
  }
}
```

### `GET /api/feedback_arch/daily`

去重后的每日摘要(24h 缓存,给 cron + 浏览器用)。按 title 归一化,同一反馈在 GitHub + Gitee 上合并。

响应(200):
```json
{
  "updated_at": "2026-08-06T11:55:00",
  "count": 2,
  "items": [
    {
      "title": "v3.5.40 节点连不上",
      "gh": {"number": 45, "html_url": "https://github.com/.../issues/45"},
      "gt": {"number": 41, "html_url": "https://gitee.com/.../issues/41"},
      "labels": ["bug"]
    }
  ],
  "_cache": "hit"  // 或 "miss" 表示刚刷新
}
```

**缓存位置**: `logs/.feedback_arch_daily_cache.json`,24h TTL,删文件强制刷新。

---

## 9. 改前必读(给 AI)

1. **改端点前**:先看本文件 → 找对应章节 → 改 `server/handlers/<name>.py` 的 `handle_xxx`
2. **改完必做**:更新本文件对应章节(请求/响应/状态码)
3. **新加端点**:在 `server/routes.py` 注册 → 更新本文件 → 跑 `_smoke.py` 验证
4. **新加前端调用**:在 `client/js/api.js` 加 `export async function xxx()` → 在 `client/js/modules/*.js` 调用
5. **不破坏 v1 兼容**:v1(8082) 还在跑,所有 API 行为必须等价(响应字段不删只加)

---

> 变更记录
> - 2026-08-06 · v3.5.41 · 加 `/api/feedback_arch` 3 个端点(create / list / daily):反馈转 GitHub + Gitee 双平台 issue · Gitee POST path 不带 {repo} 踩坑已注释
> - 2026-08-05 · v3.5.22-28 · 加 `/api/optimize_prompt` / `_replace` / `_rollback` 3 个端点(AI 节点 prompt 优化,4 段生成 + 历史回滚 · 详见第 4 节)
> - 2026-07-08 · v3.0 升格端口 9002,加 client/ 静态资源规范 · arch2
> - 2026-07-02 · v2 重构(端口 8083)· arch2
> - 2026-06-27 · v1 初版(端口 8082)· arch2
