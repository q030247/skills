#!/usr/bin/env python3
"""Deterministic local half of flomo -> Markdown synchronization.

The AI/MCP client fetches memos and saves a normalized JSON file. This script
plans or applies local changes without storing credentials. It intentionally
parses only the index schema owned by this skill, using Python's standard
library so the bundled skill has no third-party dependency.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from knowledge_base_profile import discover_profile, load_profile, render_profile


ACTIONS = {"added", "updated", "deleted"}
SOURCE_FIELDS = {
    "source_url",
    "source_created_at",
    "source_updated_at",
    "updated",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if value == "[]":
        return []
    return value.strip('"\'')


def parse_index(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if not path.exists():
        return {
            "index_version": 1,
            "identity_key": "memo_id",
            "last_successful_sync_at": None,
        }, {}
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Index has no YAML frontmatter: {path}")
    lines = parts[1].splitlines()
    meta: dict[str, Any] = {}
    items: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    in_items = False
    in_attachments = False
    for line in lines:
        if line == "items:":
            in_items = True
            current = None
            continue
        if not in_items:
            match = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*)$", line)
            if match:
                meta[match.group(1)] = scalar(match.group(2))
            continue
        start = re.match(r"^  - memo_id:\s*(\S+)\s*$", line)
        if start:
            current = {"memo_id": start.group(1), "attachments": []}
            if current["memo_id"] in items:
                raise ValueError(f"Duplicate memo_id: {current['memo_id']}")
            items[current["memo_id"]] = current
            in_attachments = False
            continue
        if current is None:
            continue
        field = re.match(r"^    ([a-zA-Z_][\w-]*):\s*(.*)$", line)
        if field:
            key, value = field.groups()
            current[key] = [] if key == "attachments" and value.strip() == "" else scalar(value)
            in_attachments = key == "attachments" and value.strip() == ""
            continue
        attachment = re.match(r"^      -\s+(.+)$", line)
        if in_attachments and attachment:
            current.setdefault("attachments", []).append(attachment.group(1).strip())
    return meta, items


def yaml_value(value: Any) -> str:
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value == []:
        return "[]"
    return str(value)


STATE_LABELS = {
    "active": "活跃 / Active", "raw": "原始 / Raw", "present": "存在 / Present",
    "missing": "缺失 / Missing", "moved": "已迁移 / Moved", "deleted": "已删除标记 / Deleted",
    "synced": "已同步 / Synced", "added": "新增 / Added", "updated": "已更新 / Updated",
}


def state_label(value: Any) -> str:
    return STATE_LABELS.get(str(value or ""), f"待确认 / {value or 'Unknown'}")


def render_index(meta: dict[str, Any], items: dict[str, dict[str, Any]], today: str) -> str:
    ordered = sorted(items.values(), key=lambda x: x.get("source_created_at") or "", reverse=True)
    counts = {action: sum(i.get("sync_action") == action for i in ordered) for action in ACTIONS}
    front = [
        "---",
        "title: 浮墨同步索引",
        "summary: 记录浮墨笔记的新增、更新和删除状态，用于增量同步、去重和保持本地删除。",
        "tags: [浮墨, 同步, 去重]",
        "type: system",
        "status: active",
        "status_label: 活跃 / Active",
        "source: flomo",
        f"created: {meta.get('created') or today}",
        f"updated: {today}",
        "ai_generated: true",
        f"index_version: {meta.get('index_version') or 1}",
        "identity_key: memo_id",
        f"last_successful_sync_at: {yaml_value(meta.get('last_successful_sync_at'))}",
        "sync_policy:",
        "  existing_id: skip",
        "  missing_local_file: keep_deleted",
        "  source_updated: update_source_section",
        "  source_deleted: mark_only",
        "  restore: explicit_only",
        "items:",
    ]
    keys = [
        "source_url", "source_created_at", "source_updated_at", "local_path",
        "local_state", "local_state_label", "source_state", "source_state_label",
        "sync_status", "sync_status_label", "sync_action", "sync_action_label",
        "is_deleted", "deleted_at", "moved_at", "destination_type",
        "revision_count", "synced_at",
    ]
    for item in ordered:
        for state_key in ("local_state", "source_state", "sync_status", "sync_action"):
            item.setdefault(f"{state_key}_label", state_label(item.get(state_key)))
        front.append(f"  - memo_id: {item['memo_id']}")
        for key in keys:
            front.append(f"    {key}: {yaml_value(item.get(key))}")
        attachments = item.get("attachments") or []
        if attachments:
            front.append("    attachments:")
            front.extend(f"      - {p}" for p in attachments)
        else:
            front.append("    attachments: []")
    front.append("---")
    body = [
        "", "# 浮墨同步索引", "",
        "此文件是浮墨来源文件夹内的唯一同步状态台账。YAML 中的 `items` 是机器数据，正文表格用于人工核对。", "",
        "## 同步策略", "",
        "- 已登记且未更新的 ID：跳过。",
        "- 来源更新：保留旧版原文，再更新来源属性和“原始内容”章节。",
        "- 来源删除：保留本地文件并标记。",
        "- 本地删除：保留历史 ID，不自动恢复。", "",
        "## 状态统计", "",
        "| 状态 | 数量 |", "|---|---:|",
        f"| 新增 | {counts['added']} |",
        f"| 更新 | {counts['updated']} |",
        f"| 已删除 | {counts['deleted']} |", "",
        "## 已同步笔记", "",
        "| 创建时间 | flomo ID | 本地笔记 | 同步动作 | 删除标记 |",
        "|---|---|---|---|---|",
    ]
    labels = {"added": "新增", "updated": "更新", "deleted": "已删除"}
    for item in ordered:
        created = (item.get("source_created_at") or "")[:16].replace("T", " ")
        local = Path(item.get("local_path") or "").with_suffix("").as_posix()
        body.append(
            f"| {created} | `{item['memo_id']}` | [[{local}]] | "
            f"{labels.get(item.get('sync_action'), '待确认')} | "
            f"{'是' if item.get('is_deleted') else '否'} |"
        )
    body += ["", "## 维护说明", "", "- 不删除历史 ID。", "- 自动同步时保持 YAML、统计和表格一致。", ""]
    return "\n".join(front + body)


def load_memos(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    memos = data if isinstance(data, list) else data.get("memos", [])
    if not isinstance(memos, list):
        raise ValueError("Input must be a memo array or an object with a memos array")
    seen: set[str] = set()
    for memo in memos:
        memo_id = memo.get("id") or memo.get("memo_id")
        if not memo_id:
            raise ValueError("Every memo needs id or memo_id")
        if memo_id in seen:
            raise ValueError(f"Duplicate candidate memo_id: {memo_id}")
        seen.add(memo_id)
        memo["id"] = memo_id
        if memo.get("content_truncated"):
            raise ValueError(f"Memo {memo_id} is truncated; fetch full content first")
    return memos


def title_from(memo: dict[str, Any]) -> str:
    content = re.sub(r"[#*_`<>]", "", memo.get("content") or "")
    line = next((x.strip() for x in content.splitlines() if x.strip()), "")
    line = re.sub(r"https?://\S+", "", line).strip(" ｜:：-—")
    return (line[:36].strip() or f"浮墨笔记-{memo['id'][-6:]}")


def safe_filename(text: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\n\r]", "-", text).strip(" .-") or "浮墨笔记"


def note_path(target_dir: Path, memo: dict[str, Any]) -> Path:
    stamp = datetime.fromisoformat(memo["created_at"]).strftime("%Y-%m-%d-%H%M")
    return target_dir / f"{stamp}-{safe_filename(title_from(memo))}.md"


def render_note(memo: dict[str, Any], rel_path: str, include_confidentiality: bool = False) -> str:
    title = title_from(memo)
    created = memo["created_at"][:10]
    updated = memo.get("updated_at", memo["created_at"])[:10]
    tags = json.dumps(memo.get("tags") or [], ensure_ascii=False)
    confidentiality = "confidentiality: personal\n" if include_confidentiality else ""
    return f"""---
