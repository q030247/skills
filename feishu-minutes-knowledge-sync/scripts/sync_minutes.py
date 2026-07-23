#!/usr/bin/env python3
"""Deterministic Feishu Minutes -> Markdown knowledge-base synchronizer.

Uses only Python's standard library and lark-cli. The calling AI remains
responsible for reading the target knowledge-base rules and supplying the
resolved paths and frontmatter values.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


STATE_START = "<!-- FEISHU_MINUTES_SYNC_STATE:START -->"
STATE_END = "<!-- FEISHU_MINUTES_SYNC_STATE:END -->"
TABLE_START = "<!-- FEISHU_MINUTES_SYNC_TABLE:START -->"
TABLE_END = "<!-- FEISHU_MINUTES_SYNC_TABLE:END -->"
EXIT_PRECONDITION = 2
EXIT_CONFIRMATION_REQUIRED = 3
EXIT_PARTIAL_FAILURE = 4


class SyncError(RuntimeError):
    pass


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def json_scalar(value: Any) -> str:
    """JSON strings are valid YAML scalars and avoid hand-written escaping."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)


def now_local() -> dt.datetime:
    return dt.datetime.now().astimezone()


def iso_now() -> str:
    return now_local().isoformat(timespec="seconds")


def default_dates() -> Tuple[str, str]:
    today = now_local().date()
    return (today - dt.timedelta(days=29)).isoformat(), today.isoformat()


def resolve_knowledge_base(args: argparse.Namespace) -> Tuple[Path, str]:
    """Resolve KB by selected folder > user input > portable default folder."""
    if args.selected_folder:
        raw, source, create = args.selected_folder, "selected-folder", False
    elif args.knowledge_base:
        raw, source, create = args.knowledge_base, "user-input", False
    else:
        raw, source, create = args.default_folder, "default-folder", True
    path = Path(raw).expanduser()
    path = path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise SyncError(f"knowledge base from {source} does not exist or is not a directory: {path}")
    return path, source


