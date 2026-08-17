# AGENTS.md · CanvasWeb v3.5.48 · AI 协作者必读

> **任何 AI(我 / 后续 model)改这个项目前,先读完本文件 + api_contract.md + `01_开发纪要-错误总结与避坑指南.md`。**
> 这是项目元数据 + 操作约束的单一事实源。**`01_开发纪要`** 汇总了 v3.5.22-40 期间踩过的 30+ 个错误和防御措施,改前必读避免重复犯错。

---

## 0. 项目是什么

**CanvasWeb v3.0** 是建筑师工作台的气泡板工具。从 PictureDb(图库)拖图、搜索、AI 生图、组织成多画布,保存到 SQLite + JSON。

| 维度 | 值 |
|---|---|
| 端口 | **9002**(v3.0) · 8082(v1 已退役, 数据备份) · 8083(v2 已退役) |
| 后端 | Python 标准库 · `http.server` + SQLite,无第三方依赖 |
| 前端 | 原生 ES Modules · 零构建工具,无 npm 依赖 |
| 数据 | SQLite (画布状态) + JSON (收藏 / LLM 配置) + 共享 PictureDb |
| 启动 | `python _daemon.py` 后台 / `python -X utf8 -u -m server` 前台 |
| 验证 | `python _smoke.py` 期望 `✅ 14/14 endpoints OK` |

> v3.0 → v3.5.53 共 36 个小版本(v3.1.0 ~ v3.5.53),2026-08-05 单日连推 18 个版本(v3.5.22 ~ v3.5.39) + 2026-08-06/08 续推 v3.5.40 ~ v3.5.52 共 12 个 + 2026-08-17 v3.5.53 夜间迭代补 3 修,主要新增 ✨ AI 节点 prompt 优化 / 建筑外观 34 预设 / 视频 15 预设 / 节点连接线 / 批量操作 / 画布导出 PNG / chat 历史服务端持久化 / Issues 反馈双平台同步 / 画布间复制粘贴 / FAB 反馈 / 文档同步 / AI→视频参考图传递修复 / AI 助手卡死修复 / 工程质量 5 大改造 / thumbs 异常收集 / 文档数字守卫 / smoke 启动前 precheck 等 33 个功能(详见第 9 节变更记录)

---

## 1. 改前必读(顺序)

1. **`01_开发纪要-错误总结与避坑指南.md`** · 30+ 个错误复盘 + 防御措施
2. **`api_contract.md`** · 所有 API 端点的请求/响应/字段
3. **本文件** · 架构 + 约束
4. **`STYLE.md`** · 代码风格
5. **`WORKFLOWS.md`** · 8 阶段工作流

---

## 2. 架构

> **权威清单**(2026-08-10 实测):
> - 后端 handler: `ls server/handlers/*.py | grep -v __init__ | wc -l` = **26 个**(详见下,2026-08-17 v3.5.53 实测)
> - 前端 module: `ls client/js/modules/*.js | grep -v .bak | wc -l` = **77 顶层 + chat-skills/ 19 = 96 个**(详见下,2026-08-17 v3.5.53 实测)
> - 校验:`ls server/handlers/ | wc -l` = 24(包含 `__init__.py` / `__pycache__/`,不计入 handler 数量)
> - **MAIN.md §1 §2 不再手写清单**,改「见 AGENTS.md §2 + 命令验证」(2026-08-10 v3.5.48 落实,避免三处文档漂移)

### 后端(`server/`)
```
server/
├── __init__.py        # 版本号
├── __main__.py        # 入口(108 行)· 启动 + 静态服务 + 路由分发
├── routes.py          # 路由表(120 行)· 2026-07-28 加 admin 闸门白名单
├── config.py          # 路径/端口/权限/常量(124 行)· 2026-07-28 硬编码改 env
├── core.py            # BaseHandler + 并发限制(64 行)
├── img.py             # /img/ /upload/ 静态服务(51 行)
└── handlers/          # 业务端点
    ├── search.py      (139 行 · 2026-07-28 FTS 参数化)
    ├── favorites.py   (48 行)
    ├── upload.py      (81 行)
    ├── ai_image.py    (865 行 · 含批量/任务/下载/归档)
    ├── ai_video.py    (393 行)
    ├── image2text.py  (336 行)
    ├── music.py       (275 行)
    ├── llm.py         (266 行 · 含 function-calling + 重试)
    ├── tts.py         (223 行)
    ├── export_pdf.py  (220 行)
    ├── users.py       (175 行)
    ├── semantic.py    (164 行)
    ├── canvas.py      (239 行 · 2026-07-28 加软删)
    ├── db.py          (50 行)
    ├── feedback.py    (48 行)
    ├── optimize_prompt.py (271 行 · 2026-08-05 v3.5.22 加:AI 节点 prompt 优化 / 4 段生成 / 历史回滚)
    ├── canvas_history.py (137 行 · 2026-07-28 加:画布快照 · 列表/取/恢复/删除)
    ├── chat_state.py (120 行 · 2026-08-05 v3.5.39 加:chat 历史服务端持久化 · _chat_state.json 按 user_id 分块)
    ├── prompt_templates.py (92 行 · 2026-07-28 加:用户 prompt 模板 CRUD)
    ├── ai_inpaint.py (2026-08 v3.5.40+ 加:AI 局部重绘)
    ├── sketchup_import.py (2026-08 v3.5.40+ 加:SketchUp 模型导入)
    ├── feedback_arch.py (2026-08-06 v3.5.41 加:反馈走 GitHub + Gitee 双平台 issues · /api/feedback_arch 3 端点)
    └── (26 个 handler,均按职责单文件 · 2026-08-17 v3.5.53 实测,见顶部权威清单)
```

