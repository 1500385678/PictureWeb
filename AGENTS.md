# AGENTS.md — PictureWeb 项目真值源

> Agent 必读。本文件描述项目是什么、怎么工作,任何 agent 进项目都先读这一份。

## 0. 项目是什么

**PictureWeb** 是独立图库检索系统。多维标签 + 全文搜索 + AI 语义搜 + 以图搜图。
端口 **8081** · Python 标准库 + Pillow · 零 npm 依赖。

**前身**: `PictureWebWorkflowtest` (仓库 `1500385678/PictureWebWorkflowtest`),v0.1.x ~ v2.0.0 期间作为 **3-Agent 流水线** PoC 验证场。2026-07-22 v2.0.0 拆出,作为正式独立项目运营。

## 1. 关键属性

| 项 | 值 |
|---|---|
| 工作目录 | `D:\Mac\Mac\Mac\workteam\05_space\03_architect\Mobile\_ArchitectMobileLib\PictureWeb\` |
| 远端仓库 | `https://github.com/1500385678/PictureWeb` (private, 2026-07-22 v2.0.5 起) |
| 远端主分支 | `main` |
| 当前版本 | `v2.0.9` (`__version__.py`) |
| DB 根 (v2.0.9) | `D:\Database\Database` (统一抽库,2026-08-27 改;env `PICTUREWEB_DB_ROOT` 可覆盖) |
| 启动命令 | `python -X utf8 server.py` (Windows) 或双击 `start.bat` |
| 默认 URL | http://127.0.0.1:8081/ |
| 共享数据 | `_ArchitectLib/PictureDb/PictureDb.db` (兄弟模块) |
| 图库根 | `D:\Mac\Mac\workteam\05_space\03_architect\Mobile` |
| 缩略图缓存 | `thumbs/` (gitignore) |
| 日志 | `logs/` (gitignore) |
| 历史老仓库 | `1500385678/PictureWebWorkflowtest` (v0.1.x ~ v2.0.0,教学样本) |

## 2. 目录结构

```
PictureWeb/
├── server.py             # 后端(单文件,~430 行)
├── index.html            # 搜索主页(CSS+JS 内嵌)
├── start.bat / start.sh  # 启动脚本
├── start_hidden.vbs      # 无窗口启动(Windows)
├── libraryControl.md     # 旧 control 文件(归档)
├── LICENSE               # 许可证
├── favorites.json        # 收藏(运行时,gitignore)
├── AGENTS.md             # 本文件
├── README.md             # 用户档
├── __version__.py        # 版本号源
├── docs/
│   ├── 3agent-workflow.md  # 3-Agent 流水线手册
│   └── phase6-design.md    # Phase 6 设计
├── scripts/
│   ├── auto_dispatch.py        # 3-Agent: 分发 issue
│   ├── auto_fixer_architect.py # 3-Agent: Architect Fixer
│   ├── auto_tester.py          # 3-Agent: Tester
│   ├── auto_release.py         # 3-Agent: Release + bump + tag
│   ├── daily_pipeline.py       # 4 步端到端 orchestrator
│   ├── feedback.py             # 3-Agent: feedback 收集
│   ├── git_data_push.py        # Git Data API 推送工具
│   ├── _demo_e2e.py            # 完整闭环 demo
│   └── ... (辅助)
├── tests/
│   └── smoke.py            # 烟雾测试
├── .Log/                   # 重要事件日志(归档)
├── .pending/               # 待办 issue 暂存
├── logs/                   # 运行时日志(gitignore)
└── thumbs/                 # 缩略图缓存(gitignore)
```

## 3. API 速览

公开端点: `/api/search` `/api/facets` `/api/favorites` (GET) `/api/semantic_search` (GET)
本机端点: `127.0.0.1` / `192.168.181.136` / `::1` 才允许的写操作: `POST /api/favorites` `POST /api/semantic_search` `POST /api/upload_search` `POST /api/ai_image`

完整列表 + 权限: `server.py:ADMIN_IPS` + README.md

## 4. 3-Agent 流水线

**角色**: Architect(Fixer) → Tester → Release
**入口**: `python scripts/daily_pipeline.py` (4 步端到端)
**调度**: Windows Task Scheduler `PictureWeb-DailyPipeline` (每天 0:00)
**详细**: `docs/3agent-workflow.md`

## 5. 推送规范

`git push` 在本机走 TCP 443 不通(被网络拦截),但 `https://api.github.com` 走得通。
**标准推送方式**:
- 走 `scripts/git_data_push.py` (项目自带,内部用 Git Data API)
- fallback:直接 `Invoke-RestMethod` + Bearer header 调 GitHub API

**绝不要用**: `gh CLI` (`gh auth login` 对本项目 token 必返 401) / PowerShell `Set-Content` 写 .py (GBK 污染中文)。

## 6. 验证凭据

```powershell
$h = @{Authorization="Bearer $env:GH_TOKEN"}
(Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $h).login
# 期望: 1500385678
```

## 7. 已知坑(避坑指南)

- **空仓库拒绝 `git/blobs` `git/commits`**:必须先用 Contents API `PUT /contents/<file>` 推 1 个 file 建初始 commit
- **autocrlf=true 时 SHA mismatch**:Contents API 用 `ReadAllBytes` 推的 SHA ≠ 本地 git object SHA;要本地一致就用 `git cat-file blob <sha>` 拿 LF bytes 再 base64
- **PowerShell `return ,$bytes` 嵌套 byte[]**:用 `return $bytes` 即可
- **PowerShell `ConvertTo-Json` 双重调用**:函数里别再调,只让调用方传已 JSON 化的 string
- **Secret scanning 拦硬编码 `ghp_...`**:改占位符 `__GITHUB_TOKEN_PLACEHOLDER__`,真实 token 走 env 注入
- **README CRLF vs LF**:Contents API 走 ReadAllBytes 会上传 CRLF bytes,跟 git object LF bytes SHA 不同

## 8. 沟通规范

- 语言: 中文
- 文档命名: 中文 .md,禁乱码 / 英文 draft.md / output.md
- 数字前缀宽度一致 (01/02/.../09/10/11)
- 报告: 改动 + 链接 + exit code

## 9. Owner 决策点

- 是否继续用 `_ArchitectLib/PictureDb/PictureDb.db` 共享库?(短期 yes,长期可拆)
- 是否在 PictureWeb 上重启 3-Agent 流水线 daily run?(取决于是否需要持续 issue 流入)
- 是否迁移 v0.1.x 文档到 docs/?(目前留作历史)
- 是否把 8081 端口改成可配置?(短期 hardcode,长期 PICTUREWEB_PORT env)
