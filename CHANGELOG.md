# CanvasWeb v3.5.53 · CHANGELOG

> 2026-08-05 单日连推 18 个 release (v3.5.22 → v3.5.40) + 2026-08-06/07 续推 v3.5.40.3-48 共 16 个 patch/minor + 2026-08-12/13 续推 v3.5.49-50 修 401/参考图传递 + 2026-08-17 v3.5.53 补 P1 守卫,覆盖 ✨ AI 节点 prompt 优化 / 建筑外观 34 预设 / 视频 15 预设 / 节点连接线 / 批量操作 / 画布导出 PNG / chat 历史服务端持久化 / Issues 反馈双平台同步 / 画布间复制粘贴 / FAB 反馈 / 文档同步 / thumbs 异常收集 / 文档数字守卫 / smoke 启动前 precheck 等
> 详细每个 release 的变更点见下方「v3.5.14 → v3.5.48 · 自动汇总」段(2026-08-07 由 `tools/gen_changelog.sh` 从 `AGENTS.md` 提取)
> v3.5.14-48 完整 commit 列表见 [GitHub Releases](https://github.com/1500385678/canvasweb/releases) · [Gitee Releases](https://gitee.com/architectzy/canvasweb/releases)

---

## v3.5.49 → v3.5.53 · 手动补(2026-08-14/17 by canvasweb-coder 夜间迭代批 1)

- 2026-08-12 · v3.5.49 · patch · 修本机保存画布 401(_check_post 加本机 admin IP 豁免)
- 2026-08-13 · v3.5.50 · patch · 修 AI 节点→视频节点 参考图传递(ai_video.py 解析 /upload/ + input_image_path 走 upload_file + _matrix_api 包 MediaInfo)
- 2026-08-16 · v3.5.51 · patch · 修 AI 设计助手"思考中"卡死(chat-context _srcToDataUrl 递归 bug + AbortController 60s 兜底) + 工程质量 5 大改造(中心化 timeout / 60+ 单测 / 拆 state.js god / skill 危险操作确认 / 关 v2)
- 2026-08-17 · v3.5.53 · patch · 3 修(夜间迭代 R365):thumbs 异常收集 logs/thumb_errors.json + _thumbs_health.py 全量扫描工具 / 文档数字漂移治理(handler 22→26,module 99→96 真实数 + _gen_structure.py --check-doc-drift 守卫) / _smoke.py 启动前 syntax precheck 防 connection refused 误导

---

## v3.5.14 → v3.5.48 · 自动汇总(2026-08-07 由 `tools/gen_changelog.sh` 生成,2026-08-11 增补 v3.5.41-48) · v3.5.49+50 见上方手动段

<!-- 数据源: AGENTS.md 变更记录段 -->
<!-- 自动生成于 2026-08-07 · 人审后合入 CHANGELOG.md -->

- 2026-08-05 · v3.5.40 · minor · 4 合一波(doc sync + 连接线增强 + chat 导出 MD + 节点缩放/旋转)
- 2026-08-05 · v3.5.39 · minor · 4 合一波(代码卫生 + 导出 PNG + chat 持久化)
- 2026-08-05 · v3.5.38 · patch · 文档同步(AGENTS.md 补 v3.5.22-37 · 模块数 60+ → 95 · 警戒列表更新)
- 2026-08-05 · v3.5.37 · minor · 节点批量操作(浮动栏 + 6 维对齐 + 横/竖排 + 批量改色 · bulk-actions.js 254 行 · AGENTS.md §6 ❌→✅)
- 2026-08-05 · v3.5.36 · minor · 节点备注/说明(n.desc 字段 + 画布右上角 📝 徽章 + AI 浮层 📝 按钮 + desc-edit.js 跟 name-edit.js 平行)
- 2026-08-05 · v3.5.35 · minor · 迷你连接线(1px 极简 + 端点拖动重指 + 右键删 · AGENTS.md §6 ❌→✅)
- 2026-08-05 · v3.5.34 · minor · 节点 name 标签双击改名(name-edit.js,123 行,跟 text-edit.js 平行)
- 2026-08-05 · v3.5.33 · minor · AI 节点重跑队列(🔁×3 并行 + 侧栏 10 张可点回主图)
- 2026-08-05 · v3.5.32 · minor · 快捷键补缺(方向键 nudge / F2 改名 / Esc 取消 / ? 帮助弹窗)
- 2026-08-05 · v3.5.31 · patch · 预设/模板下拉加搜索框(filter <option> + optgroup auto-hide + Escape 清空)
- 2026-08-05 · v3.5.30 · minor · 节点对齐辅助线(Figma 风格 5 维 snap + 橙色虚线)
- 2026-08-05 · v3.5.29 · patch · 文档同步(AGENTS.md + api_contract.md 补 v3.5.22-28)
- 2026-08-05 · v3.5.28 · patch · 去掉 AI 节点画布占位矩形(`drawAINodePlaceholder` 跟浮层 panel 视觉错位)
- 2026-08-05 · v3.5.27 · patch · 去掉 AI 节点选中时 panel 自身橙色/绿色 border + box-shadow 辉光
- 2026-08-05 · v3.5.26 · patch · 修 AI 节点选中时橙色外框跟 panel border 错位 2px bug
- 2026-08-05 · v3.5.25 · patch · 模板下拉 + chip bar 改 <details> 默认折叠(节省垂直空间)
- 2026-08-05 · v3.5.24 · minor · 建筑外观视频预设库(15 条 · 4 维 chip · 复用生图数据)
- 2026-08-05 · v3.5.23 · minor · 建筑外观 prompt 预设库(34 条 · 4 维 chip)
- 2026-08-05 · v3.5.22 · minor · AI 节点 prompt 优化(中/英/反向词 4 段 + 历史回滚)
- 2026-08-06 · v3.5.40.3 · hotfix · 修图片/AI 节点看不见(`canvas-fit.js` 自动 fit-to-view)
- 2026-08-06 · v3.5.40.4 · hotfix · 修 AI 节点浮层 panel 全不显示(根因: v3.5.33 rerunQueueStrip `isChild` const TDZ)
- 2026-08-06 · v3.5.40.5 · doc · 加 `01_开发纪要-错误总结与避坑指南.md` + AGENTS.md §1 指向
- 2026-08-06 · v3.5.41 · minor · 加 `/api/feedback_arch` 反馈模块(并行创建 GitHub + Gitee issue · 24h 缓存)
- 2026-08-06 · v3.5.42 · minor · Issues 反馈前端 UI(画布底部 🐛 按钮 + 弹窗 3 tab)
- 2026-08-06 · v3.5.43 · minor · Excel 主源路线 + GitHub Issues 自动同步(`_excel_to_github.py` 推 66 任务)
- 2026-08-07 · v3.5.44 · minor · 画布间复制粘贴(`canvas-paste-to.js` 104 行) + 空白画布清理
- 2026-08-07 · v3.5.45 · minor · 右下角问题反馈 FAB 按钮(`fb-issues-fab`)
- 2026-08-07 · v3.5.46 · patch · FAB 修(移 body 末尾 + inline style 兜底 + CSS/JS no-cache)
- 2026-08-07 · v3.5.47 · patch · close open issues + `_fetch_issues.py` 工具(拉到 `logs/github-issues-latest.json`)
- 2026-08-07 · v3.5.48 · minor · 真做 D-013/014/015 三个 auto-dev issues(报错自动上报 + docs 补齐 + 大图懒加载)
- 2026-07-28 · 代码评审响应:3 个 P0 修复(events 孤儿 / admin 闸门 / 右键删除) + 2 个 P1(is_deleted 软删 / FTS 参数化) + config.py 硬编码改 env + AGENTS.md 行数同步
- 2026-07-27 · 跨画布全局搜索从顶栏挪到底部居中(v3.1.7)
- 2026-07-27 · 移除顶栏快捷键提示文字(v3.1.8)
- 2026-07-27 · 复活右侧 AI 设计助手聊天面板(chat-panel.js) + 拆出 chat-runtime.js
- 2026-07-27 · 加聊天技能系统(chat-skills/)— OpenAI function-calling 协议,LLM 调技能改画布
- 2026-07-27 · 加右侧悬浮折叠按钮(chat-toggle-btn)
- 2026-07-08 · v3.0 重构完成 · 后端 15 模块 + 前端 18 模块 + 3 CSS · arch2

> 重新生成: `bash tools/gen_changelog.sh` · 数据源策略: 优先 `git tag`,回退 `AGENTS.md` 变更记录段

---

## v3.5.13 · 累计 25 个 release · 2026-07-28

**代码量**: 22,767 行 (121 个文件, 0 依赖, 0 npm, 0 pip)
**Commits**: 192 个 · **Tags**: 71 个 (v3.0.40 ~ v3.5.13)

---

### 核心架构 (v3.0 基础)
- **后端**: Python 标准库 `http.server` + SQLite, 26 个 handler 文件
- **前端**: 原生 ES Modules, 96 个模块, 0 构建工具
- **数据**: SQLite (画布状态 + AI 图片库) + JSON (收藏 + LLM 配置) + 共享 PictureDb
- **设计**: 单文件 < 250 行 · AGENTS.md 协作规范 · 0 业务库依赖

---

## v3.3.x 系列功能 (主要)

### v3.3.3 — Tier 1.3 最终: 4 个功能 + 3 个 bug fix
- 调色板 → prompt 工具 (`palette-util.js`)
- prompt 模板系统 (`prompt-templates.js`)
- 画布历史快照 (`canvas-history.js`)
- 本地 LLM 支持 (Ollama / LM Studio)

### v3.3.4 — 语音输入 (Web Speech API)
- `voice-input.js` · 浏览器原生语音识别
- 实时转文字到 chat 输入框

### v3.3.5 — 项目库 (画布按项目分组)
- canvas.project 字段 + 下拉分组

### v3.3.6 — 蒙版工具
- `mask-tool.js` + `mask-launcher.js`
- 4 笔刷粗细 + 撤销/清除 + 复制到剪贴板

### v3.3.7 — AI 智能修补 (simulated inpainting)
- `ai_inpaint.py` · PIL crop + 8px 高斯羽化
- ⚠️ matrix 平台偶发 "temporary failure", 3-retry

### v3.3.8 — 视口懒加载 + Toast 栈
- `canvas-list.js` _loadImg IntersectionObserver
- `dom.js` toast 队列(最多 4 条, 底部居中)

### v3.3.9 — 画布文本上下文(LLM 助手)
- `chat-context.js` · 节点类型/状态统计 + 多选 + 锚点
- 动态 system prompt(每轮)

### v3.3.10 — 画布图像多模态
- `chat-context.js` getCanvasImages() · 3 张图 max
- 512x512 JPEG q=0.7 · 附首条 user message
- 修 LLM 多模态 list content 处理

### v3.3.11 — 画布历史 diff 视图
- `canvas-history-diff.js` · 9 字段对比
- color-coded: 绿=加 / 红=删 / 琥珀=改

### v3.3.12 — 批量 prompt 编辑器
- `bulk-prompt-editor.js` · 4 模式(prefix/suffix/replace/find_replace)
- 50ms 错峰重新生成

### v3.3.13 — 节点连接管理面板
- `connections-panel.js` · 列表 / 单删 / 清空 / 双击定位
- 顶部"🔗 连接"按钮

### v3.3.14 — 右击节点菜单 "🔗 连接到..."
- `context-menu.js` 暂存 from → target
- 3 种连线入口 (Ctrl+L / 端口拖拽 / 右击)

### v3.3.15 — Prompt 模板面板
- `prompt-templates-panel.js` · 列表 / 保存 / 复制到剪贴板
- 顶部"📋 模板"按钮

### v3.3.16/17/18/19 — 4 个 P0 修复
- v3.3.16: `connections` import 撞名
- v3.3.17: `nodes` import 撞名(修一个漏一个的教训)
- v3.3.18: `connections-panel.js` emoji 编码崩
- v3.3.19: `prompt-templates-panel.js` 同样 emoji 崩
- 加 `_check_imports.py` 预检脚本

### v3.3.20 — UI 重构: 工具栏挪到左侧
- ⚠️ 后面被 v3.3.21 撤销(挤掉了图库)

### v3.3.21 — UI 重做: 画布下拉留左, 工具栏回顶
- 14 个功能按钮回画布顶部 · 缩短文字 + 字号缩小
- 画布下拉 + 新建/重命名/删除 留 sidebar

### v3.3.22 — Sidebar + Toolbar 收起/展开按钮
- `panel-toggle.js` · 2 个按钮(参考 chat-toggle-btn 风格)
- localStorage 持久化
- "你正在编辑" banner 跟着 toolbar 收起

### v3.3.23 — 画布选择栏挪到画布底部 + 第 3 个收起按钮
- `panel-toggle.js` 拓展 canvastopbar
- 跟 minimap/缩放在同一行

### v3.3.24 — 修复 LLM 状态重叠 + 重命名
- .canvas-topbar right: 12px → 240px 让出 LLM 状态位置

### v3.3.25 — 切画布后重命名失败修复
- `renameCanvas()` cur 找不到时主动 fetch 兜底

---

## 今日 (2026-07-28) 一天 25 个 release

**5 个 P0 修复**:
- 2 个 import 撞名 (`connections` / `nodes`)
- 2 个 emoji 编码崩 (`connections-panel` / `prompt-templates-panel`)
- 1 个回归 bug (切画布后重命名)

**教训固化**:
- 写新 import 前 `python _check_imports.py` 防撞名
- 写新 JS panel 文件绝对不用 emoji (用 ASCII `[T]` `[IMG]`)
- `node --check` + smoke + `_check_imports.py` + Python urllib 拉 server 字节 四件套

---

## 性能与统计 (截至 v3.5.13)

| 项 | 值 |
|---|---:|
| 画布数 | 33 可见 + 48 软删 |
| AI 生图 | 170 张 |
| Output 数据 | 657 MB |
| Workspace 总大小 | 1.1 GB |
| 工作区代码:数据比 | 1 : 800 |

---

## 路线图 (deferred)

- 真实 inpainting (DashScope API) — 1 week
- SketchUp 衔接 — 2 weeks
- 缩略图缓存优化
- AI 风格库 (按项目分组 prompt 历史) — 6h
- WebSocket 实时协作 — 1-2 weeks
- 移动端 PWA — 1 week
- PDF 文档化导出 — 1 week

---

## 部署

```bash
# 前台
python -X utf8 -u -m server
# 后台
python _daemon.py
# 验证
python _smoke.py   # 14/14 OK
```

端口: 9002 (v3.0) · 8082 (v1 留对照) · 8083 (v2 留对照)