def safe_path(root: Path, user_path: str, label: str) -> Path:
    candidate = Path(user_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SyncError(f"{label} must stay inside knowledge base: {resolved}") from exc
    return resolved


def rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def run_cli(cli: str, argv: Sequence[str], cwd: Path) -> Dict[str, Any]:
    env = os.environ.copy()
    env["LARKSUITE_CLI_NO_UPDATE_NOTIFIER"] = "1"
    env["LARKSUITE_CLI_NO_SKILLS_NOTIFIER"] = "1"
    proc = subprocess.run(
        [cli, *argv],
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    raw = proc.stdout.strip() if proc.returncode == 0 else proc.stderr.strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        message = raw[-1200:] if raw else "no structured output"
        raise SyncError(f"lark-cli returned non-JSON output (exit {proc.returncode}): {message}") from exc
    if proc.returncode != 0 or payload.get("ok") is False:
        error = payload.get("error", payload)
        raise SyncError(f"lark-cli failed: {json.dumps(error, ensure_ascii=False)}")
    return payload


def data_of(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload.get("data", payload)
    return data if isinstance(data, dict) else {}


def extract_items(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], bool, str]:
    data = data_of(payload)
    items = data.get("items")
    if items is None and isinstance(data.get("minutes"), list):
        items = data["minutes"]
    if not isinstance(items, list):
        items = []
    clean = [item for item in items if isinstance(item, dict)]
    return clean, bool(data.get("has_more")), str(data.get("page_token") or "")


def token_of(item: Dict[str, Any]) -> str:
    return str(item.get("minute_token") or item.get("token") or item.get("id") or "").strip()


def search_once(
    cli: str,
    profile: str,
    kb: Path,
    start: str,
    end: str,
    owner: bool,
    participant: bool,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    page_token = ""
    while True:
        argv = [
            "minutes", "+search", "--profile", profile, "--as", "user",
            "--start", start, "--end", end, "--page-size", "30", "--format", "json",
        ]
        if owner:
            argv += ["--owner-ids", "me"]
        if participant:
            argv += ["--participant-ids", "me"]
        if page_token:
            argv += ["--page-token", page_token]
        payload = run_cli(cli, argv, kb)
        items, has_more, next_token = extract_items(payload)
        results.extend(items)
        if not has_more:
            return results
        if not next_token or next_token == page_token:
            raise SyncError("pagination reported has_more without a usable next page token")
        page_token = next_token


def search_candidates(args: argparse.Namespace, kb: Path) -> List[Dict[str, Any]]:
    pools: List[List[Dict[str, Any]]] = []
    if args.scope in ("owned", "all-related"):
        pools.append(search_once(args.cli, args.profile, kb, args.start, args.end, True, False))
    if args.scope in ("participated", "all-related"):
        pools.append(search_once(args.cli, args.profile, kb, args.start, args.end, False, True))
    merged: Dict[str, Dict[str, Any]] = {}
    for item in (x for pool in pools for x in pool):
        token = token_of(item)
        if token:
            merged.setdefault(token, item)
    return list(merged.values())


def load_state(index_path: Path) -> Dict[str, Any]:
    if not index_path.exists():
        return {"index_version": 2, "identity_key": "minute_token", "last_successful_sync_at": None, "items": []}
    text = index_path.read_text(encoding="utf-8")
    if STATE_START not in text or STATE_END not in text:
        raise SyncError(
            f"existing index has no managed state markers; migrate or confirm before changing it: {index_path}"
        )
    raw = text.split(STATE_START, 1)[1].split(STATE_END, 1)[0].strip()
    if raw.startswith("```json"):
        raw = raw[len("```json"):].strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SyncError(f"index managed state is invalid JSON: {index_path}") from exc
    if not isinstance(state, dict) or not isinstance(state.get("items"), list):
        raise SyncError("index managed state must be an object containing an items array")
    seen: set[str] = set()
    for item in state["items"]:
        token = token_of(item) if isinstance(item, dict) else ""
        if not token or token in seen:
            raise SyncError("index contains a missing or duplicate minute_token")
        seen.add(token)
    return state


def portable_index_path(kb: Path, value: str, legacy_roots: Sequence[str], label: str) -> Tuple[Path, str]:
    """Resolve an indexed path and normalize legacy absolute paths to KB-relative paths."""
    raw = Path(value)
    if not raw.is_absolute():
        resolved = safe_path(kb, value, label)
        return resolved, rel(kb, resolved)
    roots = [kb, *(Path(root).expanduser().resolve() for root in legacy_roots)]
    for root in roots:
        try:
            relative = raw.resolve().relative_to(root)
            resolved = safe_path(kb, relative.as_posix(), label)
            return resolved, relative.as_posix()
        except ValueError:
            continue
    raise SyncError(
        f"{label} is an absolute path from another device; pass its former knowledge-base root with --legacy-root: {value}"
    )


def path_has_prefix(value: str, prefixes: Sequence[str]) -> bool:
    normalized = value.replace("\\", "/").strip("/")
    return any(normalized == prefix.strip("/") or normalized.startswith(prefix.strip("/") + "/") for prefix in prefixes)


def validate_local_states(
    state: Dict[str, Any], kb: Path, legacy_roots: Sequence[str], skip_prefixes: Sequence[str]
) -> None:
    for item in state.get("items", []):
        summary_value = str(item.get("summary_path") or "").strip()
        transcript_value = str(item.get("transcript_path") or "").strip()
        if not summary_value or not transcript_value:
            raise SyncError("index item is missing summary_path or transcript_path")
        summary, summary_relative = portable_index_path(kb, summary_value, legacy_roots, "summary_path")
        transcript, transcript_relative = portable_index_path(kb, transcript_value, legacy_roots, "transcript_path")
        item["summary_path"] = summary_relative
        item["transcript_path"] = transcript_relative
        if item.get("local_state") == "deleted" or item.get("pair_state") == "deleted":
            item["local_state"] = "deleted"
            item["pair_state"] = "deleted"
            item["sync_action"] = "deleted"
            continue
        if path_has_prefix(summary_relative, skip_prefixes) or path_has_prefix(transcript_relative, skip_prefixes):
            item["local_validation"] = "skipped"
            continue
        present = int(summary.exists()) + int(transcript.exists())
        item["local_state"] = "present" if present == 2 else "partial" if present == 1 else "missing"
        item["pair_state"] = "complete" if present == 2 else "incomplete"
        item["local_validation"] = "checked"


def remote_metadata(item: Dict[str, Any]) -> Dict[str, str]:
    return {
        "source_url": first_value([item], ["url", "minute_url", "source_url"]),
        "source_created_at": first_value([item], ["create_time", "created_at", "source_created_at", "start_time"]),
        "source_updated_at": first_value([item], ["update_time", "updated_at", "source_updated_at", "modify_time"]),
    }


def time_key(value: str) -> Tuple[int, str]:
    value = str(value or "").strip()
    if not value:
        return (0, "")
    if value.isdigit():
        stamp = int(value)
        if stamp > 10_000_000_000:
            stamp //= 1000
        return (stamp, value)
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=now_local().tzinfo)
        return (int(parsed.timestamp()), value)
    except ValueError:
        return (0, value)


def compare_and_backfill(local: Dict[str, Any], remote: Dict[str, Any]) -> Tuple[bool, bool]:
    """Return (metadata_backfilled, source_update_pending), never touching note content."""
    metadata = remote_metadata(remote)
    changed = False
    for key in ("source_url", "source_created_at"):
        if not local.get(key) and metadata[key]:
            local[key] = metadata[key]
            changed = True
    remote_updated = metadata["source_updated_at"]
    local_updated = str(local.get("source_updated_at") or "")
    if not local_updated and remote_updated:
        local["source_updated_at"] = remote_updated
        local.pop("remote_source_updated_at", None)
        local.pop("update_check", None)
        return True, False
    if remote_updated and time_key(remote_updated) > time_key(local_updated):
        local["remote_source_updated_at"] = remote_updated
        local["update_check"] = "pending"
        return changed, True
    return changed, local.get("update_check") == "pending"


def clean_title(value: str, fallback: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "-", value).strip(" .-")
    value = re.sub(r"\s+", " ", value)
    return (value[:80].rstrip() or fallback)


def first_value(items: Iterable[Dict[str, Any]], keys: Sequence[str]) -> str:
    for item in items:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return str(value)
    return ""


def date_from(item: Dict[str, Any], detail: Dict[str, Any]) -> str:
    raw = first_value([detail, item], ["start_time", "create_time", "created_at", "source_created_at"])
    if raw:
        if raw.isdigit():
            stamp = int(raw)
            if stamp > 10_000_000_000:
                stamp //= 1000
            return dt.datetime.fromtimestamp(stamp, tz=dt.timezone.utc).astimezone().date().isoformat()
        match = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
        if match:
            return match.group(1)
    return now_local().date().isoformat()


def detail_for(args: argparse.Namespace, kb: Path, token: str, temp_rel: str) -> Dict[str, Any]:
    payload = run_cli(
        args.cli,
        [
            "minutes", "+detail", "--profile", args.profile, "--as", "user",
            "--minute-tokens", token, "--summary", "--todo", "--chapter", "--keyword",
            "--transcript", "--output-dir", temp_rel, "--format", "json",
        ],
        kb,
    )
    data = data_of(payload)
    minutes = data.get("minutes")
    if not isinstance(minutes, list) or not minutes or not isinstance(minutes[0], dict):
        raise SyncError(f"detail response contains no minute for token {token}")
    return minutes[0]


def resolve_transcript(kb: Path, detail: Dict[str, Any]) -> str:
    artifacts = detail.get("artifacts") if isinstance(detail.get("artifacts"), dict) else {}
    path_value = artifacts.get("transcript_file") or detail.get("transcript_file")
    if not path_value:
        raise SyncError("detail response contains no transcript_file")
    path = Path(str(path_value))
    path = path.resolve() if path.is_absolute() else (kb / path).resolve()
    try:
        path.relative_to(kb)
    except ValueError as exc:
        raise SyncError("transcript_file resolved outside the knowledge base working directory") from exc
    if not path.is_file():
        raise SyncError(f"transcript file does not exist: {path}")
    return path.read_text(encoding="utf-8")


def render_value(value: Any) -> str:
    if value in (None, "", [], {}):
        return "_飞书未返回此项。_"
    if isinstance(value, str):
        return value.strip()
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"


def frontmatter(fields: Sequence[Tuple[str, Any]]) -> str:
    return "---\n" + "\n".join(f"{key}: {json_scalar(value)}" for key, value in fields) + "\n---"


def note_pair(
    args: argparse.Namespace,
    kb: Path,
    target: Path,
    item: Dict[str, Any],
    detail: Dict[str, Any],
    transcript: str,
) -> Tuple[Path, Path, str, str, Dict[str, Any]]:
    token = token_of(detail) or token_of(item)
    title = clean_title(first_value([detail, item], ["title", "topic"]), f"飞书妙记-{token[-8:]}")
    date = date_from(item, detail)
    base = clean_title(f"{date}-{title}", f"{date}-飞书妙记-{token[-8:]}")
    summary_path = target / f"{base}-智能纪要.md"
    transcript_path = target / f"{base}-原始逐字稿.md"
    if summary_path.exists() or transcript_path.exists():
        raise SyncError(f"target filename already exists for unindexed token {token}")
    summary_link = transcript_path.stem
    transcript_link = summary_path.stem
    source_url = first_value([detail, item], ["url", "minute_url", "source_url"])
    source_created = first_value([detail, item], ["create_time", "created_at", "source_created_at"])
    source_updated = first_value([detail, item], ["update_time", "updated_at", "source_updated_at"])
    note_id = str(detail.get("note_id") or "")
    artifacts = detail.get("artifacts") if isinstance(detail.get("artifacts"), dict) else {}
    common = [
        ("source", "feishu-minutes"), ("source_id", token), ("minute_token", token),
        ("source_group_id", token),
        ("source_url", source_url), ("source_created_at", source_created),
        ("source_updated_at", source_updated), ("note_id", note_id),
        ("profile_name", args.profile), ("sync_status", "synced"),
        ("sync_status_label", "已同步 / Synced"),
        ("created", date), ("updated", now_local().date().isoformat()),
        ("ai_generated", False),
    ]
    if args.confidentiality:
        common.append(("confidentiality", args.confidentiality))
    status_labels = {"raw": "原始 / Raw", "processing": "处理中 / Processing", "active": "活跃 / Active"}
    status_label = status_labels.get(args.status, f"待确认 / {args.status}")
    summary_text = "\n\n".join([
        frontmatter([
            ("title", f"{date} {title} 智能纪要"),
            ("summary", "飞书妙记生成的智能纪要，需结合原始逐字稿复核。"),
            ("tags", ["飞书妙记", "会议纪要"]), ("type", args.summary_type),
            ("status", args.status), ("status_label", status_label), ("content_role", "summary"),
            ("capture_types", []), ("ai_processing_status", "unprocessed"),
            ("ai_processing_status_label", "未处理 / Unprocessed"),
            ("article_extraction_status", "not_applicable"),
            ("article_extraction_status_label", "不适用 / Not applicable"), *common,
        ]),
        f"# {date} {title} 智能纪要",
        f"> 对应原始记录：[[{summary_link}]]",
        "## 飞书智能总结\n\n" + render_value(artifacts.get("summary")),
        "## 章节\n\n" + render_value(artifacts.get("chapters")),
        "## 待办\n\n" + render_value(artifacts.get("todos")),
        "## 关键词\n\n" + render_value(artifacts.get("keywords")),
        f"## 来源\n\n- 飞书妙记：{source_url or '未提供'}\n- 原始逐字稿：[[{summary_link}]]",
        "<!-- AI:START -->\n## AI处理区\n\n- 内容分类：待处理\n- 建议归属：待确认\n- 衍生结果：待处理\n<!-- AI:END -->",
    ]) + "\n"
    transcript_text = "\n\n".join([
        frontmatter([
            ("title", f"{date} {title} 原始逐字稿"),
            ("summary", "飞书妙记的原始文字记录，结论待确认。"),
            ("tags", ["飞书妙记", "原始记录", "逐字稿"]), ("type", args.transcript_type),
            ("status", args.status), ("status_label", status_label), ("content_role", "transcript"),
            ("transcript_review_status", "pending_review"),
            ("transcript_review_status_label", "待人工检查 / Pending review"),
            ("transcript_text_source", ""), ("corrected_transcript", ""), *common,
        ]),
        f"# {date} {title} 原始逐字稿",
        f"> 对应智能纪要：[[{transcript_link}]]",
        "## 原始文字记录\n\n" + transcript.rstrip(),
        "> [!warning] 人工校订闸门\n> 原始文字记录永久保留。人工将`transcript_review_status`改为`ready_for_extraction`并明确`transcript_text_source`前，不得进行后续提取。",
        f"## 来源\n\n- 飞书妙记：{source_url or '未提供'}\n- 智能纪要：[[{transcript_link}]]",
    ]) + "\n"
    record = {
        "minute_token": token,
        "source_url": source_url,
        "source_title": title,
        "source_created_at": source_created,
        "source_updated_at": source_updated,
        "note_id": note_id,
        "summary_path": rel(kb, summary_path),
        "transcript_path": rel(kb, transcript_path),
        "local_state": "present",
        "source_state": "present",
        "pair_state": "complete",
        "sync_status": "synced",
        "sync_action": "added",
        "profile_name": args.profile,
        "synced_at": iso_now(),
    }
    return summary_path, transcript_path, summary_text, transcript_text, record


def table_for(state: Dict[str, Any]) -> str:
    lines = [
        "| 来源时间 | minute token | 智能纪要 | 原始逐字稿 | 配对状态 |",
        "|---|---|---|---|---|",
    ]
    for item in state.get("items", []):
        created = str(item.get("source_created_at") or "")
        token = str(item.get("minute_token") or "")
        summary = Path(str(item.get("summary_path") or "")).with_suffix("").as_posix()
        transcript = Path(str(item.get("transcript_path") or "")).with_suffix("").as_posix()
        lines.append(f"| {created} | `{token}` | [[{summary}]] | [[{transcript}]] | {item.get('pair_state', '')} |")
    return "\n".join(lines)


def index_text(args: argparse.Namespace, state: Dict[str, Any], existing: Optional[str]) -> str:
    state_block = STATE_START + "\n```json\n" + json.dumps(state, ensure_ascii=False, indent=2) + "\n```\n" + STATE_END
    table_block = TABLE_START + "\n" + table_for(state) + "\n" + TABLE_END
    if existing:
        text = re.sub(re.escape(STATE_START) + r".*?" + re.escape(STATE_END), state_block, existing, flags=re.S)
        if TABLE_START in text and TABLE_END in text:
            text = re.sub(re.escape(TABLE_START) + r".*?" + re.escape(TABLE_END), table_block, text, flags=re.S)
        else:
            text = text.rstrip() + "\n\n## 已同步妙记\n\n" + table_block + "\n"
        text = re.sub(r"(?m)^updated:\s*.*$", f"updated: {now_local().date().isoformat()}", text, count=1)
        text = re.sub(r"(?m)^profile_name:\s*.*$", f"profile_name: {json_scalar(args.profile)}", text, count=1)
        return text
    today = now_local().date().isoformat()
    return f"""---
title: {json_scalar('飞书妙记同步索引')}
summary: {json_scalar('记录飞书妙记与本地智能纪要、原始逐字稿的对应关系。')}
tags: [飞书妙记, 同步, 索引]
type: system
status: active
status_label: 活跃 / Active
source: feishu-minutes
created: {today}
updated: {today}
ai_generated: true
index_version: 2
identity_key: minute_token
profile_name: {json_scalar(args.profile)}
---

# 飞书妙记同步索引

此索引的 JSON 区域由同步脚本维护；不要手工修改 token 或路径。

{state_block}

## 已同步妙记

{table_block}
"""


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def write_report(
    args: argparse.Namespace,
    kb: Path,
    report_path: Path,
    added: List[Dict[str, Any]],
    skipped: int,
    deleted_skipped: int,
    metadata_backfilled: int,
    updates_pending: List[Tuple[str, str, str]],
    failures: List[Tuple[str, str]],
    pending: List[str],
) -> None:
    lines = [
        "---",
        f"title: {json_scalar(now_local().date().isoformat() + ' 飞书妙记同步报告')}",
        f"summary: {json_scalar(f'本次新增 {len(added)} 条、跳过 {skipped} 条、来源更新待确认 {len(updates_pending)} 条、失败 {len(failures)} 条。')}",
        "tags: [飞书妙记, 同步报告]", "type: system", "status: active", "source: ai",
        f"created: {now_local().date().isoformat()}", f"updated: {now_local().date().isoformat()}",
        "ai_generated: true", "---", "",
        f"# {now_local().date().isoformat()} 飞书妙记同步报告", "",
        "## 执行范围", "",
        f"- Profile：`{args.profile}`", f"- 查询时间：{args.start} 至 {args.end}",
        f"- 知识库路径来源：`{args.knowledge_base_source}`",
        f"- 目标目录：`{rel(kb, safe_path(kb, args.target_dir, 'target_dir'))}`",
        "- 唯一键：`minute_token`", "",
        "## 统计", "",
        f"- 新增：{len(added)}", f"- 跳过：{skipped}", f"- 已删除且永久跳过：{deleted_skipped}",
        f"- 来源元数据回填：{metadata_backfilled}", f"- 来源更新待确认：{len(updates_pending)}",
        f"- 失败：{len(failures)}", f"- 待确认：{len(pending) + len(updates_pending)}", "",
        "## 新增文件", "",
    ]
    for item in added:
        lines.append(f"- [[{Path(item['summary_path']).stem}]] ↔ [[{Path(item['transcript_path']).stem}]]")
    lines += ["", "## 失败与待确认", ""]
    if not failures and not pending:
        lines.append("- 无")
    for token, reason in failures:
        lines.append(f"- `{token}`：{reason}")
    for token, local_time, remote_time in updates_pending:
        lines.append(f"- `{token}`：来源更新时间由 `{local_time}` 变为 `{remote_time}`；未覆盖本地纪要，等待确认。")
    for value in pending:
        lines.append(f"- {value}")
    lines += ["", "## 安全检查", "", "- 未覆盖、移动或删除既有知识库文件。", "- 未向飞书之外的服务发送妙记内容。", ""]
    atomic_write(report_path, "\n".join(lines))


def doctor(args: argparse.Namespace) -> int:
    cli = shutil.which(args.cli)
    if not cli:
        print(json.dumps({"ok": False, "cli_found": False, "install_command": "npx @larksuite/cli@latest install"}, ensure_ascii=False, indent=2))
        return EXIT_PRECONDITION
    version = subprocess.run([cli, "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout.strip()
    try:
        auth = run_cli(cli, ["auth", "status", "--profile", args.profile, "--json", "--verify"], Path.cwd())
    except SyncError as exc:
        print(json.dumps({"ok": False, "cli_found": True, "version": version, "profile": args.profile, "auth_error": str(exc)}, ensure_ascii=False, indent=2))
        return EXIT_PRECONDITION
    auth_data = data_of(auth)
    identities = auth_data.get("identities") if isinstance(auth_data.get("identities"), dict) else {}
    user = identities.get("user") if isinstance(identities.get("user"), dict) else {}
    verified = bool(auth_data.get("verified")) and bool(user.get("verified")) and bool(user.get("available"))
    print(json.dumps({"ok": verified, "cli_found": True, "version": version, "profile": args.profile, "auth": auth_data}, ensure_ascii=False, indent=2))
    return 0 if verified else EXIT_PRECONDITION


def sync(args: argparse.Namespace) -> int:
    cli = shutil.which(args.cli)
    if not cli:
        raise SyncError("lark-cli not found; install with: npx @larksuite/cli@latest install")
    args.cli = cli
    kb, args.knowledge_base_source = resolve_knowledge_base(args)
    target = safe_path(kb, args.target_dir, "target_dir")
    index_path = safe_path(kb, args.index_path, "index_path")
    report_path = safe_path(kb, args.report_path, "report_path")
    target.mkdir(parents=True, exist_ok=True)
    existing_index = index_path.read_text(encoding="utf-8") if index_path.exists() else None
    state = load_state(index_path)
    validate_local_states(state, kb, args.legacy_root, args.skip_local_validation_prefix)
    if not args.start:
        watermark = str(state.get("last_successful_sync_at") or "")
        if watermark:
            try:
                water_date = dt.datetime.fromisoformat(watermark.replace("Z", "+00:00")).astimezone().date()
                args.start = (water_date - dt.timedelta(days=args.overlap_days)).isoformat()
            except ValueError:
                args.start = default_dates()[0]
        else:
            args.start = default_dates()[0]
    known = {token_of(item): item for item in state.get("items", [])}
    candidates = search_candidates(args, kb)
    new_items: List[Dict[str, Any]] = []
    skipped = 0
    deleted_skipped = 0
    metadata_backfilled = 0
    updates_pending: List[Tuple[str, str, str]] = []
    for candidate in candidates:
        token = token_of(candidate)
        local = known.get(token)
        if local is None:
            new_items.append(candidate)
            continue
        if local.get("local_state") == "deleted" or local.get("pair_state") == "deleted" or local.get("source_state") == "deleted":
            deleted_skipped += 1
            continue
        old_updated = str(local.get("source_updated_at") or "")
        backfilled, update_pending = compare_and_backfill(local, candidate)
        metadata_backfilled += int(backfilled)
        if update_pending:
            updates_pending.append((token, old_updated, str(local.get("remote_source_updated_at") or "")))
        else:
            skipped += 1
    missing = [token for token, item in known.items() if item.get("local_state") in ("partial", "missing")]
    if len(new_items) > args.batch_limit and not args.confirm_batch:
        preview = {"ok": False, "confirmation_required": True, "new_count": len(new_items), "batch_limit": args.batch_limit, "tokens": [token_of(x) for x in new_items[:args.batch_limit]]}
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return EXIT_CONFIRMATION_REQUIRED
    added: List[Dict[str, Any]] = []
    failures: List[Tuple[str, str]] = []
    created_paths: List[Path] = []
    with tempfile.TemporaryDirectory(prefix=".feishu-minutes-sync-", dir=str(kb)) as temp_dir:
        temp_rel = rel(kb, Path(temp_dir))
        for item in new_items[: args.batch_limit]:
            token = token_of(item)
            try:
                detail = detail_for(args, kb, token, temp_rel)
                transcript = resolve_transcript(kb, detail)
                summary_path, transcript_path, summary_text, transcript_text, record = note_pair(args, kb, target, item, detail, transcript)
                atomic_write(summary_path, summary_text)
                created_paths.append(summary_path)
                try:
                    atomic_write(transcript_path, transcript_text)
                    created_paths.append(transcript_path)
                except Exception:
                    summary_path.unlink(missing_ok=True)
                    created_paths.remove(summary_path)
                    raise
                state["items"].append(record)
                added.append(record)
            except Exception as exc:
                failures.append((token, str(exc)))
    state["last_successful_sync_at"] = iso_now() if not failures and not updates_pending and len(new_items) <= args.batch_limit else state.get("last_successful_sync_at")
    state["updated_at"] = iso_now()
    state["last_profile_name"] = args.profile
    try:
        atomic_write(index_path, index_text(args, state, existing_index))
    except Exception:
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise
    pending = [f"索引中的 `{token}` 本地配对文件不完整，未自动恢复。" for token in missing]
    write_report(args, kb, report_path, added, skipped, deleted_skipped, metadata_backfilled, updates_pending, failures, pending)
    result = {
        "ok": not failures,
        "added": len(added), "skipped": skipped, "deleted_skipped": deleted_skipped,
        "metadata_backfilled": metadata_backfilled, "source_updates_pending": len(updates_pending),
        "failed": len(failures), "pending": len(pending) + len(updates_pending),
        "knowledge_base_source": args.knowledge_base_source,
        "knowledge_base": str(kb),
        "remaining_candidates": max(0, len(new_items) - args.batch_limit),
        "index": rel(kb, index_path), "report": rel(kb, report_path),
        "files": [{"summary": x["summary_path"], "transcript": x["transcript_path"]} for x in added],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else EXIT_PARTIAL_FAILURE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Incrementally sync Feishu Minutes into paired Markdown notes.")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor_p = sub.add_parser("doctor", help="Check lark-cli and the specified profile authorization.")
    doctor_p.add_argument("--profile", required=True)
    doctor_p.add_argument("--cli", default="lark-cli")
    sync_p = sub.add_parser("sync", help="Run deterministic incremental synchronization.")
    sync_p.add_argument("--profile", required=True)
    sync_p.add_argument("--selected-folder", help="Folder currently selected as the AI workspace/project; highest priority.")
    sync_p.add_argument("--knowledge-base", help="Knowledge-base path supplied by the user; used only when no selected folder exists.")
    sync_p.add_argument("--default-folder", default="feishu-minutes-knowledge-base", help="Portable fallback folder relative to the current working directory.")
    sync_p.add_argument("--target-dir", default="feishu-minutes")
    sync_p.add_argument("--index-path", default="feishu-minutes/feishu-minutes-sync-index.md")
    sync_p.add_argument("--report-path", default=f"feishu-minutes/reports/{now_local().date().isoformat()}-feishu-minutes-sync-report.md")
    _, end = default_dates()
    sync_p.add_argument("--start", help="Defaults to the last successful watermark minus overlap-days, or 30 days ago for a new index.")
    sync_p.add_argument("--end", default=end)
    sync_p.add_argument("--overlap-days", type=int, default=2)
    sync_p.add_argument("--scope", choices=["owned", "participated", "all-related"], default="all-related")
    sync_p.add_argument("--batch-limit", type=int, default=50)
    sync_p.add_argument("--confirm-batch", action="store_true", help="Confirm processing the first batch when candidates exceed the limit; never processes more than batch-limit.")
    sync_p.add_argument("--legacy-root", action="append", default=[], help="Former device knowledge-base root used to convert legacy absolute index paths; repeatable.")
    sync_p.add_argument("--skip-local-validation-prefix", action="append", default=[], help="KB-relative prefix whose indexed files must not be read; repeatable.")
    sync_p.add_argument("--confidentiality", help="Optional legacy frontmatter field; omit when the target knowledge base does not use it.")
    sync_p.add_argument("--summary-type", default="meeting")
    sync_p.add_argument("--transcript-type", default="transcript")
    sync_p.add_argument("--status", default="raw")
    sync_p.add_argument("--cli", default="lark-cli")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return doctor(args) if args.command == "doctor" else sync(args)
    except SyncError as exc:
        eprint(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return EXIT_PRECONDITION


if __name__ == "__main__":
    raise SystemExit(main())
