## 长期记忆

> pictureweb 项目 · 跨会话需要记住的稳定事实(不是日志流水)
> 长史(YYDS 灵魂)统一格式 · 不写流水账,只留"会反复回来查"的关键节点

- 2026-08-05:长史(YYDS 灵魂)批量创建 .Core 骨架(10 件套)
- 2026-08-06:夜间批 1 5 项修复完成
  - P0 server.py 上线(stdlib http.server + /search /image /phash)
  - P1 aliases 三方一致(PictureWeb / PictureDb / pictureweb)
  - P1 arch_type 拆 image_arch_types 表(FTS5 重建)
  - P1 light 补全脚本(89/390 空 → GPT-4V 反推)
  - P2 description 降级(caption + keywords 拼接)
- 2026-08-08 23:15:pictureweb-verifier 首次巡检 5 条(P0×2 / P1×2 / P2×1)
- 2026-08-09 00:00:夜间批 1 (00:00) 全闭环
  - P0 push 重试(GitHub Contents API · 2/2 .py 上,DB 二进制略)
  - P0 fill_light_gpt4v.py 修 base64 截断 + gpt-4o + Anthropic 回退
  - P1 server.py 三处参数 try/except 转 400
  - P1 server.py ALLOWED_ROOTS 路径白名单(realpath 防 symlink)
  - P2 .Core/MEMORY.md + HEARTBEAT.md + 顶层 README.md 充实
- 2026-08-13 00:00:夜间批 1 (00:00) · 2 轮重开 · 5 项核验
  - 5 项全部已在历史 commit 完成(cbed616/d8108f4 系列),无新代码改动
  - 核验 P0 push 状态:HEAD=a7e136c 已在 origin/master + gitee/master 双远端
  - 核验 P1 aliases:.Core/IDENTITY.md:12 [PictureWeb, PictureDb, pictureweb] 3 个 ✅
  - 核验 P1 arch_type:image_arch_types 表 6 行 + images_fts 列 10 索引纳入 ✅
  - 核验 P1 light:fill_light_gpt4v.py dry-run 89/390 待补(无 key 走 ⚠️ 路径)✅
  - 核验 P2 description:fill_description_default.py dry-run 0/390 空(已满)✅
  - 闭环状态:5/5 核验通过 · 0 新代码改动 · 1 单 commit · push 双远端
- 2026-08-13 23:30:批 1 (23:30) · P0(/image 403 realpath 泄露,8-13 23:15 巡检 R362)· commit 1a87e1a
  - server.py:414-416 删 "path": real 字段(攻击者注入 .ssh/known_hosts 配合法后缀可拿 403+真实路径)
  - server.py:426-430 删 "ext": ext_suffix 字段(可枚举 DB 内 .ssh/.bashrc/.key 等敏感后缀)
  - 统一只返 {"error":..., "allowed": False} + 布尔列表
  - push:Gitee ✅(1a87e1a 0d7849e..1a87e1a)· GitHub ❌(网络层 75s × 2 timeout,本机网络层不通)
- 2026-08-14 00:00:夜间批 1 (00:00) · 3 轮重开 · 5 项核验 + P0 push 重试
  - P0 server.py GitHub push 重试:走 Contents API PUT,新 commit a0a47d3(同 1a87e1a 内容,server.py blob=57a6d593...)上 origin/master;Gitee 1a87e1a + GitHub a0a47d3 同 tree 不同 hash,长期通过 pull --rebase 同步
  - 5 项核验全部已在历史 commit 完成,无新代码改动
  - 核验 P1 aliases:.Core/IDENTITY.md:12 [PictureWeb, PictureDb, pictureweb] 3 个仍在(本次改最近更新字段)
  - 核验 P1 arch_type:image_arch_types 表 6 行(无变化)· images.arch_type 空 20/390(Verifier R363 8-13 新发现,不在本批范围,留待后续)
  - 核验 P1 light:fill_light_gpt4v.py dry-run 89/390 待补(无 key 走 ⚠️ 路径)✅
  - 核验 P2 description:fill_description_default.py dry-run 0/390 空(已满)✅
  - 闭环状态:5/5 核验通过 + P0 push ✅ · 0 新代码改动 · 1 单 commit(HEARTBEAT/MEMORY/IDENTITY 文档更新)

## 不写在这里

- 单次会话的临时操作(在 HEARTBEAT)
- 字段级 schema 变更(在 SOUL 或独立 .Workflow 文档)
- 进程日志(在 PictureDb 启动清单 / cron 任务表)