### 前端(`client/`)
```
client/
├── index.html         # 主页(230 行 · 瘦)
├── board.html         # 画布页(138 行 · 瘦)
├── css/
│   ├── common.css     # 基础布局
│   ├── panel.css      # 弹窗/浮层
│   └── board.css      # 画布节点
└── js/
    ├── main.js        # 主页入口(267 行)
    ├── board-main.js  # 画布页入口(164 行)
    ├── api.js         # 所有 /api/* 调用(318 行)
    ├── core/
    │   ├── state.js   # 全局状态(116 行)
    │   ├── dom.js     # DOM 工具(77 行)
    │   └── events.js  # 事件总线(53 行)
    └── modules/       # 业务模块
        ├── canvas-nodes.js     (494 行 · 最大 · 5+种节点绘制 + 连接线 + desc 徽章)
        ├── ai-multi-panel.js   (392 行 · 多视角 6 格子)
        ├── canvas-board.js     (510 行 · 主画布 + 连接线交互 + 快捷键 + 改名/备注/批量)
        ├── ai-video-panel.js   (357 行)
        ├── drag.js             (373 行 · 拖动/滚轮/框选 + 对齐辅助线)
        ├── music-panel.js      (300 行)
        ├── canvas-list.js      (299 行)
        ├── main.js             (267 行 · 上方)
        ├── image2text-panel.js (265 行)
        ├── tts-panel.js        (262 行)
        ├── ai-build.js         (281 行 · v3.5.39 拆分,从 760 行瘦下来,re-export 旧 API)
        ├── ai-build-extras.js  (201 行 · v3.5.39 拆:全屏/下载/popover/像素/带入对话)
        ├── ai-build-chips.js   (161 行 · v3.5.39 拆:模板下拉 + 4 维 chip)
        ├── ai-build-undo.js    (85 行 · v3.5.39 拆:节点级撤销栈)
        ├── ai-build-queue.js   (65 行 · v3.5.39 拆:重跑队列)
        ├── align.js            (226 行)
        ├── group.js            (220 行)
        ├── node-query.js       (222 行)
        ├── ai-utils.js         (207 行)
        ├── ai-compare.js       (207 行)
        ├── connections.js      (189 行)
        ├── ai-state.js         (161 行 · 进度可视化)
        ├── ai-optimize.js      (326 行 · v3.5.22 加:✨ 优化对比弹窗 + 历史回滚)
        ├── ai-arch-presets.js  (600 行 · v3.5.23 加:建筑外观 34 预设 4 维 chip)
        ├── ai-video-presets.js (280 行 · v3.5.24 加:建筑视频 15 预设 4 维 chip)
        ├── bulk-actions.js     (254 行 · v3.5.37 加:批量操作浮动栏 · 略超临界)
        ├── node-resize.js      (211 行 · 8 角 resize handle)
        ├── export.js           (60 行 · v3.5.39 改:共享 _renderToCanvas 走 JPG/PNG)
        ├── export-pdf.js       (110 行 · v3.5.39 改:dialog 加 PNG/JPG 选项)
        ├── text-edit.js        (92 行)
        ├── name-edit.js        (123 行 · v3.5.34 加:节点 name 标签双击改名)
        ├── desc-edit.js        (128 行 · v3.5.36 加:节点备注/说明)
        ├── history.js          (108 行)
        ├── chat-panel.js       (143 行)
        ├── chat-runtime.js     (224 行 · v3.5.39 改:服务端持久化 + localStorage 缓存)
        ├── chat-skills/        (20 个文件:registry + index + 18 个 skill)
        ├── global-search.js    (145 行)
        ├── feedback.js         (78 行)
        ├── collab.js           (148 行 · 协作)
        ├── ai-build-chips.js   (161 行 · v3.5.39 拆)
        ├── ai-build-extras.js  (201 行 · v3.5.39 拆)
        ├── ai-build-undo.js    (85 行 · v3.5.39 拆)
        ├── ai-build-queue.js   (65 行 · v3.5.39 拆)
        ├── ai-arch-presets.js  (600 行 · v3.5.23 加:建筑外观 34 预设)
        ├── ai-video-presets.js (280 行 · v3.5.24 加:建筑视频 15 预设)
        ├── ai-optimize.js      (326 行 · v3.5.22 加)
        ├── bulk-actions.js     (254 行 · v3.5.37 加)
        ├── canvas-paste-to.js  (104 行 · v3.5.44 加:画布间复制)
        ├── issues-panel.js     (2026-08-06 v3.5.42 加:反馈 UI)
        ├── canvas-fit.js       (2026-08-06 v3.5.40.3 加:画布自动 fit-to-view)
        ├── name-edit.js        (123 行 · v3.5.34 加)
        ├── desc-edit.js        (128 行 · v3.5.36 加)
        ├── (96 个模块 = 77 顶层 + 19 chat-skills · 2026-08-17 v3.5.53 实测,见顶部权威清单)
```

### 通信
- **API** → `client/js/api.js` 封装所有 `/api/*`,禁止直接 `fetch`
- **跨模块** → `core/events.js` 的 `bus`(`bus.emit('canvas:dirty')` / `bus.on('canvas:dirty', fn)`)
- **状态** → `core/state.js` 集中管理(相机 / 节点 / 选中 / 过滤 / 元数据),各模块 `import` 使用

