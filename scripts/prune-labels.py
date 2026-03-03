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


def parse_plain_messages(text):
    messages = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("ID"):
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        labels = [x.strip() for x in parts[5].split(",") if x.strip()]
        messages.append(
            {
                "id": parts[0].strip(),
                "thread": parts[1].strip(),
                "date": parts[2].strip(),
                "from": parts[3].strip(),
                "subject": parts[4].strip(),
                "labels": labels,
            }
        )
    return messages


def load_labels(account):
    out = run(["gog", "gmail", "labels", "list", "--account", account, "--plain"]).stdout
    user = set()
    for line in out.splitlines():
        if not line.strip() or line.startswith("ID"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name = parts[1].strip()
        ltype = parts[2].strip().lower()
        if ltype != "system":
            user.add(name)
    return user


def label_message_count(account, label):
    escaped = label.replace('"', '\\"')
    query = f'label:"{escaped}" -in:spam -in:trash'
    result = run(["gog", "gmail", "messages", "search", query, "--account", account, "--all", "--plain"])
    return len(parse_plain_messages(result.stdout))


def message_ids_for_label(account, label):
    escaped = label.replace('"', '\\"')
    query = f'label:"{escaped}" -in:spam -in:trash'
    result = run(["gog", "gmail", "messages", "search", query, "--account", account, "--all", "--plain"])
    return [m["id"] for m in parse_plain_messages(result.stdout)]


def ensure_label_exists(account, label):
    user_labels = load_labels(account)
    if label in user_labels:
        return
    run(["gog", "gmail", "labels", "create", label, "--account", account, "--no-input"])


def batch_add_misc_label(account, ids, dry_run, batch_size=100):
    if dry_run or not ids:
        return 0
    success = 0
    total_batches = (len(ids) + batch_size - 1) // batch_size
    for batch_idx, i in enumerate(range(0, len(ids), batch_size), start=1):
        batch = ids[i : i + batch_size]
        print(f"    Misc 打标批次: {batch_idx}/{total_batches} ({len(batch)} 封)")
        run(["gog", "gmail", "batch", "modify", *batch, "--add", "Misc", "--account", account, "--no-input"])
        success += len(batch)
    return success


def extract_hierarchy_parents(labels):
    parents = set()
    for label in labels:
        if "/" not in label:
            continue
        parts = label.split("/")
        for i in range(1, len(parts)):
            parents.add("/".join(parts[:i]))
    return parents


def prune_low_count_labels(account, user_labels, min_count, dry_run, apply):
    details = []
    deleted = 0
    failed = 0
    kept = 0

    labels_sorted = sorted(user_labels)
    parents = extract_hierarchy_parents(labels_sorted)
    total = len(labels_sorted)

    for idx, label in enumerate(labels_sorted, start=1):
        if idx == 1 or idx % 20 == 0 or idx == total:
            print(f"  标签扫描进度: {idx}/{total}")

        if label in parents:
            details.append((-1, label, "KEEP_PARENT"))
            kept += 1
            continue

        count = label_message_count(account, label)
        if count > min_count:
            details.append((count, label, "KEEP"))
            kept += 1
            continue

        if not apply or dry_run:
            details.append((count, label, "PRUNE_CANDIDATE"))
            continue

        try:
            ids = message_ids_for_label(account, label)
            ensure_label_exists(account, "Misc")
            misc_ok = batch_add_misc_label(account, ids, dry_run=False)
            run(["gog", "gmail", "labels", "delete", label, "--account", account, "--no-input", "--force"])
            details.append((count, label, f"DELETED_MISC({misc_ok})"))
            deleted += 1
        except RuntimeError:
            details.append((count, label, "DELETE_FAILED"))
            failed += 1

    return {"total": total, "kept": kept, "deleted": deleted, "failed": failed, "details": details}


def main():
    ap = argparse.ArgumentParser(description="Manual labels prune tool")
    ap.add_argument("--account", help="Gmail 账号（可选，默认从 .env 读取 GMAIL_ACCOUNT）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true", help="真正删除低频标签")
    ap.add_argument("--min-label-count", type=int, default=0, help="低频阈值：<=N 视为可删，默认 0")
    args = ap.parse_args()
    account = load_account(args.account)

    user_labels = load_labels(account)
    result = prune_low_count_labels(
        account,
        user_labels,
        min_count=args.min_label_count,
        dry_run=args.dry_run,
        apply=args.apply,
    )

    print("\n== Labels Prune ==")
    print(f"账号: {account}")
    print(f"- 扫描标签数: {result['total']}")
    print(f"- 保留标签数: {result['kept']}")
    if args.apply:
        suffix = " (DRY RUN)" if args.dry_run else ""
        print(f"- 删除标签数: {result['deleted']}{suffix}")
        print(f"- 删除失败数: {result['failed']}")
    else:
        candidates = sum(1 for c, _, s in result["details"] if s == "PRUNE_CANDIDATE")
        print(f"- 建议可删除标签数: {candidates} (默认仅建议，不自动删除)")

    print("\n标签明细:")
    for count, label, status in result["details"]:
        count_text = "ERR/PARENT" if count < 0 else str(count)
        print(f"- [{status}] hits={count_text:>10} | {label}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
