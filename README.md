# PictureWeb

> 建筑效果图与参考图的多维标签库 · 8081 端口 · Python stdlib + SQLite FTS5

## 这是什么

PictureWeb = `~/Mac/WorkTeam/05_Space/03_Architect/_ArchitectLib/PictureDb/`。
建筑效果图的入库、检索、以图搜图服务。三种写法都指向同一个项目:

| 场合 | 写法 |
|---|---|
| 正式引用 / Control / Cron | **PictureWeb** |
| 文件目录 | **PictureDb** |
| 命令行 / 日志 / 进程名 | **pictureweb** |

## 启动

```bash
cd /Users/aaron/Mac/WorkTeam/05_Space/03_Architect/_ArchitectLib/PictureDb/
python3 -X utf8 server.py &
curl http://127.0.0.1:8081/health   # 验证
```

依赖:Python 3.10+(stdlib only,无 pip install)。
可选:**Pillow**(缩略图 `thumbs/` + fill_light 缩到 1024px 节省 token/内存,P2 批 4 行 186)、OPENAI_API_KEY 或 ANTHROPIC_API_KEY(LLM 补全光线字段)。
**注**:Pillow 已是事实依赖(thumbs 缩略图、fill_light 缩到 1024),但 server.py 启动本身仍零依赖,装 Pillow 仅为填光工具链完整。

## 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` 或 `/health` | 健康检查 + 端点清单(JSON)|
| GET | `/search?q=<query>&limit=<1-100>` | FTS5 trigram 全文检索,默认 20 条,上限 100;结果按 bm25 相关度升序 |
| GET | `/image?id=<id>` | 按 id 流式发图(64KB 分块) |
| GET | `/phash?id=<id>&other=<hex>` | 16 hex pHash + 可选汉明距离(≤10 视为相似)|

错误统一 JSON:`{"error": "...", "param": "..."}`,状态码 400/403/404/500。

### /search 中文查询约定

- FTS5 tokenize=`trigram`,对中文按 3 字符滑窗分词(P1 批 4 行 185)
- query 至少 3 字符才命中(1-2 字符中文 query 仍会 0 条,前端要提示"至少 3 字符")
- 英文按词匹配(unicode61 不再用,trigram 兼容英文但粒度更细)
- 排序:ORDER BY bm25(images_fts),负数越小越相关(P0 批 4 行 183)
- FTS5 引擎不可用(表缺/被 DROP/tokenize 版本不兼容)返 503,不静默降级

## 数据规模(2026-08-09)

- 索引:390 张图(images 表)
- arch_type:6 个标签(image_arch_types 表)
- light 字段空值:89/390(等 LLM 补全或前端手工)
- DB 大小:~870 KB
- FTS5:`?q=hotel` 命中 6 条(arch_type 多值正确索引)

## 文件结构

```
PictureDb/
├── server.py            # HTTP 入口 · 213 行 · stdlib
├── PictureDb.db         # SQLite + FTS5 + pHash
├── thumbs/              # 缩略图(Pillow 生成)
├── tools/               # 批量维护脚本
│   ├── fill_light_gpt4v.py          # 光线 LLM 补全
│   ├── fill_description_default.py # 描述降级(caption+keywords)
│   └── migrate_p1p2.py              # P1/P2 schema 迁移
├── .Core/               # 项目骨架 10 件套
├── .Workflow/           # 工作流文档
└── README.md            # 本文件
```

## 不做什么

- ❌ 不绑 0.0.0.0(只 127.0.0.1)
- ❌ 不外发 /image 路径越界(ALLOWED_ROOTS 白名单 · 403)
- ❌ 不存任何密钥(读环境变量)
- ❌ 不重写已有缩略图(Pillow 检测到缩略图存在则跳)
- ❌ 不在 main 之外改 master/HEAD 之外的分支
- ❌ 不改 .Core/SOUL.md 灵魂内容(J10 审)

## 关联

- [picturewebControl.md](picturewebControl.md) · Control 元数据(三方别名)
- [.Core/IDENTITY.md](.Core/IDENTITY.md) · 身份卡
- [.Core/SOUL.md](.Core/SOUL.md) · 灵魂定义
- [.Core/MEMORY.md](.Core/MEMORY.md) · 长期记忆
- [.Core/HEARTBEAT.md](.Core/HEARTBEAT.md) · 心跳日志
- 项目夜间迭代-2026-08.xlsx · Verifier 巡检表(pictureweb 行 42-46/112-116/182-186)

## 维护

- Coder:pictureweb-coder
- Verifier:pictureweb-verifier
- Commander:张勇
- 最近巡检:2026-08-10 23:15
- 最近迭代:2026-08-11 00:00(批 1 (00:00) · 4/4 闭环 P0+P1×2+P2)