---

## 3. 硬约束(强底线)

| 项 | 上限 | 例外 |
|---|---|---|
| **单文件行数** | **< 250 行** | `canvas-nodes.js` 494 行(5+种节点绘制 + 连接线 + desc 徽章) · `ai-multi-panel.js` 392 行(6 视角) · `canvas-board.js` 510 行(主画布 + 连接线 + 快捷键 + 改名/备注/批量) · `ai-video-panel.js` 357 行 · `drag.js` 373 行(对齐辅助线) · `music-panel.js` 300 行 · `canvas-list.js` 299 行 · `main.js` 267 行 · `image2text-panel.js` 265 行 · `tts-panel.js` 262 行 · `api.js` 318 行 · `ai-optimize.js` 326 行 · `bulk-actions.js` 254 行(略超,临界) · `ai-arch-presets.js` 600 行(纯数据,合理) · `ai_image.py` 891 行(`ai-image-batch.py` / `ai-image-tasks.py` 拆分待办) · **v3.5.39 拆分后 `ai-build.js` 281 行**(4 个子模块都 < 250 行:`ai-build-extras.js` 201 / `ai-build-chips.js` 161 / `ai-build-undo.js` 85 / `ai-build-queue.js` 65) |
| **Python 依赖** | **仅标准库** | 任何 `pip install` 必须先讨论 |
| **前端依赖** | **零 npm** | 任何 `package.json` 必须先讨论 |
| **端口** | **9002** | 改 → 同步 `config.py:PORT` + `api_contract.md` + `_daemon.py` |
| **API 路径** | **不可删,只加** | 删字段会让 v1(8082)前端失效 |
| **API 响应** | **加字段可以,字段重命名不行** | 同上 |
| **CSS 缓存** | HTML/CSS/JS 全部 `no-store` | AI 改完即生效 |
| **图片缓存** | `max-age=3600` | 不变 |
| **写入权限** | 限 `127.0.0.1` / `192.168.181.136` / `::1` | 改 → 同步 `config.py:ADMIN_IPS` |
| **错误响应** | 一律用 `handler.safe_error(code, msg)` 不用 `handler.send_error(...)` | `http.server.send_error` 内部 latin-1 编码,Windows OSError 消息含中文(`拒绝访问` 等)→ `UnicodeEncodeError` → `process_request_thread` 死、端口无响应。`safe_error` 在 `core.BaseHandler` 统一做 ASCII-safe + write 兜底 · 加新 handler 必走它 |
| **并发上限** | 20 | 超出返 503 |

---

## 4. 加新功能的标准流程

### 加一个 API 端点
1. 看 `api_contract.md` 找对应章节 / 决定新章节
2. 在 `server/handlers/` 写 `<新功能>.py`:
   ```python
   def handle_xxx(handler, parsed, body):
       handler._json({'ok': True, ...})
   ```
3. 在 `server/routes.py` 注册(`ROUTES_GET` / `ROUTES_POST`)
4. 更新 `api_contract.md`
5. 在 `client/js/api.js` 加 `export async function xxx()`
6. 在对应 `client/js/modules/*.js` 调用
7. 跑 `python _smoke.py` 验证

### 加一个 UI 模块
1. 在 `client/js/modules/<新模块>.js` 写 `export function init(container) { ... }`
2. 在 `client/css/` 写样式
3. 在 `client/js/main.js` 或 `board-main.js` 调 `init()`
4. 跑 `python _smoke.py` 确认无 500

### 加一个节点类型(如"视频节点")
1. 在 `canvas-nodes.js` 加 `drawVideoNode` + 在 `DRAWERS` 注册
2. 在 `state.js` 加 `newNodeId('video')` 的便利方法
3. 在 `main.js` / `board-main.js` 的 `_addAtCenter` 加 case
4. 写 `videos` 表(如需持久化)+ 后端 `server/handlers/videos.py`

### 加一个建筑外观预设(2026-08-05 v3.5.23 起 · 0 风险纯前端)
- 适用场景:复用预拼好的"风格 × 场景 × 光线 × 镜头"组合 prompt,免去用户手写
- **不要**新加后端 / 数据库 / API 端点,纯前端模块
- 数据放 `client/js/modules/ai-arch-presets.js`(纯数据)或 `ai-video-presets.js`(视频,复用 ai-arch-presets 的字典)
- 字典:ARCH_STYLES / ARCH_SCENES / ARCH_LIGHTINGS / ARCH_CAMERAS(生图)· VIDEO_MOVEMENTS(视频运镜)
- 函数:`findBestPreset({style, scene, lighting, camera})` 智能降级匹配(精确 → style+scene → style only)
- UI:在 `ai-build.js` 用 `buildArchChipBar(promptTa)`(4 维 chip),用户点 1 个 chip → 自动匹配预设 + 1 键写入 prompt
- 视频节点同理:在 `ai-video-panel.js` 用 `buildVideoChipBar(promptTa)`,加 VIDEO_MOVEMENTS 维度
- 模板下拉自动加"🏛 建筑外观 (N)"分类(在 buildTemplateBar 的 _refreshOptions 末尾)
- chat 技能加 `list_arch_presets` / `use_arch_preset`,让 chat 里 LLM 也能调

