#!/usr/bin/env python3
"""Read-only structural audit for Feishu Minutes source packages."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip('"\'')
    return result


def resolve_note(vault: Path, raw: str) -> Path:
    candidate = (vault / raw).resolve()
    if candidate.suffix != ".md":
        candidate = candidate.with_suffix(".md")
    return candidate


def parse_table(index_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell or "-") for cell in cells):
            continue
        if headers is None:
            headers = cells
            continue
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def find_value(row: dict[str, str], names: tuple[str, ...]) -> str:
    for key, value in row.items():
        normalized = key.lower().replace(" ", "_")
        if normalized in names:
            match = WIKILINK_RE.search(value)
            return match.group(1).strip() if match else value.strip(" `")
    return ""


def audit(vault: Path, index_path: Path) -> dict:
    issues: list[dict[str, str]] = []
    packages: list[dict[str, str]] = []
    seen: set[str] = set()
    vault = vault.resolve()

    for row in parse_table(index_path):
        token = find_value(row, ("minute_token", "token", "来源id", "来源_id"))
        summary_raw = find_value(row, ("summary_path", "智能纪要", "智能纪要路径"))
        transcript_raw = find_value(row, ("transcript_path", "原始逐字稿", "逐字稿路径"))
        package_id = token or find_value(row, ("source_group_id", "来源包")) or "unknown"
        if package_id in seen:
            issues.append({"severity": "error", "package": package_id, "problem": "duplicate package identifier"})
        seen.add(package_id)

        record = {"package": package_id, "summary": summary_raw, "transcript": transcript_raw}
        packages.append(record)
        paths: dict[str, Path] = {}
        for role, raw in (("summary", summary_raw), ("transcript", transcript_raw)):
            if not raw:
                issues.append({"severity": "error", "package": package_id, "problem": f"missing {role} path"})
                continue
            path = resolve_note(vault, raw)
            try:
                path.relative_to(vault)
            except ValueError:
                issues.append({"severity": "error", "package": package_id, "problem": f"{role} path escapes vault"})
                continue
            paths[role] = path
            if not path.is_file():
                issues.append({"severity": "error", "package": package_id, "problem": f"missing {role} file", "path": raw})

        if len(paths) != 2 or not all(p.is_file() for p in paths.values()):
            continue
        sm = frontmatter(paths["summary"])
        tm = frontmatter(paths["transcript"])
        sg = sm.get("source_group_id") or sm.get("minute_token") or sm.get("source_id")
        tg = tm.get("source_group_id") or tm.get("minute_token") or tm.get("source_id")
        if not sg or sg != tg:
            issues.append({"severity": "error", "package": package_id, "problem": "source group mismatch"})

        review = tm.get("transcript_review_status", "")
        source = tm.get("transcript_text_source", "")
        if review == "ready_for_extraction" and source not in {"original", "corrected"}:
            issues.append({"severity": "error", "package": package_id, "problem": "invalid transcript_text_source"})
        if review == "pending_review" and source:
            issues.append({"severity": "warning", "package": package_id, "problem": "text source set before review is ready"})
        if source == "corrected":
            corrected = tm.get("corrected_transcript", "")
            match = WIKILINK_RE.search(corrected)
            corrected_raw = match.group(1).strip() if match else corrected.strip(" `")
            if not corrected_raw or not resolve_note(vault, corrected_raw).is_file():
                issues.append({"severity": "error", "package": package_id, "problem": "missing corrected transcript"})

        summary_text = paths["summary"].read_text(encoding="utf-8")
        transcript_text = paths["transcript"].read_text(encoding="utf-8")
        if paths["transcript"].stem not in summary_text or paths["summary"].stem not in transcript_text:
            issues.append({"severity": "warning", "package": package_id, "problem": "pair backlink missing"})

    return {
        "index": str(index_path),
        "package_count": len(packages),
        "error_count": sum(i["severity"] == "error" for i in issues),
        "warning_count": sum(i["severity"] == "warning" for i in issues),
        "issues": issues,
        "packages": packages,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    index_path = args.index if args.index.is_absolute() else args.vault / args.index
    result = audit(args.vault, index_path.resolve())
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 1 if result["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
