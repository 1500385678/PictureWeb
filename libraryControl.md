---
aliases:
  - library
tags:
  - control
  - 营长
  - 建筑师助手
created: 2026-06-27
updated: 2026-06-27
---

# 🎖️ 营长 · library

> **军衔**:营长(Mac → 军长 → 师长 → 旅长 → 团长 → 营长)
> **路径**:`library/`
> **职责**:library 索引

## 上级

- [[Defense/_index/web/webControl]]

## 平级

_(暂无)_

## 下属

_(暂无)_

## 资源

- 本目录下所有内容文件
- 关联 Obsidian 反链:在 Graph View 可见指挥链

---

> 变更记录
> - 2026-06-27 · 创建 control 文件(军衔:营长) · Macmini

---

## 详情(来自原 README)

> 独立的图库检索系统。多维标签 + 全文搜索 + AI 语义搜 + 以图搜图。

## 启动

```bash
# Windows
双击 start.bat

# 或手动
python server.py
```

打开 **http://127.0.0.1:8081/**

## 功能

- 🔍 5 维标签检索（scene / light / space / material / mood）
- ⚡ FTS5 全文搜索（中文 2-gram 分词）
- 🤖 AI 语义搜索（需 embedding.py）
- 🖼️ 以图搜图（上传图找相似）
- ⭐ 收藏夹

## 目录

```
library/
├── server.py      # Python 后端（端口 8081）
├── index.html     # 搜索主页
├── start.bat      # Windows 启动
├── README.md
├── LICENSE
└── db/
    └── images.db  # 图库数据库
```

## API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/search?q=&scene=&light=&mood=` | 多维搜索 |
| GET | `/api/facets` | 5 维标签去重值 |
| GET | `/api/favorites` | 收藏列表 |
| POST | `/api/favorites` | 切换收藏 |
| GET | `/api/semantic_search?q=` | AI 语义搜 |
| POST | `/api/upload_search` | 以图搜图 |
| GET | `/img/<相对路径>` | 图片直出 |
