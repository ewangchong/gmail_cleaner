#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import subprocess
import sys


def run(cmd, check=True):
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        err = (result.stderr or "").strip()
        out = (result.stdout or "").strip()
        raise RuntimeError(err or out or f"Command failed: {' '.join(cmd)}")
    return result


def load_account(account_arg):
    if account_arg:
        return account_arg

    env_account = os.environ.get("GMAIL_ACCOUNT", "").strip()
    if env_account:
        return env_account

    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "GMAIL_ACCOUNT":
                v = v.strip().strip('"').strip("'")
                if v:
                    return v

    raise SystemExit("❌ 未提供账号。请传 --account 或在 .env 中设置 GMAIL_ACCOUNT")


def parse_plain_message_ids(text):
    ids = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("ID"):
            continue
        parts = line.split("\t")
        if parts:
            msg_id = parts[0].strip()
            if msg_id:
                ids.append(msg_id)
    return ids


def rule_match_count(account, pattern):
    escaped = pattern.replace('"', '\\"')
    query = f'subject:"{escaped}" -in:spam -in:trash'
    result = run(["gog", "gmail", "messages", "search", query, "--account", account, "--all", "--plain"])
    return len(parse_plain_message_ids(result.stdout))


def prune_subject_rules(account, rules_path, dry_run, apply):
    if not os.path.exists(rules_path):
        raise RuntimeError(f"规则文件不存在: {rules_path}")

    with open(rules_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    kept_lines = []
    details = []

    parsed_subject_rules = []
    for raw in lines:
        line = raw.strip()
        if not line:
            kept_lines.append(raw)
            continue

        parts = line.split(":", 2)
        if len(parts) != 3:
            kept_lines.append(raw)
            continue

        rtype, pattern, label = (x.strip() for x in parts)
        if rtype.lower() != "subject":
            kept_lines.append(raw)
            continue

        parsed_subject_rules.append((raw, pattern, label))

    total = len(parsed_subject_rules)
    for idx, (raw, pattern, label) in enumerate(parsed_subject_rules, start=1):
        if idx == 1 or idx % 20 == 0 or idx == total:
            print(f"  规则扫描进度: {idx}/{total}")

        count = rule_match_count(account, pattern)
        if count != 0:
            kept_lines.append(raw)
            details.append((count, pattern, label, "KEEP"))
        else:
            details.append((count, pattern, label, "PRUNE"))

    prunable = sum(1 for x in details if x[3] == "PRUNE")
    kept = len(details) - prunable

    if apply and not dry_run and prunable > 0:
        with open(rules_path, "w", encoding="utf-8") as f:
            f.writelines(kept_lines)

    return len(details), kept, prunable, details


def main():
    ap = argparse.ArgumentParser(description="Manual subject-rules prune tool")
    ap.add_argument("--account", help="Gmail 账号（可选，默认从 .env 读取 GMAIL_ACCOUNT）")
    ap.add_argument("--rules", default="config/rules.conf")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true", help="真正删除无命中规则")
    args = ap.parse_args()
    account = load_account(args.account)

    total, kept, prunable, details = prune_subject_rules(
        account, args.rules, dry_run=args.dry_run, apply=args.apply
    )

    print("\n== Rules Prune ==")
    print(f"账号: {account}")
    print(f"- 扫描规则数: {total}")
    print(f"- 命中规则数: {kept}")
    if args.apply:
        suffix = " (DRY RUN)" if args.dry_run else ""
        print(f"- 实际删除规则数: {prunable}{suffix}")
    else:
        print(f"- 建议可删除规则数: {prunable} (默认仅建议，不自动删除)")

    print("\n规则明细:")
    for count, pattern, label, status in details:
        print(f"- [{status}] hits={count:>4} | subject:{pattern} -> {label}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
