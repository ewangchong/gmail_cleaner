# Gmail Helper (Inbox Clean Only)

当前包含 2 个脚本：

- `scripts/clean-inbox.py`：收件箱整理主流程
- `scripts/prune-rules.py`：手动清理 `rules.conf` 中无命中规则

## 前置条件

1. Python 3
2. 已安装并授权 `gog` CLI

```bash
gog gmail labels list --account your-email@gmail.com
```

3. 在项目根目录 `.env` 设置账号：

```env
GMAIL_ACCOUNT=your-email@gmail.com
```

4. 规则文件：`config/rules.conf`（格式：`subject:pattern:label`）

## 功能总览

### A. 收件箱整理（clean-inbox.py）

执行：

```bash
python3 scripts/clean-inbox.py
```

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

```bash
python3 scripts/prune-rules.py
```

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
