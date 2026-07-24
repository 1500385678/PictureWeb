# PictureWeb

> 独立的图库检索系统。多维标签 + 全文搜索 + AI 语义搜 + 以图搜图。
> 端口 **8081** · Python 标准库 + Pillow · 零 npm 依赖。

## 启动

```bash
# Windows
python -X utf8 server.py
# 或
双击 start.bat
```

打开 **http://127.0.0.1:8081/**

## 功能

- 🔍 多维标签检索(project / scene / light / space / material / mood / arch / company / view)
- ⚡ FTS5 全文搜索(中文 2-gram 分词)
- 🤖 AI 语义搜索(需 `embedding.py` 兄弟模块)
- 🖼️ 以图搜图(PIL pHash)
- ⭐ 收藏夹

## 依赖

- Python 3.10+ 标准库
- `Pillow`(phash 计算)· `pip install Pillow`
- 共用 `_ArchitectLib/PictureDb/PictureDb.db`(兄弟模块,不动)
- 图片根 `D:\Mac\Mac\workteam\05_space\03_architect\Mobile`

## API

| Method | Path | 权限 | 说明 |
|--------|------|------|------|
| GET | `/api/search?` | 公开 | 多维搜索 |
| GET | `/api/facets` | 公开 | 9 维标签去重值 |
| GET | `/api/favorites` | 公开 | 收藏列表 |
| POST | `/api/favorites` | 本机 | 切换收藏 |
| GET | `/api/semantic_search?q=` | 公开 | AI 语义搜(GET 方式) |
| POST | `/api/semantic_search` | 本机 | AI 语义搜(POST 方式) |
| POST | `/api/upload_search` | 本机 | 以图搜图 |
| POST | `/api/ai_image` | 本机 | AI 生图(matrix MCP) |
| POST | `/api/intent_search` | 本机 | **v2.0.6** AI 找参考(自然语言设计意图 → top 5 案例 + reasons 解释) |
| GET | `/img/<相对路径>` | 公开 | 图片直出 |

> 权限"本机"=`127.0.0.1` / `192.168.181.136` / `::1`,见 `server.py:ADMIN_IPS`

## 目录

```
PictureWeb/
├── server.py            # 后端(约 420 行 · 单文件)
├── index.html           # 搜索主页(CSS+JS 内嵌)
├── start.bat            # Windows 启动
├── start.sh             # macOS/Linux 启动
├── start_hidden.vbs     # 无窗口启动(2026-07-22 v2.0.3:加错误处理+日志)
├── libraryControl.md    # 旧 control 文件
├── LICENSE              # 许可证
├── favorites.json       # 收藏(运行时,gitignore)
├── thumbs/              # 缩略图(运行时,gitignore)
└── server.out/err       # 日志(运行时,gitignore)
```

## 变更记录

| 日期 | 变更 | 触发 |
|------|------|------|
| 2026-07-24 | minor → v2.0.6 + AI 找参考(POST /api/intent_search · 自然语言设计意图 → top 5 案例 + reasons 解释)+ 生图变体(复用 /api/ai_image 调 matrix MCP)+ 苹果风 UI(header 单行紧凑 / 浅色 / 磨砂玻璃 / pill→rect)+ select 简化为中文标签 | 从"图库"升级为"设计助理" |
| 2026-07-22 | patch → v2.0.5 + 仓库改 private + start_hidden.vbs 加 PICTUREWEB_TEST_PORT=9001 dev 模式 + git_data_push.py/auto_release.py 默认 REPO 改新仓库 + AGENTS.md §1 改 private | 收尾 v2.0.4 残留 + 修老仓库误推风险 + 开机自启(Startup 快捷方式)|
| 2026-07-22 | patch → v2.0.4 + git_data_push.py / auto_release.py 加 Windows 用户级环境变量 fallback + 修 origin/local sha 错位 + README 改 port 说明 | mavis bash tool 不读 HKCU\Environment,token 持久化补丁 |
| 2026-07-22 | patch → v2.0.3 + server.py 端口回归 8081(PICTUREWEB_TEST_PORT env 覆盖)+ start_hidden.vbs 加错误处理+日志 | 修端口 regression + Issue #1 收尾 |
| 2026-07-22 | patch → v2.0.2 + server.py load_favs/save_favs 用 with 块 + 改 except 类型 | 修小问题 |
| 2026-07-22 | 重大升级 → v2.0.0 + daily_pipeline 端口/日志/环境变量重构 | 用户手动指定 |
| 2026-07-21 | git init + .gitignore + README(本文件) | 接入 3-agent 流水线试点 |
| 2026-06-27 | 创建 libraryControl 文件 | 初版 |


## 验收日志

- 2026-07-24 · v2.0.6 · minor: AI 找参考(`/api/intent_search` 端点 + 前端"AI 找参考"tab · 自然语言设计意图 → top 5 案例 + reasons 解释); 生图变体(复用 `/api/ai_image` 调 matrix MCP); 苹果风 UI 改造(header 单行紧凑 / 浅色 / 磨砂玻璃 / pill→rect); select 文案简化为中文标签(项目/场景/光线/氛围/类型/公司/视角)
- 2026-07-22 · v2.0.5 · patch: 仓库 visibility public→private, start_hidden.vbs 加 PICTUREWEB_TEST_PORT=9001 env set, git_data_push.py/auto_release.py 默认 REPO 改新仓库(避免老仓库误推), AGENTS.md §1 同步
- 2026-07-22 · v2.0.4 · patch: git_data_push.py / auto_release.py 加 HKCU\Environment fallback(mavis bash tool 自动读 user-scope token)+ origin/local sha 错位修复(force update + squash)
- 2026-07-22 · v2.0.3 · patch: server.py 端口 9001→8081(PICTUREWEB_TEST_PORT env 覆盖), start_hidden.vbs 加 On Error + 写日志, README 修"路径待修"过时描述
- 2026-07-22 · v2.0.2 · patch: server.py load_favs/save_favs 用 with 块, 修 bare except 吞所有异常
- 2026-07-22 · v2.0.0 · 跨 major 升级 + daily_pipeline 端口自适应(8081/9001)+ PICTUREWEB_TEST_PORT 环境变量 + server 启停改用日志文件
- 2026-07-21 · v0.1.0 · 3-Agent 流水线首次跑通(PR #9 + #10)
- 2026-07-21 · Phase 6 自动化骨架完成(feedback / dispatch / tester / release)