title: {title}
summary: 浮墨原始记录，内容待整理确认。
tags: {tags}
type: inbox
status: raw
status_label: 原始 / Raw
source: flomo
source_id: {memo['id']}
source_url: {memo.get('url', '')}
source_created_at: {memo['created_at']}
source_updated_at: {memo.get('updated_at', memo['created_at'])}
created: {created}
updated: {updated}
{confidentiality}ai_generated: false
---

# {title}

## 原始内容

{memo.get('content', '')}

## 它支持什么决策或输出

- 待确认

## 我的理解

- 待整理

## 处理结果

- 建议归属：待确认 / Needs confirmation
- 归档审批：未创建 / Not created
"""


def update_note(path: Path, memo: dict[str, Any], preserve_history: bool = True) -> str:
    text = path.read_text(encoding="utf-8")
    replacements = {
        "source_url": memo.get("url", ""),
        "source_updated_at": memo.get("updated_at", memo["created_at"]),
        "updated": memo.get("updated_at", memo["created_at"])[:10],
    }
    for key, value in replacements.items():
        pattern = rf"(?m)^{re.escape(key)}:.*$"
        if re.search(pattern, text):
            text = re.sub(pattern, f"{key}: {value}", text, count=1)
    pattern = r"(?ms)^## 原始内容\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Cannot safely find original-content section: {path}")
    previous = match.group(1).strip()
    current = memo.get("content", "")
    source = f"## 原始内容\n\n{current}\n\n"
    text = re.sub(pattern, source, text, count=1)
    if preserve_history and previous != current.strip():
        stamp = memo.get("updated_at", memo["created_at"])
        history_entry = f"### {stamp}\n\n{previous}\n\n"
        marker = r"(?m)^## 来源更新历史\s*$"
        if re.search(marker, text):
            text = re.sub(marker, "## 来源更新历史\n\n" + history_entry.rstrip(), text, count=1)
        else:
            text = text.rstrip() + "\n\n## 来源更新历史\n\n" + history_entry
    return text


def build_plan(
    root: Path,
    target: Path,
    items: dict[str, dict[str, Any]],
    memos: list[dict[str, Any]],
    restore: bool,
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for item in items.values():
        local = root / str(item.get("local_path") or "")
        if not local.is_file() and item.get("local_state") not in {"missing", "moved"}:
            plan.append({"action": "mark_local_deleted", "id": item["memo_id"], "path": item.get("local_path")})
    for memo in memos:
        old = items.get(memo["id"])
        if not old:
            path = note_path(target, memo)
            plan.append({"action": "add", "id": memo["id"], "path": path.relative_to(root).as_posix()})
        elif old.get("local_state") == "missing":
            if restore:
                plan.append({"action": "restore", "id": memo["id"], "path": old.get("local_path")})
            else:
                plan.append({"action": "skip_deleted", "id": memo["id"], "path": old.get("local_path")})
        elif memo.get("source_state") == "deleted" or memo.get("deleted") is True:
            plan.append({"action": "mark_source_deleted", "id": memo["id"], "path": old.get("local_path")})
        elif (memo.get("updated_at") or "") > (old.get("source_updated_at") or ""):
            plan.append({"action": "update", "id": memo["id"], "path": old.get("local_path")})
        else:
            plan.append({"action": "skip", "id": memo["id"], "path": old.get("local_path")})
    return plan


def render_report(result: dict[str, Any], index_path: str, target_dir: str, compact: bool) -> str:
    counts = result["counts"]
    rows = [
        ("新增", counts.get("add", 0) + counts.get("restore", 0)),
        ("更新", counts.get("update", 0)),
        ("跳过", counts.get("skip", 0) + counts.get("skip_deleted", 0)),
        ("删除保持", counts.get("mark_local_deleted", 0) + counts.get("mark_source_deleted", 0)),
        ("失败", 0),
    ]
    mode = "精简" if compact else "完整"
    lines = [
        "---",
        f"title: {result['timestamp'][:16].replace('T', ' ')} 浮墨增量同步报告",
        f"summary: 浮墨增量同步完成，本批候选 {result['candidate_count']} 条。",
        "tags: [浮墨, 同步, 执行报告]",
        "type: system",
        "status: done",
        "source: ai",
        f"created: {result['timestamp'][:10]}",
        f"updated: {result['timestamp'][:10]}",
        "ai_generated: true",
        "---", "",
        f"# {result['timestamp'][:16].replace('T', ' ')} 浮墨增量同步报告", "",
        "## 执行概览", "",
        f"- 执行时间：{result['timestamp']}",
        f"- 报告类型：{mode}",
        f"- 目标目录：`{target_dir}`",
        f"- 同步索引：`{index_path}`",
        f"- 本批候选：{result['candidate_count']}", "",
        "## 结果", "", "| 项目 | 数量 |", "|---|---:|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in rows)
    if not compact:
        lines += ["", "## 操作明细", ""]
        for op in result["operations"]:
            detail = op.get("new_path") or op.get("path") or ""
            lines.append(f"- `{op['action']}` `{op['id']}` → `{detail}`")
    lines += [
        "", "## 安全检查", "",
        "- 未向 flomo 写入内容。",
        "- 未物理删除本地 Markdown。",
        "- 来源更新时保留旧版原始内容。",
        "- 报告与索引在同一批本地事务中写入。", "",
    ]
    return "\n".join(lines)


def atomic_commit(writes: dict[Path, str]) -> None:
    """Stage every text file beside its target, then replace all targets."""
    staged: list[tuple[Path, Path]] = []
    try:
        for target, content in writes.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            handle, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
            temp = Path(temp_name)
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            staged.append((temp, target))
        for temp, target in staged:
            os.replace(str(temp), str(target))
    finally:
        for temp, _ in staged:
            if temp.exists():
                temp.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan/apply local flomo Markdown synchronization")
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--input", type=Path, help="Normalized memo JSON from MCP")
    parser.add_argument("--target-dir")
    parser.add_argument("--index")
    parser.add_argument("--profile")
    parser.add_argument("--report", help="Markdown report path inside vault")
    parser.add_argument("--result-json", type=Path, help="Optional machine-readable result JSON")
    parser.add_argument("--configure-only", action="store_true")
    parser.add_argument("--restore-deleted", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Write changes; default is dry-run")
    args = parser.parse_args()

    root = args.vault.resolve()
    discovered = discover_profile(root)
    profile_rel = args.profile or discovered["profile_path"]
    profile_path = (root / profile_rel).resolve()
    profile_exists = profile_path.is_file()
    profile = load_profile(profile_path) if profile_exists else discovered
    profile_changed = (not profile_exists) or profile.get("knowledge_base_fingerprint") != discovered["knowledge_base_fingerprint"]
    if profile_changed:
        profile = discovered
    target_rel = args.target_dir or profile["target_dir"]
    index_rel = args.index or profile["index_path"]
    target = (root / target_rel).resolve()
    index_path = (root / index_rel).resolve()
    report_dir = (root / profile["report_dir"]).resolve()
    paths = [target, index_path, profile_path, report_dir]
    if any(root != path and root not in path.parents for path in paths):
        raise SystemExit("Target, index, profile, and report must stay inside vault")
    if args.configure_only and not args.apply:
        print(render_profile(profile, now_iso()[:10]))
        return 0
    if args.configure_only and args.apply:
        atomic_commit({profile_path: render_profile(profile, now_iso()[:10])})
        print(json.dumps({"mode": "configure", "profile": profile_rel}, ensure_ascii=False))
        return 0
    if args.input is None:
        raise SystemExit("--input is required unless --configure-only is used")
    meta, items = parse_index(index_path)
    memos = load_memos(args.input)
    if len(memos) > int(profile.get("batch_limit", 50)):
        raise SystemExit(f"Refusing more than {profile.get('batch_limit', 50)} memos in one batch")
    plan = build_plan(root, target, items, memos, args.restore_deleted)
    if profile_changed:
        plan.insert(0, {"action": "configure_profile", "id": "profile", "path": profile_rel})
    timestamp = now_iso()
    by_id = {m["id"]: m for m in memos}
    result = {
        "mode": "apply" if args.apply else "dry-run",
        "timestamp": timestamp,
        "candidate_count": len(memos),
        "counts": {a: sum(op["action"] == a for op in plan) for a in sorted({op["action"] for op in plan})},
        "operations": plan,
    }

    if args.apply:
        next_items = copy.deepcopy(items)
        writes: dict[Path, str] = {}
        for op in plan:
            if op["action"] == "configure_profile":
                continue
            item = next_items.get(op["id"])
            memo = by_id.get(op["id"])
            item = items.get(op["id"])
            if op["action"] == "mark_local_deleted":
                item = next_items[op["id"]]
                item.update(local_state="missing", sync_action="deleted", is_deleted=True, deleted_at=timestamp)
            elif op["action"] in {"add", "restore"}:
                path = root / op["path"]
                writes[path] = render_note(memo, op["path"], bool(profile.get("include_confidentiality", False)))
                next_items[memo["id"]] = {
                    "memo_id": memo["id"], "source_url": memo.get("url", ""),
                    "source_created_at": memo["created_at"],
                    "source_updated_at": memo.get("updated_at", memo["created_at"]),
                    "local_path": op["path"], "local_state": "present", "local_state_label": "存在 / Present",
                    "source_state": "present", "source_state_label": "存在 / Present",
                    "sync_status": "synced", "sync_status_label": "已同步 / Synced",
                    "sync_action": "added", "sync_action_label": "新增 / Added", "is_deleted": False,
                    "deleted_at": None, "moved_at": None, "destination_type": None,
                    "revision_count": 0, "synced_at": timestamp, "attachments": [],
                }
            elif op["action"] == "update":
                path = root / op["path"]
                item = next_items[op["id"]]
                writes[path] = update_note(path, memo, bool(profile.get("preserve_source_history", True)))
                item.update(source_url=memo.get("url", ""), source_updated_at=memo.get("updated_at", memo["created_at"]), sync_action="updated", sync_action_label="已更新 / Updated", synced_at=timestamp)
                item["revision_count"] = int(item.get("revision_count") or 0) + 1
            elif op["action"] == "mark_source_deleted":
                item = next_items[op["id"]]
                item.update(source_state="deleted", source_state_label="已删除标记 / Deleted", sync_action="deleted", sync_action_label="已删除标记 / Deleted", is_deleted=True, deleted_at=timestamp, synced_at=timestamp)
        meta["last_successful_sync_at"] = timestamp
        writes[index_path] = render_index(meta, next_items, timestamp[:10])
        if profile_changed:
            writes[profile_path] = render_profile(profile, timestamp[:10])
        report_name = f"{timestamp[:10]}-{timestamp[11:13]}{timestamp[14:16]}{timestamp[17:19]}-浮墨增量同步报告.md"
        report_path = (root / args.report).resolve() if args.report else report_dir / report_name
        if root != report_path and root not in report_path.parents:
            raise SystemExit("Report must stay inside vault")
        substantive = {"add", "restore", "update", "mark_local_deleted", "mark_source_deleted"}
        compact = not any(op["action"] in substantive for op in plan)
        writes[report_path] = render_report(result, index_rel, target_rel, compact)
        atomic_commit(writes)

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.result_json:
        args.result_json.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
