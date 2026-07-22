# 3-Agent 流水线实战记录

> 2026-07-21 · 第一次跑通 3-Agent(Inspector / Fixer / Tester)协作流水线。
> 项目:`PictureWebWorkflowtest` · 仓库:https://github.com/1500385678/PictureWebWorkflowtest

---

## 1. 流程全景

```
┌──────────┐   issue   ┌────────┐    PR    ┌────────┐
│ Inspector│ ────────→ │ Fixer  │ ───────→ │ Tester │
│ 找问题   │  (label:  │ 改代码 │  (push)  │ 验收   │
└──────────┘   auto-   │ + 版本 │          │ 通过   │
              fix)     └────────┘          │ = merge│
                                           └────────┘
                                              │ 失败
                                              ↓
                                           留 PR comment
                                              ↓
                                          Fixer 改(循环 ≤ 3 次)
```

| 角色 | 当前是 | 自动化目标 |
|---|---|---|
| **Inspector** | 人肉 review(LLM 辅助) | `scripts/inspect.py` 扫代码 → 写 issue |
| **Fixer** | 人改 + commit + push | `scripts/auto_fix.py` 接 `auto-fix` label 自动开 PR |
| **Tester** | `python tests/smoke.py` 跑端点 | `scripts/tester.py` 跑 smoke + 业务流,通过 merge |
| **Dispatcher** | 我(对话里) | GitHub Actions cron 触发 |

GitHub = 协作中枢(issue / PR / comment / label = 单一事实源)

---

## 2. 实战命令清单(可直接复用)

### 2.1 环境准备(只需做一次)

```powershell
# 1. 验证 token + 拿真实 username
$env:GH_TOKEN = 'ghp_xxx'
$me = Invoke-RestMethod -Uri 'https://api.github.com/user' `
  -Headers @{Authorization='token '+$env:GH_TOKEN}
$me.login   # 真实 GitHub username(不一定是 email)

# 2. 设通用 header(后续复用)
$h = @{
  'Authorization' = 'token ' + $env:GH_TOKEN
  'Accept'        = 'application/vnd.github+json'
  'User-Agent'    = 'ArchitectAgent'
}
```

### 2.2 Phase 0 · 本地 git 入库

```powershell
$root = 'D:\Mac\Mac\Mac\workteam\05_space\03_architect\Mobile\_ArchitectMobileLib\PictureWebWorkflowtest'
Set-Location $root

git init -b main
git config user.name 'YOUR_GITHUB_USERNAME'
git config user.email 'YOUR_USERNAME@users.noreply.github.com'  # GitHub noreply 格式

# 写 .gitignore(参考项目根 .gitignore)
# 写 README.md

git add .
git commit -m "init: git 入库 + .gitignore + README"
```

### 2.3 Phase 2 · 创建/复用 GitHub 仓库

```powershell
# 检查是否已存在
$repo = Invoke-RestMethod -Uri "https://api.github.com/repos/$($me.login)/PictureWebWorkflowtest" -Headers $h

# 如不存在则创建(private)
if (-not $repo) {
  $body = @{name='PictureWebWorkflowtest'; private=$true} | ConvertTo-Json
  $repo = Invoke-RestMethod -Uri 'https://api.github.com/user/repos' `
    -Method POST -Headers $h -Body $body -ContentType 'application/json'
}
```

### 2.4 Phase 3 · 批量创建 issue

```powershell
$issues = @(
  @{ title = '[P0] 某问题'; labels = @('bug','priority:high'); body = @'...markdown...'@ },
  ...
)
foreach ($iss in $issues) {
  $payload = @{title=$iss.title; body=$iss.body; labels=$iss.labels} | ConvertTo-Json -Depth 10
  $r = Invoke-RestMethod -Uri "https://api.github.com/repos/$($me.login)/PictureWebWorkflowtest/issues" `
    -Method POST -Headers $h -Body $payload -ContentType 'application/json'
  Write-Host "#$($r.number) $($r.title)"
}
```

### 2.5 Phase 4-5 · Fixer 改 + 开 PR + Tester 验收 + Merge

```powershell
# Fixer: 改代码 + 开 PR
git checkout -b fix/issue-N
# ... 改代码 ...
git add .
git commit -m "fix(issue-N): ..."
git remote set-url origin "https://x-access-token:$($env:GH_TOKEN)@github.com/$($me.login)/PictureWebWorkflowtest.git"
git push -u origin fix/issue-N
git remote set-url origin "https://github.com/$($me.login)/PictureWebWorkflowtest.git"

