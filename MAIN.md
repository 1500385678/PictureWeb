# MAIN.md · 主程序 vs 支程序 · 边界声明

> **改之前先看这个**。明确告诉你哪些是"系统骨架"(改要谨慎),哪些是"业务模块"(可独立替换)。

---

## 0. 核心原则

**主程序 = 改之前要三思。**
**支程序 = 可独立替换 / 删 / 改,不影响主程序。**

判断标准:**改它会不会让整个项目"启动不起来"或"路由错乱"?**
- ✅ 会 → 主程序
- ❌ 不会 → 支程序

---

## 1. 主程序(改之前三思)

> **本节文件清单为骨架层**(后端 6 + 前端 6 + 主核心 2 = 14 骨架文件),改之前必看。
> 完整文件列表 + 权威清单见 **AGENTS.md §2**,**加新文件必须同步 AGENTS.md**(单一事实源 · 2026-08-10 v3.5.48 落实)。

### 后端骨架 · 6 文件(2026-08-10 复核 = 6)
- `server/__init__.py` · v3.0.0 包标识 + `__version__`
- `server/__main__.py` · 启动入口 + 路由分发(所有请求第一站)
- `server/config.py` · 路径 / 端口 / 权限 / 并发(改 → 同步 `_daemon.py` + `api_contract.md`)
- `server/core.py` · BaseHandler 基类(所有 handler 继承)
- `server/routes.py` · 路由表(加/移端点改这里)
- `server/img.py` · /img/ /upload/ 静态服务

> 命令复核:`ls server/{__init__,__main__,config,core,routes,img}.py | wc -l` = 6

