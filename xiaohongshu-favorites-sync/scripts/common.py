#!/usr/bin/env python3
"""Shared, dependency-free helpers for Xiaohongshu favorite records."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

BASE_URL = "https://www.xiaohongshu.com"
UNKNOWN = "待确认"
ID_PATTERNS = (
    re.compile(r"/(?:explore|discovery/item)/([0-9a-zA-Z]+)"),
    re.compile(r"/note/([0-9a-zA-Z]+)"),
)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def records_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = payload.get("items", payload.get("records", payload.get("data", [])))
    else:
        raise ValueError("输入必须是 JSON 数组，或包含 items/records/data 数组的对象")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("收藏记录必须是对象数组")
    return records


def first(record: Dict[str, Any], names: Iterable[str], default: str = "") -> str:
    for name in names:
        value = record.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def normalize_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    absolute = urljoin(BASE_URL, raw_url.strip())
    parts = urlsplit(absolute)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    kept = [(key, query[key]) for key in ("xsec_token", "xsec_source") if query.get(key)]
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/")
    return urlunsplit((parts.scheme or "https", parts.netloc.lower(), path, urlencode(kept), ""))


def dedupe_url(raw_url: str) -> str:
    normalized = normalize_url(raw_url)
    if not normalized:
        return ""
    parts = urlsplit(normalized)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def extract_note_id(record: Dict[str, Any], url: str) -> str:
    explicit = first(record, ("source_id", "note_id", "noteId", "id", "笔记ID"))
    if explicit:
        return explicit
    for pattern in ID_PATTERNS:
        match = pattern.search(urlsplit(url).path)
        if match:
            return match.group(1)
    return ""


def normalize_record(record: Dict[str, Any], collected_at: str = "") -> Dict[str, Any]:
    source_url = normalize_url(first(record, ("source_url", "url", "href", "link", "原始链接")))
    note_id = extract_note_id(record, source_url)
    title = first(record, ("title", "name", "标题"), UNKNOWN)
    author = first(record, ("author", "nickname", "user", "作者"), UNKNOWN)
    collection = first(record, ("source_collection", "collection", "group", "收藏分组"), UNKNOWN)
    body = first(record, ("body", "content", "description", "正文", "简介"))
    media_type = first(record, ("media_type", "type", "媒体类型"), UNKNOWN)
    collected = first(record, ("collected_at", "captured_at", "采集时间"), collected_at or UNKNOWN)
    stable_key = f"id:{note_id}" if note_id else (f"url:{dedupe_url(source_url)}" if source_url else "")
    issues = []
    if not note_id:
        issues.append("缺少稳定笔记ID")
    if not source_url:
        issues.append("缺少原始链接")
    if source_url and "xsec_token=" not in source_url:
        issues.append("链接缺少xsec_token")
    return {
        "title": title,
        "author": author,
        "source_id": note_id or UNKNOWN,
        "source_url": source_url or UNKNOWN,
        "dedupe_url": dedupe_url(source_url) or UNKNOWN,
        "source_collection": collection,
        "body": body,
        "media_type": media_type,
        "collected_at": collected,
        "stable_key": stable_key or UNKNOWN,
        "needs_confirmation": bool(issues),
        "issues": issues,
    }


def normalize_records(records: List[Dict[str, Any]], collected_at: str = "") -> List[Dict[str, Any]]:
    output = []
    seen = set()
    for raw in records:
        item = normalize_record(raw, collected_at)
        key = item["stable_key"]
        if key != UNKNOWN and key in seen:
            continue
        if key != UNKNOWN:
            seen.add(key)
        output.append(item)
    return output


def safe_filename(value: str, fallback: str = "小红书收藏") -> str:
    name = re.sub(r"[\\/:*?\"<>|#^[\]]+", "-", value).strip(" .-")
    name = re.sub(r"\s+", " ", name)
    return (name[:80] or fallback) + ".md"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def md_cell(value: Any) -> str:
    return str(value if value not in (None, "") else UNKNOWN).replace("|", "\\|").replace("\n", "<br>")
