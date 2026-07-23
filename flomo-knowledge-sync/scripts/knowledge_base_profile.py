#!/usr/bin/env python3
"""Discover a vault's local rules and render a stable flomo sync profile."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


RULE_FILES = ("AGENTS.md", "AI-RUNBOOK.md", "知识库规则/SCHEMA.md", "知识库规则/自动化任务.md")


def _read_rules(root: Path) -> tuple[str, list[str], str]:
    chunks: list[str] = []
    used: list[str] = []
    digest = hashlib.sha256()
    for relative in RULE_FILES:
        path = root / relative
        if path.is_file():
            data = path.read_bytes()
            digest.update(relative.encode("utf-8") + b"\0" + data)
            chunks.append(data.decode("utf-8", errors="replace"))
            used.append(relative)
    return "\n".join(chunks), used, digest.hexdigest()[:16]


def discover_profile(root: Path) -> dict[str, Any]:
    rules, files, fingerprint = _read_rules(root)
    target = "00-收件箱/浮墨笔记"
    path_match = re.search(r"`(00-收件箱/[^`]*浮墨[^`]*)/?`", rules)
    if path_match:
        target = path_match.group(1).rstrip("/")
    report_dir = "07-AI产出/每日整理报告"
    report_candidates = [x.rstrip("/") for x in re.findall(r"`(07-AI产出/[^`]*报告[^`]*)/?`", rules)]
    preferred = next((x for x in report_candidates if "每日整理报告" in x), None)
    if preferred:
        report_dir = preferred
    elif report_candidates:
        report_dir = report_candidates[0]
    batch_match = re.search(r"每批最多处理\s*(\d+)\s*篇", rules)
    batch_limit = int(batch_match.group(1)) if batch_match else 50
    confidentiality_disabled = bool(
        re.search(r"不再使用`?confidentiality`?|confidentiality.*不再", rules)
    )
    confidentiality_required = bool(
        re.search(r"confidentiality[^\n]{0,80}(?:必填|required)", rules, re.IGNORECASE)
    ) and not confidentiality_disabled
    preserve_history = bool(re.search(r"原始记录.*不得.*(?:覆盖|改写)", rules))
    inbox_lifecycle = bool(re.search(r"完成处理.*不再位于`?00-收件箱", rules))
    return {
        "profile_version": 1,
        "knowledge_base_fingerprint": fingerprint,
        "rules_files": files,
        "target_dir": target,
        "attachments_dir": f"{target}/附件",
        "index_path": f"{target}/浮墨同步索引.md",
        "profile_path": f"{target}/浮墨同步配置.md",
        "report_dir": report_dir,
        "batch_limit": batch_limit,
        "include_confidentiality": confidentiality_required,
        "preserve_source_history": preserve_history,
        "inbox_lifecycle": inbox_lifecycle,
        "migration_requires_manifest": True,
    }


def _value(raw: str) -> Any:
    raw = raw.strip()
    if raw in {"true", "false"}:
        return raw == "true"
    if raw.isdigit():
        return int(raw)
    if raw.startswith("[") and raw.endswith("]"):
        return [x.strip() for x in raw[1:-1].split(",") if x.strip()]
    return raw


def load_profile(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Profile has no YAML frontmatter: {path}")
    profile: dict[str, Any] = {}
    for line in parts[1].splitlines():
        match = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*)$", line)
        if match:
            profile[match.group(1)] = _value(match.group(2))
    return profile


def render_profile(profile: dict[str, Any], today: str) -> str:
    rules = ", ".join(profile.get("rules_files") or [])
    return f"""---
title: 浮墨同步配置
summary: 根据当前知识库规则自动生成的浮墨同步适配配置。
tags: [浮墨, 同步, 配置]
type: system
status: active
status_label: 活跃 / Active
source: ai
created: {today}
updated: {today}
ai_generated: true
profile_version: {profile['profile_version']}
knowledge_base_fingerprint: {profile['knowledge_base_fingerprint']}
rules_files: [{rules}]
target_dir: {profile['target_dir']}
attachments_dir: {profile['attachments_dir']}
index_path: {profile['index_path']}
report_dir: {profile['report_dir']}
batch_limit: {profile['batch_limit']}
include_confidentiality: {'true' if profile['include_confidentiality'] else 'false'}
preserve_source_history: {'true' if profile['preserve_source_history'] else 'false'}
inbox_lifecycle: {'true' if profile['inbox_lifecycle'] else 'false'}
migration_requires_manifest: true
---

# 浮墨同步配置

此配置由内置脚本首次运行时读取知识库规则生成。脚本按配置调整行为，不直接改写自身源码。

## 当前适配结果

- 目标目录：`{profile['target_dir']}`
- 索引：`{profile['index_path']}`
- 报告目录：`{profile['report_dir']}`
- 单批上限：{profile['batch_limit']}
- 写入 confidentiality：{'是' if profile['include_confidentiality'] else '否'}
- 保存来源更新历史：{'是' if profile['preserve_source_history'] else '否'}
- 收件箱生命周期规则存在：{'是' if profile['inbox_lifecycle'] else '否'}
- 归档执行技能：`close-confirmed-inbox`

## 维护规则

- `knowledge_base_fingerprint`变化时，先重新读取规则并刷新本配置，再执行同步。
- 人工可以复核配置，但不要在不理解影响时修改机器字段。
- 同步脚本不执行归档；迁出收件箱与索引闭环必须通过`close-confirmed-inbox`的统一审批门槛。
"""
