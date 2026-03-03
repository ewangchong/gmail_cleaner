#!/usr/bin/env python3
import argparse
from email.utils import parseaddr
import os
from pathlib import Path
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime


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
    system = set()
    user = set()
    for line in out.splitlines():
        if not line.strip() or line.startswith("ID"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name = parts[1].strip()
        ltype = parts[2].strip().lower()
        if ltype == "system":
            system.add(name)
        else:
            user.add(name)
    return system, user


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
    _, user_labels = load_labels(account)
    if label in user_labels:
        return
    run(["gog", "gmail", "labels", "create", label, "--account", account, "--no-input"])


def batch_add_misc_label(account, ids, dry_run, batch_size=100):
    if dry_run or not ids:
        return 0, 0
    success = 0
    total_batches = (len(ids) + batch_size - 1) // batch_size
    for batch_idx, i in enumerate(range(0, len(ids), batch_size), start=1):
        batch = ids[i : i + batch_size]
        print(f"    Misc 打标批次: {batch_idx}/{total_batches} ({len(batch)} 封)")
        run(["gog", "gmail", "batch", "modify", *batch, "--add", "Misc", "--account", account, "--no-input"])
        success += len(batch)
    return success, 0


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

        ids = message_ids_for_label(account, label)
        ensure_label_exists(account, "Misc")
        misc_ok, _ = batch_add_misc_label(account, ids, dry_run=False)

        run(["gog", "gmail", "labels", "delete", label, "--account", account, "--no-input", "--force"])
        details.append((count, label, f"DELETED_MISC({misc_ok})"))
        deleted += 1

    return {"total": total, "kept": kept, "deleted": deleted, "failed": failed, "details": details}


def load_rules(path):
    rules = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            rtype, pattern, label = (x.strip() for x in parts)
            rules.append((rtype.lower(), pattern, pattern.lower(), label))
    return rules


def extract_sender_name(from_field):
    name, email = parseaddr(from_field or "")
    name = (name or "").strip().strip('"').strip("'")
    if name:
        return name
    if email and "@" in email:
        return email.split("@", 1)[0]
    return (from_field or "").strip()

def choose_label_for_message(msg, label_list, rules):
    msg_labels = set(msg["labels"])
    subject_l = (msg.get("subject") or "").lower()

    for rtype, raw_pattern, pattern_l, label in rules:
        if label not in label_list:
            continue
        if rtype == "subject" and pattern_l in subject_l:
            return label
        if rtype == "category" and raw_pattern in msg_labels:
            return label
    return ""


def sanitize_label_segment(text):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")
    return cleaned[:60] if cleaned else "misc"


def batch_add_label(account, label, ids, dry_run, batch_size=100):
    success = 0
    if dry_run or not ids:
        return success, 0
    total_batches = (len(ids) + batch_size - 1) // batch_size
    for batch_idx, i in enumerate(range(0, len(ids), batch_size), start=1):
        batch = ids[i : i + batch_size]
        print(f"    打标批次: label={label} {batch_idx}/{total_batches} ({len(batch)} 封)")
        run(["gog", "gmail", "batch", "modify", *batch, "--add", label, "--account", account, "--no-input"])
        success += len(batch)
    return success, 0


def batch_archive(account, ids, dry_run, batch_size=100):
    if dry_run or not ids:
        return
    total_batches = (len(ids) + batch_size - 1) // batch_size
    for batch_idx, i in enumerate(range(0, len(ids), batch_size), start=1):
        batch = ids[i : i + batch_size]
        print(f"    归档批次: {batch_idx}/{total_batches} ({len(batch)} 封)")
        run(["gog", "gmail", "batch", "modify", *batch, "--remove", "INBOX", "--account", account, "--no-input"])


def one_month_ago():
    now = datetime.now()
    y = now.year
    m = now.month - 1
    if m == 0:
        y -= 1
        m = 12
    day = min(now.day, [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return f"{y:04d}/{m:02d}/{day:02d}"


def main():
    ap = argparse.ArgumentParser(description="Clean inbox workflow")
    ap.add_argument("--account", help="Gmail 账号（可选，默认从 .env 读取 GMAIL_ACCOUNT）")
    ap.add_argument("--rules", default="config/rules.conf")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune-labels", action="store_true", help="扫描低频自定义标签（按 --min-label-count）")
    ap.add_argument("--apply-prune-labels", action="store_true", help="真正删除低频标签（需配合 --prune-labels）")
    ap.add_argument("--min-label-count", type=int, default=0, help="低频阈值：<=N 视为可删，默认 0")
    ap.add_argument("--max-inbox", type=int, default=None)
    ap.add_argument("--max-unread", type=int, default=None, help="Deprecated: use --max-inbox")
    args = ap.parse_args()
    account = load_account(args.account)

    if args.apply_prune_labels and not args.prune_labels:
        raise SystemExit("❌ 参数错误: --apply-prune-labels 需要与 --prune-labels 一起使用")

    print("== Gmail 一键整理开始 ==")
    print(f"账号: {account}")
    if args.dry_run:
        print("模式: DRY RUN")

    _, user_labels = load_labels(account)
    if args.prune_labels:
        print("")
        print("[0/2] 低频标签清理")
        prune_result = prune_low_count_labels(
            account,
            user_labels,
            min_count=args.min_label_count,
            dry_run=args.dry_run,
            apply=args.apply_prune_labels,
        )
        print(f"- 扫描标签数: {prune_result['total']}")
        print(f"- 保留标签数: {prune_result['kept']}")
        if args.apply_prune_labels:
            suffix = " (DRY RUN)" if args.dry_run else ""
            print(f"- 删除标签数: {prune_result['deleted']}{suffix}")
            print(f"- 删除失败数: {prune_result['failed']}")
        else:
            candidates = sum(1 for c, _, s in prune_result["details"] if s == "PRUNE_CANDIDATE")
            print(f"- 建议可删除标签数: {candidates} (默认仅建议，不自动删除)")
        print("标签明细:")
        for count, label, status in prune_result["details"]:
            count_text = "ERR/PARENT" if count < 0 else str(count)
            print(f"- [{status}] hits={count_text:>10} | {label}")
        if args.apply_prune_labels or args.dry_run:
            # Reload labels after potential deletion.
            _, user_labels = load_labels(account)

    label_list = sorted(user_labels)

    rules = load_rules(args.rules)
    inbox_query = "in:inbox"
    limit = args.max_inbox if args.max_inbox is not None else args.max_unread
    cmd = ["gog", "gmail", "messages", "search", inbox_query, "--account", account, "--plain"]
    cmd += ["--max", str(limit)] if limit else ["--all"]
    print("开始拉取收件箱邮件列表...")
    inbox_messages = parse_plain_messages(run(cmd).stdout)

    planned = defaultdict(list)
    created_labels = set()
    skipped_has_custom = 0

    label_set = set(label_list)

    total_inbox = len(inbox_messages)
    for idx, msg in enumerate(inbox_messages, start=1):
        if idx == 1 or idx % 25 == 0 or idx == total_inbox:
            print(f"  收件箱处理进度: {idx}/{total_inbox}")
        msg_labels = set(msg["labels"])
        if msg_labels.intersection(label_set):
            skipped_has_custom += 1
            continue

        chosen = choose_label_for_message(msg, label_list, rules)

        if not chosen:
            sender_name = sanitize_label_segment(extract_sender_name(msg.get("from", "")))
            chosen = f"Auto/{sender_name}"
            if chosen not in label_set and not args.dry_run:
                run(["gog", "gmail", "labels", "create", chosen, "--account", account, "--no-input"])
            if chosen not in label_set:
                created_labels.add(chosen)
                label_list.append(chosen)
                label_set.add(chosen)

        planned[chosen].append(msg["id"])

    add_success = 0
    add_failed = 0
    for label, ids in planned.items():
        s, f = batch_add_label(account, label, ids, args.dry_run)
        add_success += s
        add_failed += f

    print("")
    print("[1/2] 收件箱邮件智能打标")
    print(f"- 收件箱邮件扫描数: {len(inbox_messages)}")
    print(f"- 已有自定义标签跳过: {skipped_has_custom}")
    print(f"- 新建标签数: {len(created_labels)}")
    print(f"- 计划打标邮件数: {sum(len(v) for v in planned.values())}")
    print(f"- 打标成功数: {add_success}")
    print(f"- 打标失败数: {add_failed}")

    cutoff = one_month_ago()
    archive_query = f"in:inbox before:{cutoff}"
    print(f"开始拉取需归档邮件（before:{cutoff}）...")
    inbox_old = parse_plain_messages(
        run(["gog", "gmail", "messages", "search", archive_query, "--account", account, "--plain", "--all"]).stdout
    )
    archive_ids = [m["id"] for m in inbox_old]
    batch_archive(account, archive_ids, args.dry_run)

    print("")
    print("[2/2] 收件箱归档")
    print(f"- 截止日期(含此前): {cutoff}")
    print(f"- 归档邮件数: {len(archive_ids)}")

    print("")
    print("== 完成 ==")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
