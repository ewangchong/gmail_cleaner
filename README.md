<<<<<<< HEAD
# gmail_cleaner

A lightweight Gmail cleanup toolkit powered by [`gog`](https://github.com/julien040).

中文文档: [README_zh.md](README_zh.md)

It focuses on 3 practical tasks:
- Clean inbox with rule-based labeling + auto fallback labels
- Prune unused `subject` rules from `config/rules.conf`
- Prune low-frequency custom Gmail labels safely

## Features

- Rule-based labeling (`subject:pattern:label`)
- Auto-label fallback: `Auto/<sender-name>` when no rule matches
- Optional archive for inbox emails older than 1 month
- Safe label pruning flow: add `Misc` first, then delete old labels
- Dry-run mode for risky operations

## Requirements

- Python 3.8+
- `gog` CLI installed and authenticated
- You must complete `gog` Gmail auth before running any script

Authenticate first:

```bash
gog auth add your-email@gmail.com --services gmail
```

Then verify `gog` is ready:
=======
# Gmail Helper (Inbox Clean Only)

当前包含 2 个脚本：

- `scripts/clean-inbox.py`：收件箱整理主流程
- `scripts/prune-rules.py`：手动清理 `rules.conf` 中无命中规则

## 前置条件

1. Python 3
2. 已安装并授权 `gog` CLI
>>>>>>> origin/main

```bash
gog gmail labels list --account your-email@gmail.com
```

<<<<<<< HEAD
## Quick Start (1 minute)

1. Clone this repo

```bash
git clone https://github.com/ewangchong/gmail_cleaner.git
cd gmail_cleaner
```

2. Create `.env` in project root
=======
3. 在项目根目录 `.env` 设置账号：
>>>>>>> origin/main

```env
GMAIL_ACCOUNT=your-email@gmail.com
```

<<<<<<< HEAD
3. Authenticate `gog` for Gmail (required)

```bash
gog auth add your-email@gmail.com --services gmail
gog gmail labels list --account your-email@gmail.com
```

4. Run a safe dry-run

```bash
python3 scripts/clean-inbox.py --dry-run --max-inbox 100
```

## Rule File Format

Default file: `config/rules.conf`

Format:

```text
subject:<pattern>:<label>
```

Example:

```text
subject:Invoice:Admin/Invoices
subject:Golf:Sports/Golf
subject:Offer:Important/Personal
```

Notes:
- Only `subject` rules are used for matching in current scripts.
- Matching is case-insensitive substring matching.

## Scripts

### 1) `clean-inbox.py`

Main workflow script.
=======
4. 规则文件：`config/rules.conf`（格式：`subject:pattern:label`）

## 功能总览

### A. 收件箱整理（clean-inbox.py）

执行：
>>>>>>> origin/main

```bash
python3 scripts/clean-inbox.py
```

<<<<<<< HEAD
Arguments:
- `--account`: override account (otherwise from `.env`)
- `--rules`: rules file path (default `config/rules.conf`)
- `--dry-run`: preview changes without modifying Gmail
- `--max-inbox N`: process only first `N` inbox messages
- `--max-unread N`: deprecated alias of `--max-inbox`
- `--prune-labels`: scan low-frequency custom labels before inbox processing
- `--apply-prune-labels`: actually delete low-frequency labels (must combine with `--prune-labels`)
- `--min-label-count N`: threshold for low-frequency labels, `hits <= N` is prunable

Workflow:
1. Optional custom-label pruning
2. Fetch inbox messages
3. Skip emails that already have any custom label
4. Apply first matched `subject` rule
5. If no match, create/use `Auto/<sender-name>`
6. Archive emails matching `in:inbox before:<1 month ago>`

### 2) `prune-rules.py`

Remove dead `subject` rules (zero hit count).
=======
支持参数：

- `--account`：可选，默认从 `.env` 读取 `GMAIL_ACCOUNT`
- `--rules`：规则文件路径，默认 `config/rules.conf`
- `--dry-run`：预演模式，不实际改动
- `--max-inbox N`：只处理前 N 封收件箱邮件
- `--max-unread N`：兼容旧参数，等价 `--max-inbox`
- `--prune-labels`：扫描低频自定义标签
- `--apply-prune-labels`：真正删除低频标签（需配合 `--prune-labels`）
- `--min-label-count N`：低频阈值，`<= N` 视为低频（默认 0）

主流程规则：

1. 可选低频标签清理（仅当传 `--prune-labels`）
2. 拉取 `in:inbox` 邮件列表
3. 逐封邮件打标签：
   - 若邮件已带任一自定义标签：跳过
   - 否则仅按标题匹配 `rules.conf` 的 `subject` 规则
   - 若标题未命中：创建/使用 `Auto/<sender name>`
     - `sender name` 优先取发件人显示名
     - 无显示名则回退邮箱名前缀
4. 归档 `in:inbox before:<1个月前>` 邮件（移除 `INBOX`）

低频标签清理规则：

- 只扫描：`--prune-labels`
- 真删除：`--prune-labels --apply-prune-labels`
- 真删除时，对低频标签（`hits <= min-label-count`）执行：
  1. 先给该标签下邮件加 `Misc`
  2. 再删除旧标签
- 若 `Misc` 打标失败，则不会删除旧标签
- 父级层级标签（如 `A` 是 `A/B` 的父级）不会删除

### B. 规则清理（prune-rules.py）

执行：
>>>>>>> origin/main

```bash
python3 scripts/prune-rules.py
```

<<<<<<< HEAD
Arguments:
- `--account`
- `--rules`
- `--dry-run`
- `--apply`: actually remove rules with `hits=0`

### 3) `prune-labels.py`

Remove low-frequency custom labels.

```bash
python3 scripts/prune-labels.py
```

Arguments:
- `--account`
- `--dry-run`
- `--apply`: actually delete labels
- `--min-label-count N`: `hits <= N` is prunable

Safety behavior:
- System labels are never touched
- Parent hierarchy labels (for example `A` when `A/B` exists) are kept
- On apply: add `Misc` to emails first, then delete old label
- If a deletion step fails, status is reported as `DELETE_FAILED`

## Common Commands

```bash
# Inbox clean (dry-run)
python3 scripts/clean-inbox.py --dry-run

# Inbox clean (process at most 200 emails)
python3 scripts/clean-inbox.py --max-inbox 200

# Scan low-frequency labels only
python3 scripts/prune-labels.py --min-label-count 2

# Delete low-frequency labels
python3 scripts/prune-labels.py --apply --min-label-count 2

# Scan removable rules
python3 scripts/prune-rules.py

# Delete rules with zero hits
python3 scripts/prune-rules.py --apply
```

Use a temporary account override:

```bash
python3 scripts/clean-inbox.py --account another@gmail.com
python3 scripts/prune-rules.py --account another@gmail.com
python3 scripts/prune-labels.py --account another@gmail.com
```

## Privacy & Safety

- Never commit your real account details in `.env`
- Keep `.env` local only (already ignored by git in typical setup)
- Always run with `--dry-run` first
- Review scan output before using `--apply`
- Scripts are fail-fast: any `gog` command error stops execution

## Troubleshooting

- `❌ 未提供账号...`: pass `--account` or set `GMAIL_ACCOUNT` in `.env`
- `gog` auth/permission errors: re-run a simple `gog` Gmail command to verify login
- Unexpected labeling: run smaller batch with `--max-inbox 20 --dry-run` and inspect results
=======
支持参数：

- `--account`：可选，默认从 `.env` 读取 `GMAIL_ACCOUNT`
- `--rules`：规则文件路径，默认 `config/rules.conf`
- `--dry-run`：预演模式
- `--apply`：真正删除无命中规则

规则清理逻辑：

- 仅处理 `subject` 规则
- 对每条规则查询 `-in:spam -in:trash` 的命中数（hits）
- `hits = 0` 标记为 `PRUNE`
- 输出每条规则明细：`[KEEP/PRUNE] hits=... | subject:... -> ...`

## 常用命令

```bash
# 1) 收件箱整理（预演）
python3 scripts/clean-inbox.py --dry-run

# 2) 收件箱整理（限量 200 封）
python3 scripts/clean-inbox.py --max-inbox 200

# 3) 低频标签仅扫描（阈值 <= 2）
python3 scripts/clean-inbox.py --prune-labels --min-label-count 2

# 4) 低频标签执行删除（先打 Misc 再删）
python3 scripts/clean-inbox.py --prune-labels --apply-prune-labels --min-label-count 2

# 5) 规则仅扫描
python3 scripts/prune-rules.py

# 6) 规则执行删除（仅删 hits=0）
python3 scripts/prune-rules.py --apply
```

可选：临时覆盖账号  
`python3 scripts/clean-inbox.py --account another@gmail.com`  
`python3 scripts/prune-rules.py --account another@gmail.com`

## 安全建议

- 第一次先用 `--dry-run`
- 真删除前先跑“仅扫描”看结果
- `rules.conf` 建议纳入版本管理，方便回滚
- 当前脚本为 fail-fast：任何 `gog` 命令失败会立即报错并停止
>>>>>>> origin/main
