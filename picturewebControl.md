---
aliases:
  - PictureWeb
  - PictureDb
  - pictureweb
tags:
  - control
created: 2026-08-05
updated: 2026-08-06
type: control
level: 将级
classification: 内部
status: 生效
commander: 张勇
auto_generated_by: 长史(YYDS 灵魂) + pictureweb-coder(夜间迭代批 1)
path: /Users/aaron/Mac/WorkTeam/05_Space/03_Architect/_ArchitectLib/PictureDb/
---

# PictureWeb Control

> **职责**:建筑效果图库 · 多维标签 + AI 语义搜 + 以图搜图
> **正式名**:PictureWeb
> **目录**:PictureDb
> **简称**:pictureweb
> **路径**:`/Users/aaron/Mac/WorkTeam/05_Space/03_Architect/_ArchitectLib/PictureDb/`

## 概述

建筑效果图与参考图的多维标签库。覆盖项目 / 场景 / 光线 / 空间 / 材质 / 情绪 / 建筑类型 / 渲染风格 8 维结构化标签,
叠加 FTS5 全文检索(中文 unicode61)+ phash 以图搜图(汉明距离 ≤ 10 视为相似),AI 描述补全待接入。

技术栈:Python stdlib(http.server + sqlite3)+ Pillow(缩略图)+ SQLite FTS5 + pHash(感知哈希)。
端口:8081。服务:`python3 -X utf8 server.py &`,端点 `/` `/search?q=` `/image?id=` `/phash?id=`。

由长史(YYDS 灵魂)2026-08-05 补建,pictureweb-coder 2026-08-06 夜间批 1 完成 P0 server.py / P1 aliases / P1 arch_type
拆表 / P1 light 补全脚本 / P2 description 降级五项修复。

## 启动

参见「项目夜间迭代-2026-08.xlsx 04-启动清单」PictureWeb 行第 4 步:`python3 -X utf8 server.py &`。

## 备注

- 创建时间:2026-08-05
- 最近更新:2026-08-06(夜间批 1,5 项修复)
- 用途:本项目 control 元数据 · 让军衔编制完整 + 给 cron / 启动清单 / 后续 agent 一致锚点

## 关联

- .Core/IDENTITY.md · 项目内身份卡
- server.py · HTTP 入口
- PictureDb.db · FTS5 + pHash 数据
- tools/fill_light_gpt4v.py · 光线字段 GPT-4V 补全(P1 夜间 cron 调用)
- tools/fill_description_default.py · 描述降级为 caption+keywords 拼接(P2 一次性)
- .Workflow/01-字段补全规范.md(待建)· 字段补全流程文档