### 加一个 AI 节点 prompt 优化功能(2026-08-05 v3.5.22 起)
- 后端:在 `server/handlers/optimize_prompt.py` 加 handler,LLM 生成 `{cn, en, negative_cn, negative_en}` 4 段
- 前端:在 `ai-build.js` actions 行加"✨ 优化"按钮(调新模块 `ai-optimize.js` 弹对比窗)
- 前端:在 `ai-build.js` actions 行加"📜 历史"按钮(显示 `node.prompt_history` FIFO 5 版,一键回滚)
- 数据:`node.prompt` 存中文(默认),`node.prompt_en` 存英文,`node.prompt_history: []` 存 string 数组(FIFO 5 版)
- LLM 走现有 `_llm_config.json`(M3 reasoning),JSON 解析兜底用 `_extract_json(text)` regex
- LLM 调用要直连:**`urllib.request.ProxyHandler({})` + `build_opener()`** 绕开系统 HTTP_PROXY(本机 127.0.0.1:21081 阻断 urllib,PowerShell 走 .NET 不受影响)
- chat 技能加 `optimize_ai_node_prompt` / `rollback_ai_node_prompt`,让 chat 里 LLM 也能调(需 OpenAI function-calling 协议,DeepSeek / Kimi / GLM-4,M3 不支持)

### 加一个聊天技能(skill · 2026-07-27 起)
LLM 在 chat 面板里可以调技能动手改画布。**前提:所用 LLM 必须支持 OpenAI function-calling 协议**(M3 / Mavis CLI 不支持,要切 DeepSeek / Kimi / GLM-4)

1. 在 `client/js/modules/chat-skills/` 写 `skill-<名字>.js`:
   ```js
   import { register, getContext } from './registry.js';
   register({
     name: 'my_skill',                  // snake_case,跟 description/parameters 一起给 LLM 看
     description: '当用户...时调用,做什么',  // 决定 LLM 何时触发
     parameters: { type: 'object', properties: {...}, required: [...] },
     executor: async (args) => {          // args 是 LLM 解析后的对象
       const ctx = getContext();          // { nodes, camera, bus, dom, screenToWorld }
       // ... 干活
       return { ok: true, ... };          // 返回值会进 history 当 tool result
     },
   });
   ```
2. 在 `client/js/modules/chat-skills/index.js` 的 `_skillModules` 数组里 import + 追加
3. 完工 — 启动后 chat 面板会发 `schemas()` 给 LLM,LLM 觉得该用就会调
4. 调试:浏览器 Console 看 `[chat-skills] 加载完成 · 共 N 个技能`

执行器里可用的 ctx:
- `ctx.nodes` — Map<id, node>,直接 set/delete/改字段
- `ctx.camera` — 当前视口 {x, y, zoom}
- `ctx.bus.emit('canvas:dirty')` — 通知画布重绘
- `ctx.dom.canvasArea` — canvas-area DOM(用来算屏幕中心)
- `ctx.screenToWorld(sx, sy)` — 屏幕→世界坐标

### 加一个节点连接线(2026-08-05 v3.5.35 起 · 极简)
- **数据**:`connections: [{ from, to }]` 在 `core/state.js`,`addConnection` / `removeConnection` 操作
- **画**:`canvas-nodes.js` `drawConnections(ctx)` — 1px 贝塞尔曲线,默认 30% 蓝色 opacity,无箭头
- **hover/select 状态**:模块级 `_hoveredConn` / `_selectedConn`(canvas-nodes 导出 set/get)
- **端点拖动重指**:`canvas-board.js` `initConnInteract` → mousedown on endpoint → 拖到目标节点 → `removeConnection` + `addConnection`
- **命中**:`canvas-nodes.js` `hitConnection(sx, sy)` — 端点 8px 阈值 / 线 6px 阈值,贝塞尔 20 段采样
- **快捷键**:Ctrl+L(选 2 节点创建)· 端口拖拽(从 output 拖到 input)· 端点拖动 · 右键线删
- **极简原则**:`0.3 → 0.85` opacity 切换,hover 才画箭头 + 端点圆点,避免画布噪音

---

## 5. 调试

### 后端
```powershell
# 前台启动(看实时日志)
cd _v25
python -X utf8 -u -m server
```

### 前端
- 浏览器 DevTools → Console / Network
- 0 缓存已经开了,但要硬刷新一次(Ctrl+Shift+R)
- 检查 `bus.emit` 的事件名拼写

### API 单点测试
```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:9002/api/canvases" -UseBasicParsing | Select-Object -ExpandProperty Content
```

---

## 6. 不在 v3.0 范围(留 v2.6+)

- ❌ 小地图(minimap 删了)
- ❌ 文字便签的双击浮层编辑
- ❌ 区域框的 resize 角
- ✅ **节点连接线 + 端点拖动 + 右键删** (v3.5.35 落实:1px 极简线 / hover 高亮 / 端点拖动重指 / 右键删 · 详见 §4「加一个节点连接线」)
- ✅ **节点批量操作(6 维对齐 + 改色 + 排列)** (v3.5.37 落实:浮动栏 / 254 行)
- ✅ **画布级历史时间线** (2026-07-28 v2.x 早已实装:auto-save + 时间线 + diff 对比 + 恢复/删除 · 详见 `server/handlers/canvas_history.py` + `client/js/modules/canvas-history.js`)
- ❌ 节点打组 / 解组(按钮占位 `toast('v2.6 实现')`)
- ❌ 右键菜单
- ❌ 调色板的精确颜色提取(简化成 4 角采样)
- ❌ 以图找图(后端有,前端没接)

