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

```bash
gog gmail labels list --account your-email@gmail.com
```

## Quick Start (1 minute)

1. Clone this repo

```bash
git clone https://github.com/ewangchong/gmail_cleaner.git
cd gmail_cleaner
```

2. Create `.env` in project root

```env
GMAIL_ACCOUNT=your-email@gmail.com
```

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

```bash
python3 scripts/clean-inbox.py
```

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

```bash
python3 scripts/prune-rules.py
```

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
