# AGENTS.md — PictureWeb 项目真值源

> Agent 必读。本文件描述项目是什么、怎么工作,任何 agent 进项目都先读这一份。

## 0. 项目是什么

**PictureWeb** 是独立图库检索系统。多维标签 + 全文搜索 + AI 语义搜 + 以图搜图。
端口 **8081** · Python 标准库 + Pillow · 零 npm 依赖。

**前身**: `PictureWebWorkflowtest` (仓库 `1500385678/PictureWebWorkflowtest`),v0.1.x ~ v2.0.0 期间作为 **3-Agent 流水线** PoC 验证场。2026-07-22 v2.0.0 拆出,作为正式独立项目运营。

## 1. 关键属性

| 项 | 值 |
|---|---|
| 工作目录 | `G:\_MyGitProject\PictureWeb\` |
| 远端仓库 | `https://github.com/1500385678/PictureWeb` (private, 2026-07-22 v2.0.5 起) |
| 远端主分支 | `main` |
| 当前版本 | `v2.1.7` (`__version__.py`) |
| DB 根 (v2.1.8) | `G:\_MyDatabase\01_Space_ImageDb` (2026-09-22 改;env `PICTUREWEB_DB_ROOT` 可覆盖) |
| DB 集中点 (v2.1.8) | `G:\_MyDatabase\01_Space_ImageDb\SpaceDb.db` 总库 + 6 个分库(详见 § 10) |
| 启动命令 | `python -X utf8 start_detached.py --daemonize` (永驻,脱离 mavis 父级) |
| 默认 URL | http://127.0.0.1:8081/ |
| 默认 DB | `SpaceDb` (770 张,顶层总库;env `PICTUREWEB_DEFAULT_DB` 可覆盖) |
| 共享数据 | 兄弟模块共享(共享前通知其他项目方;非本仓库) |
| 图库根 | `D:\Mac\Mac\workteam\05_space\03_architect\Mobile` |
| 缩略图缓存 | `thumbs/` (gitignore) |
| 日志 | `logs/` (gitignore) |
| 历史老仓库 | `1500385678/PictureWebWorkflowtest` (v0.1.x ~ v2.0.0,教学样本) |

## 2. 目录结构

