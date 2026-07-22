# Phase 6 设计 · 3-Agent 流水线自动化

> 2026-07-21 · 实战第 1 天设计稿
> 项目:`PictureWebWorkflowtest`(可移植到 CanvasWeb / TectonicWeb / _index/)

---

## 1. 目标

把"issue 标 auto-fix → 自动开 PR → 跑 smoke → 通过 merge / 失败回流"做成**闭环脚本**,人只负责:

1. 复盘、改架构
2. 处理回流上限到达的 case
3. 持续喂新的 issue(写新需求)

所有"找问题 / 改代码 / 跑测试"全自动化。

---

## 2. 架构

```
                    ┌──────────────────┐
                    │   GitHub Repo    │
                    │  (issue + PR)    │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   [local cron]        [GH Action]            [mavis task]
   auto_dispatch.py    smoke.yml              Fixer agent
        │                    │                    │
        │ 扫 label=auto-fix  │  PR 触发           │  启子 session
        │ 写 .pending/      │  跑 smoke           │  改 + commit
        │ 启 Fixer agent    │  留 verdict         │  push + 开 PR
        │                    │                    │
        └─────────┬──────────┴──────────┬─────────┘
                  │                     │
                  │ 失败 ≤ 3 次         │ 失败 > 3 次
                  ▼                     ▼
            Fixer 改(回流)        @zhangyong 飞书
```

---

## 3. 文件清单(本仓库已写)

```
PictureWebWorkflowtest/
├── scripts/
│   ├── auto_dispatch.py      # 扫 issue + 派 Fixer(本地 cron)
│   └── auto_tester.py        # 跑 smoke + 写 PR verdict
├── .github/
│   └── workflows/
│       └── smoke.yml         # PR 触发 → 跑 smoke → 留 verdict
├── tests/
│   └── smoke.py              # 3 端点烟雾测试
└── docs/
    ├── 3agent-workflow.md    # 完整 runbook
    └── phase6-design.md      # 本文件
```

---

## 4. 关键决定(Why)

### 4.1 Dispatcher = 本地 cron,不靠 GitHub Action

**为什么**:GA 没法调 mavis(本地 CLI),但 mavis 是启 Fixer agent 的工具。所以调度必须本地。

**调度频率**:30 分钟扫一次。`mavis cron` 或者 PowerShell `Task Scheduler`。

### 4.2 Tester 走两路:本地 + GH Action

| 触发 | 用途 |
|---|---|
| 本地 `auto_tester.py --pr 9` | Fixer 改完手动跑,验证后 push(开发循环) |
| GH Action `smoke.yml` | PR 触发自动跑,留 verdict comment(收尾) |

**两路并行**:本地快 + 云端有记录,各管一摊。

### 4.3 失败回流用 PR comment 计数

- Tester 在 PR 留 comment,内容含 keyword `smoke verdict`
- Dispatcher 数 PR comment 中 `smoke verdict` 出现次数 = attempt 数
- attempt ≥ 3 → 留 @zhangyong 通知,不再自动改

**优点**:GitHub 永久记录,attempts 透明,人工 review 时一眼看到失败历史。

### 4.4 Fixer 当前是 stub

**为什么**:当前 mavis CLI 损坏(2026-07-14 已知),`mavis task` 不能直接调。

**当前实现**:`auto_dispatch.py` 把 issue 写到 `.pending/issue-N.json`,Fixer agent 由人/手动 mavis task 接,看 `.pending/` 队列。

**Phase 7+**:
- 修 mavis CLI(或者绕开,直接 HTTP 调 MiniMax matrix / mavis API)
- `auto_dispatch.py` 启 mavis 子 session(用 subprocess 调 mavis task 启 agent)
- Fixer agent 读 `.pending/issue-N.json` → 改代码 → commit → push → 开 PR

### 4.5 端口隔离(未来)

当前 PictureWebWorkflowtest 8081 单端口(因为本项目小,够用)。

如果以后跑 CanvasWeb-v2.5(8085 主)+ 新版本(8086 预发):
- Fixer 改完**不在 8085 跑**(影响用户)
- 起一个 8086 临时实例跑 smoke
- smoke 通过 → 切端口(8085 杀,8086 改成 8085)
- smoke 失败 → 8086 留着调试

---

## 5. 跑通的最小演示(今天能做)

