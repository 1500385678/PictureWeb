# PictureWeb Identity

> 项目身份卡 · 让所有 agent 一眼看清楚它是谁

## 身份

| 项 | 值 |
|---|---|
| 项目 | pictureweb |
| 正式名 | PictureWeb |
| 目录名 | PictureDb |
| 别名(aliases) | [PictureWeb, PictureDb, pictureweb] |
| 概述 | 建筑效果图库 · 多维标签 + AI 语义搜 + 以图搜图 |
| 路径 | /Users/aaron/Mac/WorkTeam/05_Space/03_Architect/_ArchitectLib/PictureDb/ |
| Commander | 张勇 |
| 创建 | 2026-08-05 |
| 最近更新 | 2026-08-06(夜间批 1,5 项修复) |
| Coder | pictureweb-coder |
| Verifier | pictureweb-verifier |

## 端口 / 技术栈

| 项 | 值 |
|---|---|
| HTTP 端口 | 8081 |
| 启动 | `python3 -X utf8 server.py &` |
| 语言 | Python(stdlib) |
| 缩略图 | Pillow |
| 检索 | SQLite FTS5(unicode61)|
| 以图搜图 | pHash(perceptual hash)· 16 hex |
| 相似阈值 | 汉明距离 ≤ 10 |
| 端点 | `/` `/search?q=` `/image?id=` `/phash?id=&other=` |

## 命名约定(三方一致)

| 用在哪 | 写法 |
|---|---|
| 正式引用 / Control / Cron | PictureWeb |
| 文件目录 | PictureDb |
| 命令行 / 日志 / 进程名 | pictureweb |

**别再写混。** cron / 启动清单 / 后续 agent 引用都用 `PictureWeb`。

## 关联

- SOUL.md · 灵魂定义
- picturewebControl.md · Control 元数据(三方别名)
- server.py · HTTP 入口
- PictureDb.db · FTS5 + pHash 数据
- .Workflow/01-字段补全规范.md · 字段补全流程(P1/P2 修复后新增)
- tools/ · 批量维护脚本