$prBody = @'...'@
$payload = @{title='fix(issue-N): ...'; body=$prBody; head='fix/issue-N'; base='main'} | ConvertTo-Json -Depth 5
$pr = Invoke-RestMethod -Uri "https://api.github.com/repos/$($me.login)/PictureWebWorkflowtest/pulls" `
  -Method POST -Headers $h -Body $payload -ContentType 'application/json'

# Tester: 跑 smoke
python tests/smoke.py
# 3/3 OK → merge
$merge = @{commit_title='fix(issue-N): ...'; commit_message='Closes #N'; merge_method='squash'} | ConvertTo-Json
Invoke-RestMethod -Uri "https://api.github.com/repos/$($me.login)/PictureWebWorkflowtest/pulls/$($pr.number)/merge" `
  -Method PUT -Headers $h -Body $merge -ContentType 'application/json'
```

---

## 3. 实战踩坑(必看)

### 3.1 ⚠️ PowerShell 5.1 `Invoke-WebRequest` 假错误

**症状**:`Invoke-WebRequest http://127.0.0.1:8081/api/...` 报"Windows PowerShell 处于非交互模式。朗读和提示功能不可用"。

**真相**:PowerShell 5.1 的 WebCmdlet 想弹交互对话框(屏幕阅读器),非交互模式直接 fail。**不是真网络错误**。

**绕开**:用 Python `urllib` 写 smoke,或者用 `System.Net.Http.HttpClient`。**别在 PowerShell 5.1 里用 Invoke-WebRequest 测本地服务**。

### 3.2 ⚠️ GitHub merge API 字段名

**症状**:`PUT /pulls/{n}/merge` 返 400 "Problems parsing JSON"。

**真相**:字段是 `merge_method`(`'merge' | 'squash' | 'rebase'`),**不是** `squash: true`。

```powershell
# 错
@{ commit_title='...'; squash=$true } | ConvertTo-Json
# 对
@{ commit_title='...'; merge_method='squash' } | ConvertTo-Json
```

### 3.3 ⚠️ commit message 里的换行

**症状**:`merge_method: 'squash'` + commit_message 含 `\r\n` 时,某些 PowerShell 版本下 400。

**绕开**:`commit_message` 用单行,或者在 ConvertTo-Json 后手动 replace。

### 3.4 ⚠️ `git push --delete` 在 PowerShell 5.1 卡死

**症状**:`git push origin --delete fix/xxx` 永远 hang(120s 超时)。

**绕开**:用 GitHub API:
```powershell
Invoke-RestMethod -Uri 'https://api.github.com/repos/owner/repo/git/refs/heads/fix/xxx' `
  -Method DELETE -Headers $h