```powershell
# 1. 演示 dispatcher 扫 issue(空跑)
$env:GH_TOKEN = 'ghp_xxx'
python scripts/auto_dispatch.py --dry-run
# 期望输出:"没有待 auto-fix 的 issue"

# 2. 手动给某个 issue 加 auto-fix label
$h = @{Authorization='token '+$env:GH_TOKEN; Accept='application/vnd.github+json'}
Invoke-RestMethod -Method POST `
  -Uri 'https://api.github.com/repos/1500385678/PictureWebWorkflowtest/issues/1/labels' `
  -Headers $h -Body (ConvertTo-Json @{labels=@('auto-fix')}) -ContentType 'application/json'

# 3. 再跑 dispatch
python scripts/auto_dispatch.py
# 期望:扫到 #1,写到 .pending/issue-1.json,打"STUB 模式"提示

# 4. (未来)Fixer agent 接 .pending/issue-1.json,改代码,开 PR
# 5. PR 触发 smoke.yml,跑 smoke
# 6. 通过 = auto-merge
```

---

## 6. 失败模式 + 兜底

| 失败 | 表现 | 兜底 |
|---|---|---|
| mavis CLI 损坏 | `auto_dispatch.py` 启 Fixer 失败 | 当前 stub 模式,人手动接 .pending/ |
| GitHub API rate limit | 502/429 | dispatch 加 retry + backoff |
| smoke 通过但代码有 bug | merge 后用户发现 | 加 manual review label(留给人复核) |
| 第 3 次失败没人接 | PR 卡住 | 飞书 webhook 兜底(Phase 7+) |
| mavis 启 Fixer 但 Fixer 跑飞 | .pending/ 累积 | dispatch 加超时 + 死信队列 |

---

## 7. 后续迭代路线图

### Phase 7(下一天,~4 小时)
- 修 mavis CLI(或绕开用 matrix API)
- 真实启 Fixer agent(用 mavis task)
- Fixer 改 + 自动开 PR(Closes #N)
- smoke.yml 接 verdict → auto-merge

### Phase 8(2 天)
- Inspector 自动化:`scripts/auto_inspect.py` 扫代码味道(超过 250 行 / 重复 import / 死代码)
- 每次 main 头 commit 触发 inspect,自动开 issue(标 `auto-fix` + severity)
- 飞书 webhook 兜底(第 3 次失败 @ 张勇)
- 多项目并发(同时跑 CanvasWeb / TectonicWeb / _index/)

### Phase 9(1 周)
- LLM 维度 review:`/code-review` 手动触发,LLM 读关键模块 → "代码味道"报告
- 加 changelog 自动生成(从 PR labels)
- 失败回流协议升级:dispatch 不只数 comment,还读 PR 状态(check run / commit status)
- 灰度发布:新版本先 10% 流量,无问题再 100%

---

## 8. 复用模式

把 3-agent 流水线搬到其他项目(CanvasWeb-v2.5 / TectonicWeb / _index/):

1. **复制 `tests/smoke.py` 模板** → 改端点列表
2. **复制 `scripts/auto_*.py`** → 改 `REPO` 常量
3. **复制 `.github/workflows/smoke.yml`** → 改 trigger 分支
4. **复制 `docs/3agent-workflow.md`** → 改 repo / username
5. **复制 `.gitignore`** → 项目特定(数据库文件 / 上传目录)
6. **第一次跑手动走通 1 个 issue**(跟今天 PictureWebWorkflowtest 一样)
7. **再接 mavis cron / Task Scheduler** 自动化调度

**复用清单(写进 agent memory 的)**:
- smoke.py 模板(改端点)
- auto_dispatch.py / auto_tester.py(改 repo 常量)
- smoke.yml(改 trigger)
- 3agent-workflow.md(改 repo)

---

## 9. 风险

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| Agent 改出 bug 漏到 main | 中 | 用户受影响 | smoke 是第一道;Phase 8 加 manual review label |
| 失败回流卡死(issue 永远不关) | 中 | issue 累积 | 第 3 次失败 @ 人兜底 |
| mavis 启 agent 消耗大量 token | 中 | 费用 | 限制 attempt 次数(当前 3);失败立即停 |
| 多项目并发跑,GitHub API rate limit | 低 | dispatch 失败 | 加 retry + rate limit 处理 |
| Auto-fix 误改架构层代码 | 低 | 难回滚 | severity=P0 的 issue 不进 auto-fix 队列 |

---

> 变更记录
> - 2026-07-21 · 初版 · 跟 docs/3agent-workflow.md 配套 · Architect Agent
