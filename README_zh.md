# gmail_cleaner

基于 [`gog`](https://github.com/julien040) 的轻量 Gmail 清理工具集。

English version: [README.md](README.md)

主要解决 3 个实际问题：
- 用规则为收件箱打标签，并在未命中时自动回退标签
- 清理 `config/rules.conf` 中无命中的 `subject` 规则
- 安全清理低频自定义 Gmail 标签

## 功能

- 规则驱动打标（`subject:pattern:label`）
- 无规则命中时自动创建/使用 `Auto/<sender-name>`
- 可选归档：将 1 个月前的收件箱邮件移出 `INBOX`
- 安全标签清理流程：先打 `Misc` 再删旧标签
- 支持 `dry-run` 预演，降低误操作风险

## 环境要求

- Python 3.8+
- 已安装并完成 `gog` 登录授权
- 运行任何脚本前，必须先完成 `gog` Gmail 授权

先完成授权：

```bash
gog auth add your-email@gmail.com --services gmail
```

再验证 `gog` 可用：

```bash
gog gmail labels list --account your-email@gmail.com
```

## 1 分钟快速开始

1. 克隆仓库

```bash
git clone https://github.com/ewangchong/gmail_cleaner.git
cd gmail_cleaner
```

2. 在项目根目录创建 `.env`

```env
GMAIL_ACCOUNT=your-email@gmail.com
```

3. 先完成 `gog` Gmail 授权（必需）

```bash
gog auth add your-email@gmail.com --services gmail
gog gmail labels list --account your-email@gmail.com
```

4. 再执行安全预演

```bash
python3 scripts/clean-inbox.py --dry-run --max-inbox 100
```

## 规则文件格式

默认路径：`config/rules.conf`

格式：

```text
subject:<pattern>:<label>
```

示例：

```text
subject:Invoice:Admin/Invoices
subject:Golf:Sports/Golf
subject:Offer:Important/Personal
```

说明：
- 当前脚本仅使用 `subject` 类型规则参与匹配。
- 匹配方式为不区分大小写的子串匹配。

## 脚本说明

### 1) `clean-inbox.py`

主流程脚本。

```bash
python3 scripts/clean-inbox.py
```

参数：
- `--account`：覆盖账号（默认从 `.env` 读取）
- `--rules`：规则文件路径（默认 `config/rules.conf`）
- `--dry-run`：预演模式，不实际修改 Gmail
- `--max-inbox N`：仅处理前 `N` 封收件箱邮件
- `--max-unread N`：已废弃，等价于 `--max-inbox`
- `--prune-labels`：收件箱处理前先扫描低频自定义标签
- `--apply-prune-labels`：真正删除低频标签（必须和 `--prune-labels` 一起使用）
- `--min-label-count N`：低频阈值，`hits <= N` 视为可删

流程：
1. 可选：先清理低频标签
2. 拉取收件箱邮件
3. 已有任意自定义标签的邮件直接跳过
4. 应用首条命中的 `subject` 规则
5. 未命中则创建/使用 `Auto/<sender-name>`
6. 归档 `in:inbox before:<1 month ago>` 的邮件

### 2) `prune-rules.py`

删除无命中的 `subject` 规则（`hits=0`）。

```bash
python3 scripts/prune-rules.py
```

参数：
- `--account`
- `--rules`
- `--dry-run`
- `--apply`：真正删除 `hits=0` 的规则

### 3) `prune-labels.py`

删除低频自定义标签。

```bash
python3 scripts/prune-labels.py
```

参数：
- `--account`
- `--dry-run`
- `--apply`：真正删除标签
- `--min-label-count N`：`hits <= N` 视为可删

安全行为：
- 不处理系统标签
- 层级父标签保留（如 `A/B` 存在时保留 `A`）
- 执行删除时：先给邮件加 `Misc`，再删旧标签
- 删除失败会显示 `DELETE_FAILED`

## 常用命令

```bash
# 收件箱清理（预演）
python3 scripts/clean-inbox.py --dry-run

# 收件箱清理（最多处理 200 封）
python3 scripts/clean-inbox.py --max-inbox 200

# 仅扫描低频标签
python3 scripts/prune-labels.py --min-label-count 2

# 删除低频标签
python3 scripts/prune-labels.py --apply --min-label-count 2

# 扫描可删规则
python3 scripts/prune-rules.py

# 删除零命中规则
python3 scripts/prune-rules.py --apply
```

临时覆盖账号：

```bash
python3 scripts/clean-inbox.py --account another@gmail.com
python3 scripts/prune-rules.py --account another@gmail.com
python3 scripts/prune-labels.py --account another@gmail.com
```

## 隐私与安全

- 不要把真实账号信息提交到仓库
- `.env` 仅保留本地（常见配置下会被 git 忽略）
- 建议先执行 `--dry-run`
- 使用 `--apply` 前先确认扫描输出
- 脚本为 fail-fast：任一 `gog` 命令失败都会停止

## 常见问题

- `❌ 未提供账号...`：传入 `--account` 或在 `.env` 设置 `GMAIL_ACCOUNT`
- `gog` 鉴权/权限报错：先用简单 Gmail 命令确认登录状态
- 打标结果异常：先用 `--max-inbox 20 --dry-run` 小批量排查