### 前端骨架 · 6 文件(2026-08-10 复核 = 6)
- `client/index.html` · 主页入口 HTML
- `client/board.html` · 画布页入口 HTML
- `client/js/main.js` · 主页入口(import 所有 module + 启动)
- `client/js/board-main.js` · 画布页入口
- `client/js/api.js` · 所有 /api/* 调用封装(单一事实源)
- `client/js/core/state.js` · 全局状态(相机 / 节点 / 选中 / 过滤)

> 命令复核:`ls client/{index,board}.html client/js/{main,board-main,api}.js client/js/core/state.js | wc -l` = 6

### 主核心 · 2 文件(2026-08-10 复核 = 2,旧文档写 4 过期)
- `client/js/core/dom.js` · DOM 工具 / toast(很多 module 依赖)
- `client/js/core/events.js` · 事件总线(模块间通信,改名字影响所有 on/off)

> 命令复核:`ls client/js/core/ | wc -l` = 3(含 state.js · 算 1 个主核心)→ **核心 2 + state = 3**

---

## 2. 支程序(可独立替换 · 大胆改)

> **本节权威清单**见 **AGENTS.md §2**,**本节仅描述边界 + 命令验证**。
> 2026-08-17 v3.5.53 实测:**后端 26 个 handler · 前端 96 个 module(77 顶层 + 19 chat-skills)**

### 后端业务端点(2026-08-17 v3.5.53 复核 = 26 个)
> **删了某个** → 那个功能消失,其它不受影响
> **加新文件** → 在 `routes.py` 注册一下就行
>
> 命令复核:
> ```bash
> ls server/handlers/*.py | grep -v __init__ | wc -l   # = 22
> ls server/handlers/   # 详细 24 项(22 handler + __init__ + __pycache__)
> ```
>
> 完整清单见 AGENTS.md §2 后端 handlers/ · 含 ai_image / canvas / canvas_history / chat_state / db / export_pdf / favorites / feedback / feedback_arch / image2text / llm / music / optimize_prompt / prompt_templates / search / semantic / sketchup_import / tts / upload / users / ai_video / ai_inpaint

### 前端业务模块(2026-08-10 复核 = 99 个 = 79 顶层 + 20 chat-skills)
> **删了某个** → 主入口 `main.js` / `board-main.js` 里的 `import` 删一行 + `init()` 删一行
> **加新模块** → 写新文件 → `main.js` / `board-main.js` 加 import + init
>
> 命令复核:
> ```bash
> ls client/js/modules/*.js | grep -v "\.bak" | wc -l   # = 79
> ls client/js/modules/chat-skills/   # = 20(registry + index + 18 skill)
> ```
>
> 完整清单见 AGENTS.md §2 前端 modules/ · 含 canvas-board / canvas-nodes / canvas-list / ai-build(4 拆) / ai-optimize / ai-arch-presets / ai-video-presets / bulk-actions / canvas-paste-to / issues-panel / canvas-fit / name-edit / desc-edit / chat-skills/* 等 99 个

### 样式 · 3 文件(2026-08-10 复核 = 3)
- `client/css/common.css` · 基础布局
- `client/css/panel.css` · 弹窗 / 浮层
- `client/css/board.css` · 画布节点

---

## 3. 辅助(改了不影响功能)

> 2026-08-10 实测数字(命令复核):
> - `docs/`: **10 份文档**(`ls docs/*.md docs/*.html | wc -l`)
> - `tests/`: **11 个文件**(`ls tests/*.py | wc -l`)
> - `scripts/`: **6 个文件**(`ls scripts/* | grep -v "\.err\|\.out" | wc -l`)
> - 根 `_*.py`: **14 个工具脚本**(`ls _*.py | wc -l`)

---

## 4. 模块依赖图(简化 · 2026-08-10 复核)

> 模块数量走命令,详情见 AGENTS.md §2

```
main.js  ─┬─→  api.js  ──→  /api/* (后端 · 22 handler)
          ├─→  core/state.js  ← 共享状态
          ├─→  core/dom.js    ← DOM 工具
          ├─→  core/events.js ← 事件总线
          └─→  modules/*  (99 个支程序模块 = 79 顶层 + 20 chat-skills)

server/__main__.py  ─┬─→  routes.py  ──→  handlers/* (22 支程序)
                     ├─→  config.py  ──→  所有模块
                     ├─→  core.py    ← BaseHandler
                     └─→  img.py     ← 静态服务
```

> 数量复核命令:
> ```bash
> ls server/handlers/*.py | grep -v __init__ | wc -l   # = 22
> ls client/js/modules/*.js | grep -v "\.bak" | wc -l   # = 79
> ls client/js/modules/chat-skills/   # = 20
> ```

**关键事实:**
- 主程序**不直接调用支程序的具体实现**,只通过 routes / import 间接
- 支程序**只能依赖主程序**(api.js / state.js / dom.js / events.js),不能反向
- 支程序之间**通过 events.js 通信**,不直接 import(避免循环)

---

## 5. 改前 1 句话自检

| 我想改... | 这是主/支? | 我要做 |
|---|---|---|
| 加一个 API 端点 | 支(handlers) | 写新 handler → `routes.py` 注册 → `docs/api_contract.md` 同步 |
| 加一个 UI 模块 | 支(modules) | 写新 module → `main.js` import + init |
| 改端口 / 路径 / 权限 | **主** | 改 `config.py` → 同步 `_daemon.py` + `docs/api_contract.md` |
| 改 BaseHandler | **主** | 改 `core.py` → 检查所有 handler 是否仍兼容 |
| 改事件名 | **主** | 改 `events.js` → grep `bus.on('xxx:')` 找全所有监听者 |
| 改全局状态结构 | **主** | 改 `state.js` → 找全所有 import 它的地方 |
| 调样式 | 支(css) | 改对应 `client/css/<x>.css` |
| 调某个节点的画法 | 支(canvas-nodes) | 改 `canvas-nodes.js` 的对应 `drawXxxNode` |
| 调画布交互 | 支(canvas-board) | 改 `canvas-board.js` 的对应函数 |

---

> 变更记录
> - 2026-07-08 · 初版 · 基于 v3.0 文件整理总结 · arch2
