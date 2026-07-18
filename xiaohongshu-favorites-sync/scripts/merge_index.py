#!/usr/bin/env python3
"""Preview or atomically merge normalized records into the index AI region."""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from common import UNKNOWN, atomic_write, dedupe_url, dump_json, load_json, records_from_payload

AI_RE = re.compile(r"(<!-- AI:START -->\s*)(.*?)(\s*<!-- AI:END -->)", re.S)
FENCE_RE = re.compile(r"^```(?:yaml|json)?\s*(.*?)\s*```$", re.S)


def parse_index(text: str):
    match = AI_RE.search(text)
    if not match:
        raise ValueError("同步索引缺少 AI:START/AI:END 标记")
    body = match.group(2).strip()
    fenced = FENCE_RE.match(body)
    payload = fenced.group(1).strip() if fenced else body
    if payload == "items: []" or not payload:
        data = {"items": []}
    else:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("AI 区域必须是脚本生成的 JSON/YAML 兼容结构") from error
    return match, records_from_payload(data)


def key(item):
    source_id = str(item.get("source_id", "")).strip()
    if source_id and source_id != UNKNOWN:
        return "id:" + source_id
    url = str(item.get("source_url", "")).strip()
    return "url:" + dedupe_url(url) if url and url != UNKNOWN else ""


def merge(existing, incoming):
    by_key = {key(item): dict(item) for item in existing if key(item)}
    result = []
    counts = {"新增": 0, "更新候选": 0, "跳过": 0, "跳过（已删除）": 0, "待确认": 0}
    for item in incoming:
        item = dict(item)
        item_key = key(item)
        if not item_key:
            item["sync_status"] = "待确认"
            counts["待确认"] += 1
            result.append(item)
            continue
        old = by_key.get(item_key)
        if old and str(old.get("source_status", old.get("sync_status", ""))) in ("已删除", "deleted"):
            item = old
            item["sync_status"] = "跳过（已删除）"
            counts["跳过（已删除）"] += 1
        elif old:
            comparable = ("title", "author", "source_url", "source_collection", "media_type")
            changed = any(item.get(field) not in (None, "", UNKNOWN) and item.get(field) != old.get(field) for field in comparable)
            if changed:
                candidate = dict(old)
                candidate.update(item)
                candidate["sync_status"] = "更新候选"
                item = candidate
                counts["更新候选"] += 1
            else:
                item = old
                item["sync_status"] = "跳过"
                counts["跳过"] += 1
        else:
            item["sync_status"] = "新增"
            item["first_synced_at"] = date.today().isoformat()
            counts["新增"] += 1
        item["last_seen_at"] = date.today().isoformat()
        by_key[item_key] = item
        result.append(item)
    incoming_keys = {key(item) for item in incoming if key(item)}
    for item in existing:
        if key(item) not in incoming_keys:
            result.append(item)
    return result, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", help="小红书同步索引 Markdown")
    parser.add_argument("records", help="normalize_records.py 输出的 JSON")
    parser.add_argument("--write", action="store_true", help="原子写回索引；默认只预览")
    parser.add_argument("--output", help="把合并后的完整 Markdown 写到另一文件")
    parser.add_argument("--records-output", help="输出带同步状态的本批记录 JSON，供 Markdown 渲染")
    args = parser.parse_args()
    try:
        path = Path(args.index)
        original = path.read_text(encoding="utf-8")
        match, existing = parse_index(original)
        incoming = records_from_payload(load_json(args.records))
        merged, counts = merge(existing, incoming)
        # merge() preserves incoming order at the front, including unkeyed
        # records that must remain visible as 待确认 in the report.
        batch_records = merged[: len(incoming)]
        if args.records_output:
            atomic_write(Path(args.records_output), dump_json({"items": batch_records}))
        block = "```yaml\n" + dump_json({"items": merged}).rstrip() + "\n```"
        updated = original[: match.start(2)] + block + original[match.end(2) :]
        if args.output:
            atomic_write(Path(args.output), updated)
        elif args.write:
            atomic_write(path, updated)
        else:
            sys.stdout.write(updated)
        print(dump_json({"counts": counts}).rstrip(), file=sys.stderr)
        return 0
    except (OSError, ValueError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