```
PictureWeb/
├── server.py             # 后端(单文件,~430 行)
├── start_detached.py     # 永驻启动器(CREATE_BREAKAWAY_FROM_JOB 脱离 mavis)+ watchdog
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

- 是否把 8081 端口改成可配置?(短期 hardcode,长期 PICTUREWEB_PORT env)
- 是否把 SpaceDb.db 物理拆成多个独立 db(避免单文件过大)?(短期单文件,长期按年份分)
- 是否要把分库的"metadata 全部从总库同步"做自动化脚本(避免下次重蹈覆辙)?

## 10. 数据库规则(2026-09-23 总结 · 接手必读)

### 10.1 命名铁律

- **db_name 一律等于文件名**(去掉 `.db` 扩展名 + 去下划线前缀)
  - `SpaceDb.db` → `SpaceDb`;`MasterDb.db` → `MasterDb`;`_AnalysisDb.db` → `AnalysisDb`
  - **不认父目录名**(2026-09-23 改之前会因为父目录以 `Db` 结尾而错用父目录名)
- server.py 自动派生规则:见 `server.py:69`(`db_name = os.path.splitext(fn)[0].lstrip('_')`),函数 `_scan_dbs()` 起在 `server.py:29`
- **备份文件**(`*.db.pre-fix-*` / `*.db.bak.*` / `*.db.pre-sync*`)—— server.py 自动过滤,但**清理彻底**用 `rm --` 走 mavis-trash,**不要** `Remove-Item`

### 10.2 库结构(1 总 + 6 分)

```
G:\_MyDatabase\01_Space_ImageDb\
├── SpaceDb.db                  ← 总库 (770 张,数据源)
├── 01_Master/MasterDb.db        ← 分库 (168 张,大师作品源)
├── 02_WeWork/WeWorkDb.db        ← 分库 (25 张,工作项目)
├── 03_Residence/ResidenceDb.db  ← 分库 (37 张,住宅)
├── 04_Block/BlockDb.db          ← 分库 (67 张,街区)
├── 07_Visualization/VisualizationDb.db  ← 分库 (447 张,视觉成品)
└── 08_Diagram/DiagramDb.db      ← 分库 (11 张,分析图)
```

### 10.3 总库 vs 分库

- **总库 `SpaceDb.db` 是数据源**——所有 metadata 在这里打 tag,所有 facets 从这里派生
- **6 个分库是从总库切出来的"切片库"**——只按目录维度(分类路径)切片,metadata 跟总库一致
- 分库的 metadata 字段(scene/light/mood/project/arch_type/...等 12 列)**不独立打 tag**,**只能从总库同步**
- 切片工具/同步脚本必须保证:**12 个 metadata 列 + abs_path(新路径) 都同步过去**(2026-09-22 之前切片工具只复制基础字段,metadata 全空 → 教训)

### 10.4 3 层 8 分类

每个分类目录对应一个分类维度(`images.dimension` / `images.expression` 列):

| 维度 | 目录 | 含义 |
|---|---|---|
| source | 01_Master / 02_WeWork | 大师作品 / 自己项目 |
| dimension | 03_Residence / 04_Block / 05_Spirit | 生活 / 社区 / 精神建筑 |
| expression | 06_Concept / 07_Visualization / 08_Diagram | 设计概念 / 视觉成品 / 分析图 |

每张图**可同时**属于 3 个维度,允许重叠。

### 10.5 metadata 字段(12 个,facets 派生源)

| 列 | 类型 | 例子 | facet |
|---|---|---|---|
| `project` | 单值 | 北岸礼堂 | projects |
| `scene` | `;` 分隔多值 | `eye-level;detail` | scenes |
| `light` | `;` 分隔多值 | `golden-hour;dusk` | lights |
| `mood` | `;` 分隔多值 | `quiet;contemplative` | moods |
| `arch_type` | 单值 | cultural / commercial / hotel / villa | archs |
| `render_company` | 单值 | 公司名 | companies |
| `view_type` | 单值 | bird-eye / eye-level / other | view_types |
| `material` | `;` 分隔多值 | concrete / glass | (搜索用) |
| `space` | `;` 分隔多值 | interior / exterior | (搜索用) |
| `caption` | 单值 | 中文短标题 | (显示用) |
| `description` | 单值 | 长描述(中文段落) | (显示用) |
| `keywords` | `;` 分隔多值 | 中文短语 | FTS 搜索 |

基础字段:`abs_path`(绝对路径)/ `filename` / `file_size` / `ext` / `source` / `created_at` / `updated_at`

### 10.6 路径迁移铁律

- **改名要所有相关 db 一起改**(2026-09-22 教训:`01_SpaceDb` → `01_Space_ImageDb` 第一次只改了总库 SpaceDb.db,6 个分库没动,导致 770 张图全部 404,修复 2 次才补齐)
- 改后**必须**验证所有 `abs_path` 实际存在:`os.path.exists(path) == True`,否则前端 404
- 跨项目通知:任何路径迁移都要通知其他依赖 `PictureDb.db` 的项目方

### 10.7 入库占位符禁止

- 不要在 metadata 字段填 "Style" / "TBD" / "未分类" 等通用占位符 —— 之前 `Diagram (X).jpg` 全填 "Style" 同步到 DiagramDb 全错位
- 空值用 **NULL**(project 列有 NOT NULL 约束的,用空字符串 `''`),user 后续手动补真实值
- 占位用清晰可识别的:`'Diagram-(待补)'` 等**只在当前场景下唯一**的字符串

### 10.8 ⚠️ 踩过的坑(避坑指南)

- **Python sqlite3 UPDATE 必须显式 `db.commit()`**(2026-09-23 教训)
  - 默认 `isolation_level=""` 是**延迟事务**,`db.execute("UPDATE ...")` 只在内存里跑
  - **必须** `db.commit()` 才落盘;`db.close()` **不自动 commit**
  - 诊断:写完用 `Get-Item <db文件> | Select-Object LastWriteTime` 看 mtime,mtime 没变 = 没真写入
  - 解决:每次写完都 `db.commit()`;或打开 `isolation_level=None` autocommit
- **server.py 启动时 `_scan_dbs()` 一次性扫描**(2026-09-23 教训)
  - 改 server.py 后必须**重启 server** 才能看到新 db 列表 / 新 db_name
  - hot reload 只能重启 server 子进程,不能改 module-level 变量
- **db_name 派生规则(2026-09-23 已修)** —— 一律用文件名,不再认父目录名
- **server 读 db 是每次新连接直读**(2026-09-23 教训)
  - SQLite 不缓存,server 每次请求都从文件读最新数据
  - 浏览器看到的"老数据"**几乎都是浏览器 HTML/JS 缓存**(Ctrl+F5 强制刷新解决)
  - 跟 server 缓存无关,不需要重启 server
- **PictureWeb 项目代码 0 个生成 thumbs 的代码** —— `thumbs/` 嵌套几百层是**外部 ingest/thumbnail 脚本**的路径派生 bug,跟 server 无关;PictureWeb 不读 thumbs,可安全删