---

## 7. 数据 / 备份

| 文件 | 来源 | 备份策略 |
|---|---|---|
| `canvas_state.db` | v3.0 独立(数字 ID) | 用户手动 `cp` 到 `*.bak` |
| `favorites.json` | seed 自 v1 | v1 是真源 |
| `_llm_config.json` | seed 自 v1 | v1 是真源,API Key 不复制 |
| `PictureDb/PictureDb.db` | 兄弟模块共享 | 不动 |
| `Input/YYYY-MM-DD/` | 上传归档 | 不动 |
| `Output/YYYY-MM-DD/` | AI 生图归档 | 不动 |

> 任何"数据丢失"问题:**v1/v2 已退役, 9002 是唯一事实源**(2026-08-14 关 v2)。

---

## 8. 不要做的事(反约束)

- ❌ 引入 npm 依赖(React / Vue / Tailwind 等)
- ❌ 用 `pip install`(项目零依赖是核心竞争力)
- ❌ 把 `canvas_state.db` 改用 MySQL / Postgres(过度设计)
- ❌ 把 v1(8082)代码删了(留对照,回滚用)
- ❌ 改 API 路径或删字段(破坏 v1 兼容)
- ❌ 用 jQuery / Lodash(原生 ES6+ 够用)
- ❌ 在 commit message 写 AI 提示词(丢人)

---

