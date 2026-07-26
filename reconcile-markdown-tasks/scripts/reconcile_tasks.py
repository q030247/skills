#!/usr/bin/env python3
"""Audit formal Markdown tasks and optionally append missing completion dates."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path


TASK_RE = re.compile(r"^(?P<indent>\s*)-\s+\[(?P<mark>[ xX])\]\s+(?P<body>.*?)(?P<newline>\r?\n)?$")
DONE_RE = re.compile(r"(?:✅|\bdone:)\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")
HTML_COMMENT_RE = re.compile(r"\s*(<!--.*?-->)\s*$")
TAG_RE = re.compile(r"(?<!\S)#[^\s#]+")
DATE_META_RE = re.compile(r"\s*(?:✅|\bdone:)\s*\d{4}-\d{2}-\d{2}\b", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--task-tag", default="#task")
    parser.add_argument("--category-label", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--date", required=True)
    parser.add_argument("--apply-completion-date", action="store_true")
    return parser.parse_args()


def excluded(relative: str, patterns: list[str]) -> bool:
    normalized = relative.replace(os.sep, "/")
    return any(
        normalized == pattern.strip("/")
        or normalized.startswith(pattern.strip("/") + "/")
        for pattern in patterns
        if pattern.strip("/")
    )


def normalize_task(body: str, task_tag: str, categories: list[str]) -> str:
    text = HTML_COMMENT_RE.sub("", body)
    text = DATE_META_RE.sub("", text)
    text = text.replace(task_tag, " ")
    for category in categories:
        text = text.replace(category, " ")
    text = TAG_RE.sub(" ", text)
    return " ".join(text.casefold().split())


def insert_done_date(line: str, date: str) -> str:
    newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    core = line[: -len(newline)] if newline else line
    comment = HTML_COMMENT_RE.search(core)
    if comment:
        prefix = core[: comment.start()].rstrip()
        suffix = core[comment.start():].lstrip()
        return f"{prefix} ✅ {date} {suffix}{newline}"
    return f"{core.rstrip()} ✅ {date}{newline}"


def build_markdown_index(root: Path, files: list[Path]) -> tuple[set[str], dict[str, list[str]]]:
    relative_paths: set[str] = set()
    stems: dict[str, list[str]] = defaultdict(list)
    for path in files:
        relative = path.relative_to(root).as_posix()
        without_suffix = relative[:-3] if relative.lower().endswith(".md") else relative
        relative_paths.add(without_suffix)
        stems[path.stem].append(relative)
    return relative_paths, stems


def link_exists(
    raw_target: str,
    source: Path,
    root: Path,
    relative_paths: set[str],
    stems: dict[str, list[str]],
) -> bool:
    target = raw_target.split("|", 1)[0].split("#", 1)[0].strip()
    if not target:
        return True
    target = target[:-3] if target.lower().endswith(".md") else target
    target = target.strip("/")
    if target in relative_paths:
        return True
    source_relative_parent = source.parent.relative_to(root).as_posix()
    local_target = f"{source_relative_parent}/{target}".strip("/")
    if local_target in relative_paths:
        return True
    return "/" not in target and target in stems


def task_block(lines: list[str], start: int, indent: int) -> str:
    block = [lines[start]]
    for line in lines[start + 1:]:
        if not line.strip():
            break
        leading = len(line) - len(line.lstrip())
        if leading <= indent:
            break
        block.append(line)
    return "".join(block)


def write_atomic(path: Path, lines: list[str]) -> None:
    mode = path.stat().st_mode
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.writelines(lines)
        temporary = Path(handle.name)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Root is not a directory: {root}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        raise SystemExit("--date must use YYYY-MM-DD")

    default_excludes = [".git", ".obsidian"]
    excludes = default_excludes + args.exclude
    files = [
        path
        for path in root.rglob("*.md")
        if not path.is_symlink()
        and not excluded(path.relative_to(root).as_posix(), excludes)
    ]
    files.sort()
    relative_paths, stems = build_markdown_index(root, files)

    tasks: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    added: list[dict[str, object]] = []

    for path in files:
        relative = path.relative_to(root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        except (OSError, UnicodeError) as exc:
            errors.append({"file": relative, "error": str(exc)})
            continue

        changed = False
        for index, line in enumerate(lines):
            match = TASK_RE.match(line)
            if not match or args.task_tag not in match.group("body"):
                continue
            body = match.group("body")
            checked = match.group("mark").lower() == "x"
            done_match = DONE_RE.search(body)
            categories = [label for label in args.category_label if label in body]
            block = task_block(lines, index, len(match.group("indent")))
            broken_links = sorted({
                target
                for target in WIKILINK_RE.findall(block)
                if not link_exists(target, path, root, relative_paths, stems)
            })
            record: dict[str, object] = {
                "file": relative,
                "line": index + 1,
                "checked": checked,
                "completion_date": done_match.group(1) if done_match else None,
                "categories": categories,
                "missing_category": bool(args.category_label and not categories),
                "broken_links": broken_links,
                "normalized_text": normalize_task(body, args.task_tag, args.category_label),
                "text": body,
            }
            tasks.append(record)

            if checked and not done_match and args.apply_completion_date:
                lines[index] = insert_done_date(line, args.date)
                changed = True
                added.append({"file": relative, "line": index + 1, "date": args.date})

        if changed:
            try:
                write_atomic(path, lines)
            except OSError as exc:
                errors.append({"file": relative, "error": f"write failed: {exc}"})
                added = [item for item in added if item["file"] != relative]

    duplicate_map: dict[str, list[dict[str, object]]] = defaultdict(list)
    for task in tasks:
        normalized = str(task["normalized_text"])
        if normalized:
            duplicate_map[normalized].append(task)
    duplicates = [
        {
            "normalized_text": normalized,
            "occurrences": [
                {
                    "file": task["file"],
                    "line": task["line"],
                    "checked": task["checked"],
                    "text": task["text"],
                }
                for task in group
            ],
        }
        for normalized, group in duplicate_map.items()
        if len(group) > 1
    ]

    category_stats = {
        label: {
            "open": sum(not task["checked"] and label in task["categories"] for task in tasks),
            "completed_on_date": sum(
                task["completion_date"] == args.date and label in task["categories"]
                for task in tasks
            ) + sum(
                item["date"] == args.date
                and any(
                    task["file"] == item["file"]
                    and task["line"] == item["line"]
                    and label in task["categories"]
                    for task in tasks
                )
                for item in added
            ),
        }
        for label in args.category_label
    }

    result = {
        "root": str(root),
        "date": args.date,
        "mode": "apply_completion_date" if args.apply_completion_date else "audit_only",
        "files_scanned": len(files),
        "formal_tasks": len(tasks),
        "open_tasks": sum(not task["checked"] for task in tasks),
        "checked_tasks": sum(bool(task["checked"]) for task in tasks),
        "completion_dates_added": len(added),
        "added": added,
        "missing_completion_dates": [
            {
                "file": task["file"],
                "line": task["line"],
                "text": task["text"],
            }
            for task in tasks
            if task["checked"] and not task["completion_date"]
            and not any(
                item["file"] == task["file"] and item["line"] == task["line"]
                for item in added
            )
        ],
        "uncategorized": [
            {"file": task["file"], "line": task["line"], "text": task["text"]}
            for task in tasks
            if task["missing_category"]
        ],
        "duplicates": duplicates,
        "broken_links": [
            {
                "file": task["file"],
                "line": task["line"],
                "links": task["broken_links"],
                "text": task["text"],
            }
            for task in tasks
            if task["broken_links"]
        ],
        "category_stats": category_stats,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
