#!/usr/bin/env python3
"""Dependency-free smoke tests for bundled scripts."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURE = ROOT / "tests" / "fixtures" / "browser-records.json"


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], check=True, text=True, capture_output=True)


with tempfile.TemporaryDirectory() as temporary:
    work = Path(temporary)
    normalized = work / "normalized.json"
    index = work / "index.md"
    preview = work / "preview.md"
    batch = work / "batch.json"
    notes = work / "notes"
    report = work / "report.md"
    index.write_text("# 索引\n\n<!-- AI:START -->\n```yaml\nitems: []\n```\n<!-- AI:END -->\n", encoding="utf-8")

    run(SCRIPTS / "normalize_records.py", FIXTURE, "-o", normalized, "--collected-at", "2026-07-17T12:00:00+08:00")
    items = json.loads(normalized.read_text(encoding="utf-8"))["items"]
    assert len(items) == 2
    assert items[0]["source_id"] == "abc123"
    assert "utm_source" not in items[0]["source_url"]
    assert "xsec_token=token-a" in items[0]["source_url"]
    assert items[1]["needs_confirmation"] is True

    run(SCRIPTS / "merge_index.py", index, normalized, "--output", preview, "--records-output", batch)
    batch_items = json.loads(batch.read_text(encoding="utf-8"))["items"]
    assert batch_items[0]["sync_status"] == "新增"
    assert "<!-- AI:START -->" in preview.read_text(encoding="utf-8")

    run(SCRIPTS / "render_markdown.py", batch, "--output-dir", notes, "--report", report, "--write")
    assert len(list(notes.glob("*.md"))) == 2
    assert "| 序号 | 标题 |" in report.read_text(encoding="utf-8")

    run(SCRIPTS / "merge_index.py", index, normalized, "--write")
    assert '"source_id": "abc123"' in index.read_text(encoding="utf-8")

print("3 个脚本的标准化、去重、渲染和原子写回测试通过。")