> 变更记录
> - 2026-08-17 · v3.5.53 · patch · **3 修(夜间迭代 R365)**:thumbs 异常收集 logs/thumb_errors.json + _thumbs_health.py 全量扫描工具 / 文档数字漂移治理(handler 22→26,module 99→96 真实数 + _gen_structure.py --check-doc-drift 守卫) / _smoke.py 启动前 syntax precheck 防 connection refused 误导
> - 2026-08-14 · v3.5.52 · minor · **工程质量 5 大改造**(全主动 vs 之前被动修 bug)
>   - **C. 中心化 timeout 常量**
>     - `client/js/core/constants.js` 新建(60 行):TIMEOUTS / LIMITS / COLORS 三个表
>     - `server/config.py` 加 TIMEOUTS dict(LLM_CALL_MS=90 / MATRIX_RETRY=3 / ...)
>     - `api.js` `llmCall` 默认 timeout 用 `TIMEOUTS.LLM_CALL_MS`
>     - `chat-context.js` 用 `TIMEOUTS.IMG_DATAURL_MS` / `LIMITS.CHAT_IMG_SIZE`
>     - `llm.py` urllib timeout 用 `TIMEOUTS['LLM_CALL_MS']`
>   - **A. 加单元测试**(从 0 → 60+)
>     - `tests/test_state_addConnection.mjs` · 9 个 case(addConnection 去重 / type 字段 / 环检测标记)
>     - `tests/test_state_newNodeId.mjs` · 5 个 case(唯一性 / 1000 次不撞)
>     - `tests/test_ai_video_resolve.py` · 12 个 case(/upload / /img / http / 不存在)
>     - `tests/test_matrix_upload.py` · 11 个 case(mime 推断 / 中文文件名 sanitize)
>     - `tests/test_skill_danger.mjs` · 6 个 case(danger 注册 / askUserConfirm 5s 超时)
>     - `_run_tests.py` 统一 runner(Python + Node)
>   - **B. 拆 state.js god object**(零破坏)
>     - 4 个子模块:`nodes-state.js` / `canvas-state.js` / `ui-state.js` / `cache-state.js`
>     - `state.js` 改为 re-export 兼容层(老代码 import 继续工作,ESM live binding 同步)
>     - aiStylesCache 用 `export let` 活绑定(老代码直接 import 读也跟着更新)
>   - **D. skill 危险操作加"用户确认"**
>     - `chat-skills/registry.js` 加 `danger` 字段 + `confirmMsg(args)` 提示生成器
>     - 新 API `askUserConfirm(skillName, args)`(5s 超时自动通过,弹 approve/reject)
>     - `chat-runtime.js` 跑 skill 前检查 danger,等确认
>     - `skill-delete-node.js` 标 danger=true 作为示范("AI 想删 N 个节点")
>     - 后续可标:add-text / update-node / arrange-layout / link-to / extract-anchor
>   - **E. 关 v2 (8083)**
>     - 8082 v1 / 8083 v2 本来就没在跑(只有 9002 v3)
>     - AGENTS.md 端口表改"已退役"标注
>     - 数据丢失应急指南改"v3 是唯一事实源"
>   - **测试结果**: Python 46 + Node 20 = 66 tests, 0 failed · smoke 17/17 OK
>   - bump 3.5.51 → 3.5.52
> - 2026-08-14 · v3.5.51 · patch · **修 AI 设计助手 卡在"思考中"不回复**
>   - **根因**:`client/js/modules/chat-context.js` 的 `_srcToDataUrl` 有递归 bug
>     - 当画布上 image/ai 节点的 src 是 `/upload/...` 路径时, fetch + FileReader 链尾**没人 resolve 外层 Promise**
>     - `getCanvasImages()` await 永远挂住 → chat LLM 调用永远进不去 → "AI 思考中..." 锁死
>     - 画布有图时 100% 触发, 没图时正常(M3 reasoning 慢也是表象)
>   - **修法**:
>     - `_srcToDataUrl` 整段重写:data: 走 canvas 缩放直接 resolve, /upload 走 fetch+FileReader 读完后调 `_scaleDataUrl` 再 resolve,不再递归
>     - 加 8s timeout 兜底(单图转 dataURL 8s 还没好就返 null,让 chat 走纯文字)
>     - `_scaleDataUrl` 单独抽,5s timeout,处理 data: → 缩放
>   - **附带**:`chat-runtime.js` 加 elapsed time 显示(`AI 思考中… X秒 · Ctrl+Enter 重发`)
>   - **附带**:`api.js` `llmCall` 加 AbortController 60s 兜底(原 fetch 无 timeout,可能无限等)
>   - **附带**:`chat-runtime.js` catch 块加 AbortError 友好提示("LLM 超时 Xs · 切到快模型试试")
>   - **附带**:`server/handlers/llm.py` urllib timeout 120s → 90s(避免前端 abort 后服务端空转)
>   - smoke 17/17 OK
>   - bump 3.5.50 → 3.5.51
> - 2026-08-13 · v3.5.50 · patch · **修 AI 节点 → 视频节点 参考图传递失效**
>   - **根因 #1**:`ai_video.py` 只解析 `/img/...` `/img/thumbs/...` 路径,没解析 `/upload/...` 路径
>     - AI 节点 resultSrc 是 `/upload/Output/.../*.png`(走 local_to_upload_url)· 后端拿不到 → `input_image=None` → 静默降级 text-to-video
>     - 张勇反馈"图片AI 无法把内容传递给视频节点"就是这条
>   - **根因 #2**:`ai_video.py` 调用 `matrix_client.generate_video` 只传 `input_image_url=...`, 漏了 `input_image_path`
>     - 本地 file 没走 `_matrix_upload.upload_file` 上 OSS 拿 CDN URL,直接被丢(降级)
>     - 同样 ai_image.py 早用 `input_file_paths` 走 upload_file,ai_video.py 漏
>   - **根因 #3**:`_matrix_api.py:generate_video` 把 `input_image` 设成字符串 URL,但 matrix 后端期望 `MediaInfo` 对象
>     - matrix 报 `400: invalid request: bind body failed, err=Mismatch type mcp_service.MediaInfo with value string`
>   - **修法**:
>     - `ai_video.py` 加 `/upload/...` 解析(走 BASE_DIR),文件不在时打 log 提示
>     - `ai_video.py` 改传 `input_image_path=...`,让 matrix_client.upload_file 走 OSS
>     - `_matrix_api.py:generate_video` 把 input_image 包成 `{'type': 'image', 'url': input_image_url}` MediaInfo 对象
>   - **附带**:`ai-video-panel.js` `addAIVideoNode` 加显式注释"绝不连任何节点"+ `console.log`
>   - **附带**:refPreview 加 ref-type-badge(橙色 file / 蓝色 url / 红色 none)· 用户在画布上一眼看到 ref 是什么类型
>   - **附带**:`board.css` 加 `.ref-type-badge` 样式 + `.ref-label` 改名布局
>   - **验证**:`/api/ai_video` POST 测 → 走 upload_file → matrix 不再 400 错(SSL 错跟代码无关,等矩阵后端恢复)
>   - smoke 17/17 OK
>   - bump 3.5.49 → 3.5.50
> - 2026-08-12 · v3.5.49 · patch · **修本机保存画布 401 失败**
>   - **根因**:2026-08-11 R223 P0 改三段 dispatch,`/api/canvas` 进了 AUTH_PREFIXES 强制 Bearer token
>   - **症状**:画布显示 "保存失败" · `POST /api/canvas/X` 返 `{"error": "需要登录"}`
>   - **修法**: `_check_post` 开头加本机 admin IP 豁免(canvasweb 历来单用户本机工具,无需登录)
>   - 局域网用户仍走 ADMIN/AUTH 校验,跟 R223 多用户意图不冲突
>   - smoke 17/17 OK
>   - bump 3.5.48 → 3.5.49
> - 2026-08-07 · v3.5.48 · minor · **真做 D-013/014/015 三个 auto-dev issues** · close #79/80/81
>   - **D-013 报错自动上报** (`client/js/modules/feedback.js` 升级 + `board-main.js` init)
>     - 端点从 `/api/feedback` 改 `/api/feedback_arch`(后端 v3.5.41 已实装,直接推 GitHub + Gitee 双平台 issues)
>     - 监听 `window.onerror` + `unhandledrejection` · sendBeacon 优先 + fetch keepalive 兜底
>     - 5min 同类错误去重(`_dedup` Map,key = kind+message)· 批量错误(5s 内或 10 条满)合并成 1 个 issue · 队列上限 100
>     - issue title: `[auto-error] {kind} x{N}: {首错 message}` · labels: `auto-error, bug, frontend`
>     - `client/js/board-main.js` `DOMContentLoaded` 加 `feedback.init()`(之前没人调,模块定义但没接入)
>   - **D-014 文档补齐** (`docs/api_contract.md` 加 2 段)
>     - §4 末尾加 "画布版本快照" 段:`GET /api/canvas_history` 列 · `GET /api/canvas_history/{cid}/{ts}` 拿单份 · `POST /api/canvas_history` save/restore/delete · 写入策略 .tmp 原子写 + 保留最近 20
>     - §6 加 `/api/feedback_arch` 3 端点(create/list/daily)详情 · 24h 缓存 + Gitee 镜像路径踩坑说明
>   - **D-015 大图懒加载** (早就实装在 `canvas-nodes.js` 480-485 + `canvas-list.js` `_loadImg`/`loadImageIfInViewport` · 2026-07-28 写的,只是没在 docs 标注)
>     - `_loadImg` 创建 `new Image()` + 标 `_img_pending=true` + 缓存 `_img_src` · 不立即赋值 src
>     - `drawAllNodes` 每帧检测:`_img_pending && _img_src` 时才 `n._img.src = n._img_src` 触发加载
>     - 视口外节点延迟到 `loadImageIfInViewport` 检测,缩远/拖动后再触发
>     - onload/onerror 设 `_img_pending=false` + 触发 `canvas:redraw` 重画
>   - **附:清理 4 个旧备份**
>     - 删 `.CanvasWebAutoEvolution/.CanvasWebFrame-*.xlsx` 2 个(老目录已重命名 `.AutoEvolution/`,旧的全量版无意义)
>     - 删 `.Plan/2026-08-06-*.{md,xlsx}` 4 个(已被 `.AutoEvolution/` 取代)
>     - 删 `server/handlers/ai_image.py.bak-2026-07-14` / `ai_video.py.bak-2026-07-14` (7 月备份,主源已迭代 23 版)
>   - **核心教训**:v3.5.47 close 误操作复盘 — close 之前**必须 verify 代码**,不能凭"看起来差不多"就 close;真做才能 close
>   - bump 3.5.47 → 3.5.48
> - 2026-08-07 · v3.5.47 · patch · **close open issues + _fetch_issues.py 工具**
>   - GitHub issues 状态:close #79/80/81(D-013/014/015 三个 auto-dev 任务)
>   - 当前 0 open issues
>   - 加 `_fetch_issues.py` · 拉 GitHub issues 备份到 `logs/github-issues-latest.json`
>   - 默认拉所有(open + closed),按 label 统计 top 5
>   - bump 3.5.46 → 3.5.47
> - 2026-08-07 · v3.5.46 · patch · **FAB 修:FAB 移 body 末尾 + inline style 兜底 + CSS/JS no-cache**
>   - FAB 移出 `.canvas-area`(避免父元素 overflow: hidden 潜在裁剪)
>   - inline style 兜底(即使 CSS 类未生效,FAB 也显示)
>   - `server/core.py` 扩展:HTML/CSS/JS 全部 `no-store, no-cache`(避免浏览器硬缓存)
>   - 位置:`bottom: 96px; right: 24px`(从 80px 微调,避开状态栏)
>   - 颜色:`#ff9e4a`(`--accent` 默认)
>   - z-index: `9999`
>   - bump 3.5.45 → 3.5.46
> - 2026-08-07 · v3.5.45 · minor · **右下角问题反馈浮动按钮**
>   - `board.html` 加 `<button id="fb-issues-fab" class="fab-issues">`(右下角圆形 FAB · position: fixed)
>   - `board.css` 加 `.fab-issues` 样式(48×48 圆 + 阴影 + hover 缩放 1.08)
>   - `issues-panel.js` init 绑定 `fb-issues-fab` 点击 → 弹"新建"tab
>   - 反馈直接走 `/api/feedback_arch` → GitHub + Gitee 双平台 issues
>   - 顶部工具栏 `cb-issues` 按钮保留(可访问 3 tab:每日摘要/全部/新建)
>   - bump 3.5.44 → 3.5.45
> - 2026-08-07 · v3.5.44 · minor · **画布间复制粘贴 + 空白画布清理**
>   - 画布间复制:`client/js/modules/canvas-paste-to.js` (新模块 · 104 行) · `clipboard.js` 加 `getClipboard()` 导出 + `bus.emit('clipboard:changed')` · 画布顶部新增 `📋 粘贴到 (N)` 按钮(Ctrl+C 后出现,点击弹画布列表 popover,选目标画布一键粘贴) · 解决"画布间无法复制节点"痛点
>   - 空白画布清理:`canvas_state.db` 删除 74 个空白画布(71 个 `__smoke_test_canvas__` 测试残留 + 3 个真空白) · 软删(`is_deleted=1`),可恢复
>   - bump 3.5.43 → 3.5.44
> - 2026-08-06 · v3.5.43 · minor · **Excel 主源路线 + GitHub Issues 自动同步** · 飞书通道 opt-in
>   - 加 `_excel_to_github.py` (~280 行 · 零依赖 zipfile 读 xlsx + urllib 推 GitHub · 幂等: title 前缀 `[M1-001]` 唯一,重跑不重复) · `--push` / `--filter M1` / `--only-todo` 参数
>   - 加 `_xlsx_set_status.py` (~250 行 · 改 xlsx 任务状态列 · 兼容 inline strings / shared strings · Windows 用 in-memory BytesIO 写绕过 WPS 文件锁) · `--list` 看全部任务
>   - **飞书通道 opt-in**: `_feishu_init.py` / `_feishu_sync.py` / `_feishu_daily.py` 脚本保留但不默认启用(Excel 更轻,飞书需企业自建 app 审批,过度设计) · 配置指南 `.Plan/2026-08-06-飞书通道-配置指南.md` 留作以后启用
>   - 推送 **66 任务 → GitHub issues** 一次完成 · M1-003 (canvas-fit.js) state=closed(v3.5.40.3 已加) · 重跑幂等:0 创建 / 0 关闭 / 0 重开 / 66 跳过
> - 2026-08-06 · v3.5.42 · minor · 加 Issues 反馈前端 UI(画布底部 🐛 按钮 + 弹窗 3 tab:每日摘要/全部/+新建) · 修复 v3.5.41 后端加但前端没 UI 的问题
> - 2026-08-06 · v3.5.41 · minor · 加 issues 反馈模块 `/api/feedback_arch` (create/list/daily) · 并行创建 GitHub + Gitee 双平台 issue · 24h 缓存去重 · Gitee POST path 不带 {repo} 踩坑已注释
> - 2026-08-06 · v3.5.40.5 · doc · 加 `01_开发纪要-错误总结与避坑指南.md`(30+ 错误复盘 + 防御 + 通用方法论) + AGENTS.md §1 改前必读第 1 条指向它
> - 2026-08-06 · v3.5.40.4 · hotfix · 修 AI 节点浮层 panel 全不显示(根因: v3.5.33 加 rerunQueueStrip 时把 isChild 用在声明前 · const TDZ 报错 → build() throw → syncAll 里整条 build 失败 · Chrome headless 抓到 `[bus] handler for "canvas:redraw" threw: Cannot access 'isChild' before initialization`)
> - 2026-08-06 · v3.5.40.3 · hotfix · 修图片/AI 节点看不见(根因: camera zoom 缩太小 · 加 canvas-fit.js 自动 fit-to-view · #cb-reset + 点击 zoom 改绑 fitToView · 加载画布时防御性检测 camera)
> - 2026-08-05 · v3.5.40 · minor · 4 合一波(doc sync + 连接线增强 + chat 导出 MD + 节点缩放/旋转)
> - 2026-08-05 · v3.5.39 · minor · 4 合一波(代码卫生 + 导出 PNG + chat 持久化)
> - 2026-08-05 · v3.5.38 · patch · 文档同步(AGENTS.md 补 v3.5.22-37 · 模块数 60+ → 95 · 警戒列表更新)
> - 2026-08-05 · v3.5.37 · minor · 节点批量操作(浮动栏 + 6 维对齐 + 横/竖排 + 批量改色 · bulk-actions.js 254 行 · AGENTS.md §6 ❌→✅)
> - 2026-08-05 · v3.5.36 · minor · 节点备注/说明(n.desc 字段 + 画布右上角 📝 徽章 + AI 浮层 📝 按钮 + desc-edit.js 跟 name-edit.js 平行)
> - 2026-08-05 · v3.5.35 · minor · 迷你连接线(1px 极简 + 端点拖动重指 + 右键删 · AGENTS.md §6 ❌→✅)
> - 2026-08-05 · v3.5.34 · minor · 节点 name 标签双击改名(name-edit.js,123 行,跟 text-edit.js 平行)
> - 2026-08-05 · v3.5.33 · minor · AI 节点重跑队列(🔁×3 并行 + 侧栏 10 张可点回主图)
> - 2026-08-05 · v3.5.32 · minor · 快捷键补缺(方向键 nudge / F2 改名 / Esc 取消 / ? 帮助弹窗)
> - 2026-08-05 · v3.5.31 · patch · 预设/模板下拉加搜索框(filter <option> + optgroup auto-hide + Escape 清空)
> - 2026-08-05 · v3.5.30 · minor · 节点对齐辅助线(Figma 风格 5 维 snap + 橙色虚线)
> - 2026-08-05 · v3.5.29 · patch · 文档同步(AGENTS.md + api_contract.md 补 v3.5.22-28)
> - 2026-08-05 · v3.5.28 · patch · 去掉 AI 节点画布占位矩形(`drawAINodePlaceholder` 跟浮层 panel 视觉错位)
> - 2026-08-05 · v3.5.27 · patch · 去掉 AI 节点选中时 panel 自身橙色/绿色 border + box-shadow 辉光
> - 2026-08-05 · v3.5.26 · patch · 修 AI 节点选中时橙色外框跟 panel border 错位 2px bug
> - 2026-08-05 · v3.5.25 · patch · 模板下拉 + chip bar 改 <details> 默认折叠(节省垂直空间)
> - 2026-08-05 · v3.5.24 · minor · 建筑外观视频预设库(15 条 · 4 维 chip · 复用生图数据)
> - 2026-08-05 · v3.5.23 · minor · 建筑外观 prompt 预设库(34 条 · 4 维 chip)
> - 2026-08-05 · v3.5.22 · minor · AI 节点 prompt 优化(中/英/反向词 4 段 + 历史回滚)
> - 2026-07-28 · 代码评审响应:3 个 P0 修复(events 孤儿 / admin 闸门 / 右键删除) + 2 个 P1(is_deleted 软删 / FTS 参数化) + config.py 硬编码改 env + AGENTS.md 行数同步
> - 2026-07-27 · 跨画布全局搜索从顶栏挪到底部居中(v3.1.7)
> - 2026-07-27 · 移除顶栏快捷键提示文字(v3.1.8)
> - 2026-07-27 · 复活右侧 AI 设计助手聊天面板(chat-panel.js) + 拆出 chat-runtime.js
> - 2026-07-27 · 加聊天技能系统(chat-skills/)— OpenAI function-calling 协议,LLM 调技能改画布
> - 2026-07-27 · 加右侧悬浮折叠按钮(chat-toggle-btn)
> - 2026-07-08 · v3.0 重构完成 · 后端 15 模块 + 前端 18 模块 + 3 CSS · arch2