```

### 3.5 ⚠️ `git fetch` 在某些环境也卡

**症状**:`git fetch origin` 30-90s 不返回(smart HTTP / git 协议被拦)。

**绕开**:
- 用 `git fetch origin <sha>:refs/remotes/origin/main` 指定 commit
- 或者用 GitHub API(Contents API / Refs API)直接操作

### 3.6 ⚠️ safety 拦 Remove-Item

**症状**:PowerShell 5.1 + mavis safety 把所有 `Remove-Item` 视为危险(包括删环境变量)。

**绕开**:
- 删文件用 `mavis-trash`(可恢复)
- 删环境变量赋 `$null` 即可,sub-shell 退出自动清

### 3.7 ⚠️ `git branch -d` 报"not fully merged"

**症状**:squash merge 后,git 不认分支"merged"(因为 SHA 变了),`git branch -d` 报 not fully merged。

**绕开**:`git branch -D`(强删)。

### 3.8 ⚠️ "删整行 import" 的隐性 Bug

**症状**:删 `import sqlite3, os, sys, json, base64, hashlib` 整行 → `os/sys/json/sqlite3/base64` 全没 import → `NameError: name 'sys' is not defined`。

**教训**:
- **只删用不到的名字**:`import sqlite3, os, sys, json, base64` 保留
- 用 `git diff` 看清楚再 commit
- **第一次修代码必然 Tester 抓 bug**,这正是 3-agent 流水线要的价值

---

## 4. 走通的 2 个 PR(参考样本)

### PR #9 · 删 `import hashlib`

- Commit:`57fdd09`
- Diff:1 行删除 + 新增 `tests/smoke.py`
- Tester 抓到 `NameError` → Fixer 修正 → smoke 3/3 OK
- Issue #6 auto-closed

### PR #10 · `PICTUREWEB_HOME` 环境变量

- Commit:`b791e5b6`
- Diff:7 行改 6 行(去掉 2 次 `os.path.normpath` 冗余)
- 兼容性:默认行为不变,环境变量可切换
- Issue #4 auto-closed

---

## 5. 7 个未修 Issue(待办)

| # | 标题 | 严重度 | 推荐修法 |
|---|---|---|---|
| 1 | start_hidden.vbs 路径写错 | 🔴 P0 | 用 `Scripting.FileSystemObject` 取脚本所在目录 |
| 2 | mavis CLI 损坏 | 🔴 P0 | 绕开 mavis CLI,直接 HTTP 调 matrix API |
| 3 | ADMIN_IPS 注释不一致 | 🟡 P1 | f-string 拼出错误消息 |
| 5 | server.py 350 行超铁律 | 🟡 P1 | 拆 handlers/search.py / favorites.py / ... 5 文件 |
| 7 | 前端无 fetch 错误处理 | 🟢 P2 | try/catch + 显示错误 |
| 8 | WRITE_PATHS 死列表 | 🟢 P2 | 删 OR 在 do_POST 顶部加统一检查 |

---

## 6. 下一步:Phase 6 自动化

### 6.1 目标

```
[GitHub Issue] ─label:auto-fix→ [scripts/auto_fix.py]
                                    ↓
                              启 Fixer agent(mavis task)
                                    ↓
                              改代码 + commit + push
                                    ↓
                              自动开 PR(Closes #N)
                                    ↓
                              GitHub Action 跑 smoke
                                    ↓
                              通过 → auto-merge
                              失败 → PR comment 留原因
                                    ↓
                              循环 ≤ 3 次
                                    ↓
                              第 3 次仍失败 → 飞书 @ 张勇
```

### 6.2 文件清单

```
PictureWebWorkflowtest/
├── scripts/
│   ├── auto_fix.py          # 派 Fixer agent
│   ├── auto_inspect.py      # 派 Inspector agent
│   ├── auto_tester.py       # 跑 smoke + 留 verdict
│   └── auto_dispatch.py     # cron 调度(每 30 分钟)
├── .github/
│   └── workflows/
│       └── smoke.yml        # PR 触发 → 跑 smoke
└── docs/
    └── 3agent-workflow.md   # 本文件
```

### 6.3 关键设计点

| 决定 | 选择 |
|---|---|
| 失败回流上限 | **3 次**(防止无限循环) |
| 端口隔离 | v2.5 = 8085 主,新版本 = 8086 预发(暂时单端口:port 8081 当前只有 1 个,够用) |
| Inspector 来源 | 机械的(`check_size.py` / `pyflakes`) + LLM 维度(用户主动 `/code-review`) |
| Fixer trigger | `auto-fix` label + cron 30 分钟扫一次 |
| Tester 通过标准 | `python tests/smoke.py` 3/3 OK + Python 语法无 error |
| Token 管理 | 不落盘,只在 sub-shell 进程内 `$env:GH_TOKEN`,退出即清 |

---

## 7. 复用本工作流到其他项目

`PictureWebWorkflowtest` 是教学样本。复用到 `_ArchitectLib/_index/` / `CanvasWeb-v2.5` / `TectonicWeb` 等的步骤:

1. 在目标项目根目录跑 `git init` + 写 `.gitignore` + 首次 commit
2. 改 `Inspector` 输出 issue 列表(项目特定问题)
3. 复用 `tests/smoke.py` 模板(改端点列表)
4. 用本文件的 PowerShell 脚本(改 `repo` + `username` 即可)
5. 第一次手动跑通后,迁移到 `scripts/auto_fix.py`

---

## 8. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-07-21 | 初版 · 记录 PR #9 + PR #10 实战 |
