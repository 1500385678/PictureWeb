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

## 不写在这里

- 单次会话的临时操作(在 HEARTBEAT)
- 字段级 schema 变更(在 SOUL 或独立 .Workflow 文档)
- 进程日志(在 PictureDb 启动清单 / cron 任务表)
