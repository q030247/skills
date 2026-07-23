#!/usr/bin/env python3
"""Convert captured Douyin listcollection JSON into an incremental Markdown dataset."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

INDEX_START = "<!-- DOUYIN_SYNC_INDEX:START -->"
INDEX_END = "<!-- DOUYIN_SYNC_INDEX:END -->"
AI_START = "<!-- AI:START -->"
AI_END = "<!-- AI:END -->"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def nested(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def first_nonempty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def first_url(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        for item in value:
            found = first_url(item)
            if found:
                return found
    if isinstance(value, dict):
        for key in ("url_list", "url", "uri"):
            found = first_url(value.get(key))
            if found and found.startswith(("http://", "https://")):
                return found
    return ""


def find_aweme_lists(value: Any, depth: int = 0) -> Iterable[list[dict[str, Any]]]:
    if depth > 8:
        return
    if isinstance(value, dict):
        candidate = value.get("aweme_list")
        if isinstance(candidate, list):
            yield [item for item in candidate if isinstance(item, dict)]
        for child in value.values():
            yield from find_aweme_lists(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            yield from find_aweme_lists(child, depth + 1)


def collect_items(documents: list[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for document in documents:
        for aweme_list in find_aweme_lists(document):
            items.extend(aweme_list)
    return items


def bitrate_urls(item: dict[str, Any]) -> tuple[list[str], list[str]]:
    h264: list[str] = []
    h265: list[str] = []
    bitrates = nested(item, "video", "bit_rate") or nested(item, "video", "bitrate") or []
    if not isinstance(bitrates, list):
        return h264, h265
    for entry in bitrates:
        if not isinstance(entry, dict):
            continue
        label = " ".join(str(entry.get(key, "")) for key in ("codec_type", "format", "gear_name")).lower()
        url = first_url(entry.get("play_addr"))
        if not url:
            continue
        if any(token in label for token in ("h265", "hevc", "bytevc")):
            h265.append(url)
        elif any(token in label for token in ("h264", "avc")):
            h264.append(url)
        else:
            h264.append(url)
    return list(dict.fromkeys(h264)), list(dict.fromkeys(h265))


def hashtags(item: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for entry in item.get("text_extra") or []:
        if isinstance(entry, dict):
            name = entry.get("hashtag_name")
            if name:
                result.append(str(name))
    return list(dict.fromkeys(result))


def timestamp_text(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value)).astimezone().isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return ""


def video_location_text(item: dict[str, Any]) -> str:
    poi = item.get("poi_info") if isinstance(item.get("poi_info"), dict) else {}
    address = poi.get("address_info")
    if isinstance(address, dict):
        address = first_nonempty(
            address.get("formatted_address"),
            address.get("address"),
            address.get("simple_addr"),
            address.get("city"),
        )
    return str(first_nonempty(
        poi.get("poi_name"),
        address,
        nested(poi, "city_info", "city_name"),
        item.get("ip_attribution"),
        item.get("ip_location"),
        "",
    ))


def normalize(item: dict[str, Any], collection: str, captured_at: str) -> dict[str, Any] | None:
    aweme_id = str(item.get("aweme_id") or "").strip()
    if not aweme_id:
        return None
    h264, h265 = bitrate_urls(item)
    generic_video = first_url(nested(item, "video", "play_addr"))
    video_url = first_nonempty(h264[0] if h264 else "", generic_video, h265[0] if h265 else "") or ""
    share_url = first_nonempty(item.get("share_url"), nested(item, "share_info", "share_url")) or ""
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    statistics = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
    cover_url = first_url(first_nonempty(nested(item, "video", "cover"), nested(item, "video", "origin_cover")))
    duration = first_nonempty(item.get("duration"), nested(item, "video", "duration"))
    video_location = video_location_text(item)
    record = {
        "aweme_id": aweme_id,
        "title": str(first_nonempty(item.get("desc"), item.get("title"), "待确认")),
        "author": str(first_nonempty(author.get("nickname"), "待确认")),
        "author_uid": str(first_nonempty(author.get("uid"), "")),
        "author_sec_uid": str(first_nonempty(author.get("sec_uid"), "")),
        "create_time": timestamp_text(item.get("create_time")),
        "duration_ms": duration if duration is not None else "",
        "aweme_type": item.get("aweme_type", ""),
        "likes": first_nonempty(statistics.get("digg_count"), ""),
        "comments": first_nonempty(statistics.get("comment_count"), ""),
        "shares": first_nonempty(statistics.get("share_count"), ""),
        "collects": first_nonempty(statistics.get("collect_count"), ""),
        "tags": hashtags(item),
        "video_location": video_location,
        "cover_url": cover_url,
        "share_url": str(share_url),
        "douyin_url": f"https://www.douyin.com/{'note' if item.get('aweme_type') == 68 else 'video'}/{quote(aweme_id)}",
        "video_url": str(video_url),
        "h264_urls": h264,
        "h265_urls": h265,
        "collection": collection,
        "captured_at": captured_at,
        "why_saved": "待确认",
        "supports_output": "待确认",
    }
    return finalize_record(record)


def finalize_record(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    missing: list[str] = []
    if not record.get("share_url"):
        missing.append("分享链接（已检查 share_url、share_info.share_url）")
    if not record.get("video_url"):
        missing.append("视频地址（已检查 video.bit_rate[].play_addr、video.play_addr）")
    record["missing"] = missing
    fingerprint_source = {
        key: value for key, value in record.items()
        if key not in {"captured_at", "why_saved", "supports_output", "fingerprint", "missing"}
    }
    canonical = json.dumps(fingerprint_source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    record["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return record


def merge_records(old: dict[str, Any], new: dict[str, Any], *, prefer_new: bool) -> dict[str, Any]:
    merged = dict(old)
    for key, value in new.items():
        if key in {"fingerprint", "missing"}:
            continue
        if key in {"why_saved", "supports_output"} and merged.get(key) not in (None, "", "待确认"):
            continue
        if key not in merged or merged[key] in (None, "", [], {}) or (prefer_new and value not in (None, "", [], {})):
            merged[key] = value
    return finalize_record(merged)


def load_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 2, "last_successful_full_sync_at": None}
    text = path.read_text(encoding="utf-8")
    managed = re.search(
        re.escape(INDEX_START) + r"(.*?)" + re.escape(INDEX_END),
        text,
        re.DOTALL,
    )
    if not managed:
        raise ValueError(f"Existing index has no managed JSON block: {path}")
    block = re.search(r"```json\s*(.*?)\s*```", managed.group(1), re.DOTALL)
    if not block:
        raise ValueError(f"Existing index has no JSON metadata block: {path}")
    # Legacy Markdown indexes may contain raw control characters inside long
    # source strings. Accept them only during migration; newly written state
    # is serialized as strict JSON.
    data = json.loads(block.group(1), strict=False)
    if not isinstance(data, dict):
        raise ValueError("Index metadata must be a JSON object")
    return data


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 2, "items": {}}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
        raise ValueError(f"Invalid compressed state file: {path}")
    return data


def md_cell(value: Any) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, list):
        value = "、".join(str(item) for item in value)
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def md_link(label: str, url: str) -> str:
    if not url:
        return "待确认"
    safe = html.escape(url, quote=True).replace("|", "&#124;")
    return f'<a href="{safe}">{html.escape(label)}</a>'


def split_md_row(line: str) -> list[str]:
    line = line.strip()
    if not line.startswith("|"):
        return []
    content = line[1:-1] if line.endswith("|") else line[1:]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in content:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def read_manual_fields(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    result: dict[str, dict[str, str]] = {}
    header_index = next((index for index, line in enumerate(lines) if line.startswith("| 序号 | 作品 ID | 标题/描述 |")), None)
    if header_index is None:
        return result
    header = split_md_row(lines[header_index])
    positions = {name: index for index, name in enumerate(header)}
    id_index = positions.get("作品 ID")
    why_index = positions.get("为什么收藏")
    supports_index = positions.get("支持什么决策/输出")
    if id_index is None or why_index is None or supports_index is None:
        return result
    for line in lines[header_index + 2:]:
        if not line.startswith("|"):
            break
        cells = split_md_row(line)
        if max(id_index, why_index, supports_index) >= len(cells):
            continue
        aweme_id = cells[id_index].strip()
        if not aweme_id:
            continue
        values = {
            "why_saved": cells[why_index].strip(),
            "supports_output": cells[supports_index].strip(),
        }
        result[aweme_id] = {
            key: value for key, value in values.items() if value not in ("", "—", "待确认")
        }
    return result


def multi_links(label: str, urls: list[str]) -> str:
    if not urls:
        return "待确认"
    return "<br>".join(md_link(f"{label}{index + 1}", url) for index, url in enumerate(urls))


def markdown_body(records: list[dict[str, Any]], collection: str, stats: dict[str, Any], synced_at: str) -> str:
    lines = [
        "## 同步摘要", "", "| 项目 | 内容 |", "|---|---|",
        f"| 最近同步 | {md_cell(synced_at)} |",
        f"| 收藏合集 | {md_cell(collection or '未指定')} |",
        f"| 页面显示总数 | {md_cell(stats.get('displayed_total'))} |",
        f"| 当前捕获唯一数 | {stats['captured_unique']} |",
        f"| 索引原有数 | {stats['indexed_before']} |",
        f"| 合并唯一数 | {stats['union_unique']} |",
        f"| 完整性 | {stats['completeness_label']} |",
        f"| 本次变更 | 新增 {stats['added']} / 更新 {stats['updated']} / 跳过 {stats['skipped']} |",
        "", "## 收藏列表", "",
        "| 序号 | 作品 ID | 标题/描述 | 作者 | 发布时间 | 时长(ms) | 类型 | 点赞 | 评论 | 分享 | 收藏 | 话题 | 视频位置 | 为什么收藏 | 支持什么决策/输出 | 作品链接 |",
        "|---:|---|---|---|---|---:|---|---:|---:|---:|---:|---|---|---|---|---|",
    ]
    for index, record in enumerate(records, 1):
        lines.append("| " + " | ".join([
            str(index), md_cell(record["aweme_id"]), md_cell(record["title"]), md_cell(record["author"]),
            md_cell(record["create_time"]), md_cell(record["duration_ms"]), md_cell(record["aweme_type"]),
            md_cell(record["likes"]), md_cell(record["comments"]), md_cell(record["shares"]),
            md_cell(record["collects"]), md_cell(record["tags"]), md_cell(record.get("video_location")),
            md_cell(record["why_saved"]),
            md_cell(record["supports_output"]), md_link("打开", record["douyin_url"]),
        ]) + " |")
    lines.extend([
        "", "## 链接与媒体地址（必需）", "",
        "| 作品 ID | 分享链接 | 视频播放地址 | H264 地址 | H265 地址 | 媒体地址采集时间 |",
        "|---|---|---|---|---|---|",
    ])
    for record in records:
        lines.append("| " + " | ".join([
            md_cell(record["aweme_id"]), md_link("分享", record["share_url"]), md_link("播放", record["video_url"]),
            multi_links("H264-", record["h264_urls"]), multi_links("H265-", record["h265_urls"]), md_cell(record["captured_at"]),
        ]) + " |")
    lines.extend(["", "## 待确认", "", "| 作品 ID | 问题 | 建议动作 |", "|---|---|---|"])
    missing_rows = 0
    for record in records:
        for issue in record.get("missing", []):
            missing_rows += 1
            lines.append(f"| {md_cell(record['aweme_id'])} | {md_cell(issue)} | 检查来源 JSON 或重新采集 |")
    if not missing_rows:
        lines.append("| — | 无 | — |")
    return "\n".join(lines) + "\n"


def replace_managed(text: str, start: str, end: str, body: str) -> str:
    block = f"{start}\n{body.rstrip()}\n{end}"
    if start in text and end in text:
        pattern = re.escape(start) + r".*?" + re.escape(end)
        return re.sub(pattern, block, text, count=1, flags=re.DOTALL)
    if text.strip():
        raise ValueError("Existing file has no managed block; refusing to overwrite manual content")
    return block + "\n"


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_name = handle.name
    os.replace(temp_name, path)


def atomic_write_gzip(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as raw:
        temp_name = raw.name
    try:
        with gzip.open(temp_name, "wt", encoding="utf-8", compresslevel=9) as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        os.replace(temp_name, path)
    except Exception:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def render_document(title: str, collection: str, body: str, synced_at: str) -> str:
    date = synced_at[:10]
    frontmatter = (
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"summary: {json.dumps(f'抖音收藏合集的本地增量同步表，最近同步于 {synced_at}。', ensure_ascii=False)}\n"
        "tags: [抖音收藏, 收件箱]\n"
        "type: inbox\nstatus: raw\nstatus_label: 原始 / Raw\nsource: douyin\n"
        f"source_collection: {json.dumps(collection or '未指定', ensure_ascii=False)}\n"
        f"created: {date}\nupdated: {date}\n"
        "ai_generated: true\n---\n\n"
        f"# {title}\n\n"
    )
    return frontmatter + AI_START + "\n" + body.rstrip() + "\n" + AI_END + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="Captured JSON files")
    parser.add_argument("--output", required=True, type=Path, help="Markdown favorites list")
    parser.add_argument("--index", required=True, type=Path, help="Managed Markdown sync index")
    parser.add_argument(
        "--state",
        type=Path,
        default=None,
        help="Compressed machine state; defaults beside the Markdown index",
    )
    parser.add_argument("--report", required=True, type=Path, help="Markdown execution report")
    parser.add_argument("--collection", default="", help="Collection name")
    parser.add_argument("--displayed-total", type=int, default=None)
    parser.add_argument("--page-complete", action="store_true")
    parser.add_argument("--restore-missing", action="store_true")
    args = parser.parse_args()

    synced_at = now_iso()
    documents = [read_json(path) for path in args.inputs]
    raw_items = collect_items(documents)
    current: dict[str, dict[str, Any]] = {}
    for raw in raw_items:
        record = normalize(raw, args.collection, synced_at)
        if record:
            current[record["aweme_id"]] = merge_records(
                current.get(record["aweme_id"], {}), record, prefer_new=False
            )

    index = load_index(args.index)
    state_path = args.state or args.index.with_name(f"{args.index.stem}.state.json.gz")
    if state_path.exists():
        state = load_state(state_path)
    else:
        legacy_items = index.pop("items", {})
        if legacy_items and not isinstance(legacy_items, dict):
            raise ValueError("Legacy index items must be keyed by aweme_id")
        state = {"schema_version": 2, "items": legacy_items or {}}
    index.pop("items", None)
    existing = state["items"]
    action_labels = {
        "added": "新增 / Added",
        "updated": "已更新 / Updated",
        "skipped": "已跳过 / Skipped",
        "deleted": "已删除标记 / Deleted",
    }
    state_labels = {
        "present": "存在 / Present",
        "missing": "缺失 / Missing",
        "moved": "已迁移 / Moved",
        "deleted": "已删除标记 / Deleted",
    }
    for entry in existing.values():
        if not isinstance(entry, dict):
            continue
        action = entry.get("sync_action")
        if action:
            entry["sync_action_label"] = action_labels.get(action, "待确认 / Needs confirmation")
        local_state = entry.get("local_state")
        if local_state:
            entry["local_state_label"] = state_labels.get(local_state, "待确认 / Needs confirmation")
        source_state = entry.get("source_state")
        if source_state:
            entry["source_state_label"] = state_labels.get(source_state, "待确认 / Needs confirmation")
    for aweme_id, fields in read_manual_fields(args.output).items():
        entry = existing.get(aweme_id)
        if not isinstance(entry, dict) or not isinstance(entry.get("record"), dict):
            continue
        entry["record"].update(fields)
        entry["record"] = finalize_record(entry["record"])
    indexed_before = len(existing)
    added = updated = skipped = 0
    for aweme_id, record in current.items():
        old_entry = existing.get(aweme_id)
        if old_entry and old_entry.get("local_state") == "missing" and not args.restore_missing:
            skipped += 1
            continue
        old_record = old_entry.get("record", {}) if isinstance(old_entry, dict) else {}
        merged = merge_records(old_record, record, prefer_new=True)
        if not old_entry:
            action = "added"
            added += 1
        elif old_record.get("fingerprint") != record.get("fingerprint"):
            action = "updated"
            updated += 1
        else:
            action = "skipped"
            skipped += 1
        existing[aweme_id] = {
            "sync_action": action,
            "sync_action_label": {
                "added": "新增 / Added",
                "updated": "已更新 / Updated",
                "skipped": "已跳过 / Skipped",
            }[action],
            "local_state": "present",
            "local_state_label": "存在 / Present",
            "source_state": "present",
            "source_state_label": "存在 / Present",
            "last_seen_at": synced_at,
            "record": merged,
        }

    union_unique = len(existing)
    displayed_total = args.displayed_total
    page_complete = args.page_complete
    if displayed_total is None:
        for document in documents:
            if isinstance(document, dict) and isinstance(document.get("displayed_total"), int):
                displayed_total = document["displayed_total"]
                break
    if not page_complete:
        page_complete = any(isinstance(document, dict) and document.get("page_complete") is True for document in documents)
    if displayed_total is not None and union_unique == displayed_total and page_complete:
        completeness = "complete"
        index["last_successful_full_sync_at"] = synced_at
    elif displayed_total is not None and union_unique < displayed_total:
        completeness = "partial"
    else:
        completeness = "needs_confirmation"
    completeness_label = {
        "complete": "完整 / Complete",
        "partial": "部分完成 / Partial",
        "needs_confirmation": "待确认 / Needs confirmation",
    }[completeness]
    index.update({
        "schema_version": 2,
        "updated_at": synced_at,
        "state_file": os.path.relpath(state_path, args.index.parent),
        "record_count": union_unique,
        "last_run": {
            "displayed_total": displayed_total,
            "captured_unique": len(current),
            "indexed_before": indexed_before,
            "union_unique": union_unique,
            "page_complete": page_complete,
            "completeness": completeness,
            "completeness_label": completeness_label,
        },
    })
    stats = {
        **index["last_run"], "added": added, "updated": updated, "skipped": skipped,
    }
    records = [entry["record"] for _, entry in sorted(existing.items()) if entry.get("local_state") != "missing"]
    records.sort(key=lambda row: (row.get("create_time", ""), row.get("aweme_id", "")), reverse=True)

    title = f"抖音收藏列表 - {args.collection}" if args.collection else "抖音收藏列表"
    output_body = markdown_body(records, args.collection, stats, synced_at)
    if args.output.exists():
        output_text = replace_managed(args.output.read_text(encoding="utf-8"), AI_START, AI_END, output_body)
    else:
        output_text = render_document(title, args.collection, output_body, synced_at)

    state.update({"schema_version": 2, "updated_at": synced_at, "items": existing})
    index_json = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True)
    index_block = (
        f"```json\n{index_json}\n```\n\n"
        "## 最近一次同步\n\n"
        "| 项目 | 内容 |\n|---|---|\n"
        f"| 更新时间 | {synced_at} |\n"
        f"| 压缩状态文件 | `{md_cell(index['state_file'])}` |\n"
        f"| 记录数 | {union_unique} |\n"
        f"| 当前捕获唯一数 | {len(current)} |\n"
        f"| 新增 / 更新 / 跳过 | {added} / {updated} / {skipped} |\n"
        f"| 完整性 | {completeness_label} |\n"
    )
    if args.index.exists():
        index_text = replace_managed(args.index.read_text(encoding="utf-8"), INDEX_START, INDEX_END, index_block)
    else:
        date = synced_at[:10]
        index_text = (
            "---\ntitle: 抖音同步索引\nsummary: 使用 aweme_id 维护抖音收藏增量同步状态。\n"
            "tags: [抖音收藏, 同步索引]\ntype: system\nstatus: active\nstatus_label: 活跃 / Active\n"
            f"created: {date}\nupdated: {date}\nai_generated: true\n---\n\n"
            "# 抖音同步索引\n\n" + INDEX_START + "\n" + index_block + "\n" + INDEX_END + "\n"
        )

    difference = "待确认" if displayed_total is None else displayed_total - union_unique
    report_date = synced_at[:10]
    report_text = (
        "---\n"
        f"title: {json.dumps('抖音收藏同步报告', ensure_ascii=False)}\n"
        f"summary: {json.dumps(f'记录本次抖音收藏同步结果，完整性为 {completeness_label}。', ensure_ascii=False)}\n"
        "tags: [抖音收藏, 同步报告]\ntype: system\nstatus: active\nstatus_label: 活跃 / Active\nsource: ai\n"
        f"created: {report_date}\nupdated: {report_date}\n"
        "ai_generated: true\n---\n\n"
        f"# 抖音收藏同步报告\n\n| 项目 | 内容 |\n|---|---|\n"
        f"| 执行时间 | {synced_at} |\n| 收藏合集 | {md_cell(args.collection or '未指定')} |\n"
        f"| 页面显示总数 | {md_cell(displayed_total)} |\n| 当前捕获唯一数 | {len(current)} |\n"
        f"| 索引原有数 | {indexed_before} |\n| 合并唯一数 | {union_unique} |\n| 差额 | {difference} |\n"
        f"| 分页结束 | {'是' if page_complete else '否/待确认'} |\n| 完整性 | {completeness_label} |\n"
        f"| 变更 | 新增 {added} / 更新 {updated} / 跳过 {skipped} |\n"
        f"| 缺少分享或视频地址 | {sum(bool(row.get('missing')) for row in records)} |\n"
        "| 安全检查 | 未读取或保存 Cookie、sessionid、请求头或 Authorization |\n"
    )

    atomic_write(args.output, output_text)
    atomic_write_gzip(state_path, state)
    atomic_write(args.index, index_text)
    atomic_write(args.report, report_text)
    print(json.dumps({
        "output": str(args.output),
        "index": str(args.index),
        "state": str(state_path),
        "report": str(args.report),
        **stats,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
