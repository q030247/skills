#!/usr/bin/env python3
"""Render normalized records as Obsidian notes and a Markdown report."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from common import UNKNOWN, atomic_write, load_json, md_cell, records_from_payload, safe_filename


def yaml_value(value):
    return json.dumps(value if value not in (None, "") else UNKNOWN, ensure_ascii=False)


def note_text(item, today):
    title = item.get("title", UNKNOWN)
    body = item.get("body") or "无可提取文字/待人工查看"
    lines = [
        "---", f"title: {yaml_value(title)}",
        "summary: \"小红书收藏原始输入，内容用途待确认。\"",
        "tags: [小红书, 收藏]", "type: inbox", "status: raw", "source: xiaohongshu",
        f"source_url: {yaml_value(item.get('source_url'))}",
        f"source_id: {yaml_value(item.get('source_id'))}",
        f"source_collection: {yaml_value(item.get('source_collection'))}",
        f"author: {yaml_value(item.get('author'))}",
        f"created: {today}", f"updated: {today}", "confidentiality: personal", "ai_generated: false", "---", "",
        f"# {title}", "", "| 字段 | 内容 |", "|---|---|",
        f"| 作者 | {md_cell(item.get('author'))} |",
        f"| 收藏分组 | {md_cell(item.get('source_collection'))} |",
        f"| 媒体类型 | {md_cell(item.get('media_type'))} |",
        f"| 采集时间 | {md_cell(item.get('collected_at'))} |",
        f"| 原始链接 | [打开原文]({item.get('source_url', '')}) |", "", "## 原始正文或简介", "", body, ""
    ]
    return "\n".join(lines)


def report(items, files):
    rows = ["| 序号 | 标题 | 笔记ID | 作者 | 收藏分组 | 原始链接 | 同步状态 | 本地文件 | 备注 |",
            "|---:|---|---|---|---|---|---|---|---|"]
    for number, item in enumerate(items, 1):
        url = item.get("source_url", UNKNOWN)
        link = f"[打开原文]({url})" if url != UNKNOWN else UNKNOWN
        remarks = "；".join(item.get("issues", []))
        rows.append("| " + " | ".join(map(md_cell, [number, item.get("title"), item.get("source_id"), item.get("author"), item.get("source_collection"), link, item.get("sync_status", "待写入"), files.get(number, "未写入"), remarks])) + " |")
    counts = {}
    for item in items:
        status = item.get("sync_status", "待写入")
        counts[status] = counts.get(status, 0) + 1
    rows += ["", "| 发现 | 新增 | 更新候选 | 跳过 | 失败 | 待确认 |", "|---:|---:|---:|---:|---:|---:|",
             f"| {len(items)} | {counts.get('新增', 0)} | {counts.get('更新候选', 0)} | {counts.get('跳过', 0) + counts.get('跳过（已删除）', 0)} | 0 | {sum(bool(i.get('needs_confirmation')) for i in items)} |"]
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", help="规范化或合并后的 JSON")
    parser.add_argument("--output-dir", help="收藏笔记输出目录")
    parser.add_argument("--report", help="报告 Markdown 输出路径")
    parser.add_argument("--write", action="store_true", help="实际创建文件；默认仅打印报告")
    args = parser.parse_args()
    try:
        items = records_from_payload(load_json(args.records))
        if len(items) > 50:
            raise ValueError("单批超过 50 篇，请拆分后重试")
        files = {}
        if args.write:
            if not args.output_dir:
                raise ValueError("--write 时必须提供 --output-dir")
            directory = Path(args.output_dir)
            for number, item in enumerate(items, 1):
                if item.get("sync_status") not in (None, "", "新增"):
                    files[number] = "未写入"
                    continue
                stem = f"{item.get('source_id', UNKNOWN)}-{item.get('title', UNKNOWN)}"
                path = directory / safe_filename(stem)
                if path.exists():
                    files[number] = "跳过（文件已存在）"
                    continue
                atomic_write(path, note_text(item, date.today().isoformat()))
                files[number] = f"[[{path.stem}]]"
        text = report(items, files)
        if args.report:
            atomic_write(Path(args.report), text)
        else:
            sys.stdout.write(text)
        return 0
    except (OSError, ValueError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
