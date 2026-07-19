#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("flomo_sync.py")


class SyncTest(unittest.TestCase):
    def run_sync(self, vault: Path, payload: dict, apply: bool = False, extra=None):
        source = vault / "memos.json"
        source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        cmd = [sys.executable, str(SCRIPT), "--vault", str(vault), "--input", str(source)]
        if apply:
            cmd.append("--apply")
        if extra:
            cmd.extend(extra)
        return subprocess.run(cmd, text=True, capture_output=True, check=True)

    def test_dry_run_then_add_and_skip(self):
        memo = {
            "id": "memo-1", "content": "第一条想法", "content_truncated": False,
            "created_at": "2026-07-17T08:00:00+08:00", "updated_at": "2026-07-17T08:00:00+08:00",
            "url": "https://example.invalid/memo-1", "tags": ["想法"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            dry = json.loads(self.run_sync(vault, {"memos": [memo]}).stdout)
            self.assertEqual(dry["counts"], {"add": 1, "configure_profile": 1})
            self.assertFalse((vault / "00-收件箱/浮墨笔记").exists())
            self.run_sync(vault, {"memos": [memo]}, apply=True)
            index = vault / "00-收件箱/浮墨笔记/浮墨同步索引.md"
            self.assertIn("memo_id: memo-1", index.read_text(encoding="utf-8"))
            again = json.loads(self.run_sync(vault, {"memos": [memo]}).stdout)
            self.assertEqual(again["counts"], {"skip": 1})

    def test_local_delete_is_preserved(self):
        memo = {
            "id": "memo-2", "content": "保留删除", "content_truncated": False,
            "created_at": "2026-07-17T09:00:00+08:00", "updated_at": "2026-07-17T09:00:00+08:00",
            "url": "https://example.invalid/memo-2", "tags": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            self.run_sync(vault, {"memos": [memo]}, apply=True)
            note = next((vault / "00-收件箱/浮墨笔记").glob("2026-*.md"))
            note.unlink()
            result = json.loads(self.run_sync(vault, {"memos": [memo]}, apply=True).stdout)
            actions = [x["action"] for x in result["operations"]]
            self.assertIn("mark_local_deleted", actions)
            index = vault / "00-收件箱/浮墨笔记/浮墨同步索引.md"
            self.assertIn("local_state: missing", index.read_text(encoding="utf-8"))

    def test_existing_index_with_attachment_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            target = vault / "00-收件箱/浮墨笔记"
            target.mkdir(parents=True)
            (target / "existing.md").write_text("---\nsource_id: memo-3\n---\n", encoding="utf-8")
            (target / "附件").mkdir()
            (target / "附件/file.jpeg").write_bytes(b"jpeg")
            (target / "浮墨同步索引.md").write_text("""---
index_version: 1
identity_key: memo_id
items:
  - memo_id: memo-3
    source_created_at: 2026-07-17T09:00:00+08:00
    source_updated_at: 2026-07-17T09:00:00+08:00
    local_path: 00-收件箱/浮墨笔记/existing.md
    local_state: present
    sync_action: added
    is_deleted: false
    attachments:
      - 00-收件箱/浮墨笔记/附件/file.jpeg
---
""", encoding="utf-8")
            result = json.loads(self.run_sync(vault, {"memos": []}).stdout)
            self.assertEqual([x["action"] for x in result["operations"]], ["configure_profile"])

    def test_explicit_restore_recreates_deleted_note(self):
        memo = {
            "id": "memo-4", "content": "明确恢复", "content_truncated": False,
            "created_at": "2026-07-17T10:00:00+08:00", "updated_at": "2026-07-17T10:00:00+08:00",
            "url": "https://example.invalid/memo-4", "tags": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            self.run_sync(vault, {"memos": [memo]}, apply=True)
            note = next((vault / "00-收件箱/浮墨笔记").glob("2026-*.md"))
            note.unlink()
            self.run_sync(vault, {"memos": []}, apply=True)
            source = vault / "memos.json"
            source.write_text(json.dumps({"memos": [memo]}), encoding="utf-8")
            cmd = [sys.executable, str(SCRIPT), "--vault", str(vault), "--input", str(source), "--restore-deleted", "--apply"]
            result = json.loads(subprocess.run(cmd, text=True, capture_output=True, check=True).stdout)
            self.assertIn("restore", [x["action"] for x in result["operations"]])
            self.assertTrue(note.is_file())

    def test_first_run_adapts_to_agents_and_removes_confidentiality(self):
        memo = {
            "id": "memo-5", "content": "自动适配", "content_truncated": False,
            "created_at": "2026-07-19T08:00:00+08:00", "updated_at": "2026-07-19T08:00:00+08:00",
            "url": "https://example.invalid/memo-5", "tags": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "AGENTS.md").write_text(
                "浮墨同步只写入`00-收件箱/浮墨笔记/`。知识库不再使用`confidentiality`分级。"
                "原始记录是源数据，不得删除、覆盖、改写。每批最多处理50篇。",
                encoding="utf-8",
            )
            self.run_sync(vault, {"memos": [memo]}, apply=True)
            profile = vault / "00-收件箱/浮墨笔记/浮墨同步配置.md"
            self.assertIn("include_confidentiality: false", profile.read_text(encoding="utf-8"))
            note = next((vault / "00-收件箱/浮墨笔记").glob("2026-*.md"))
            self.assertNotIn("confidentiality:", note.read_text(encoding="utf-8"))

    def test_source_update_keeps_previous_original(self):
        memo = {
            "id": "memo-6", "content": "旧原文", "content_truncated": False,
            "created_at": "2026-07-19T09:00:00+08:00", "updated_at": "2026-07-19T09:00:00+08:00",
            "url": "https://example.invalid/memo-6", "tags": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "AGENTS.md").write_text("原始记录是源数据，不得删除、覆盖、改写。", encoding="utf-8")
            self.run_sync(vault, {"memos": [memo]}, apply=True)
            memo["content"] = "新原文"
            memo["updated_at"] = "2026-07-19T10:00:00+08:00"
            self.run_sync(vault, {"memos": [memo]}, apply=True)
            note = next((vault / "00-收件箱/浮墨笔记").glob("2026-*.md"))
            text = note.read_text(encoding="utf-8")
            self.assertIn("## 原始内容\n\n新原文", text)
            self.assertIn("## 来源更新历史", text)
            self.assertIn("旧原文", text)

    def test_relocation_updates_index_without_marking_deleted(self):
        memo = {
            "id": "memo-7", "content": "迁移来源", "content_truncated": False,
            "created_at": "2026-07-19T11:00:00+08:00", "updated_at": "2026-07-19T11:00:00+08:00",
            "url": "https://example.invalid/memo-7", "tags": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            self.run_sync(vault, {"memos": [memo]}, apply=True)
            note = next((vault / "00-收件箱/浮墨笔记").glob("2026-*.md"))
            destination = vault / "99-归档/浮墨/source.md"
            destination.parent.mkdir(parents=True)
            note.rename(destination)
            manifest = vault / "relocations.json"
            manifest.write_text(json.dumps({"relocations": [{
                "memo_id": "memo-7", "local_path": "99-归档/浮墨/source.md", "destination_type": "archive"
            }]}), encoding="utf-8")
            self.run_sync(vault, {"memos": []}, apply=True, extra=["--relocate-manifest", str(manifest)])
            index = (vault / "00-收件箱/浮墨笔记/浮墨同步索引.md").read_text(encoding="utf-8")
            self.assertIn("local_state: moved", index)
            self.assertIn("local_path: 99-归档/浮墨/source.md", index)
            self.assertNotIn("local_state: missing", index)

    def test_report_failure_does_not_create_note_or_advance_index(self):
        memo = {
            "id": "memo-8", "content": "事务测试", "content_truncated": False,
            "created_at": "2026-07-19T12:00:00+08:00", "updated_at": "2026-07-19T12:00:00+08:00",
            "url": "https://example.invalid/memo-8", "tags": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            blocker = vault / "blocker"
            blocker.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(subprocess.CalledProcessError):
                self.run_sync(vault, {"memos": [memo]}, apply=True, extra=["--report", "blocker/report.md"])
            self.assertFalse((vault / "00-收件箱/浮墨笔记/浮墨同步索引.md").exists())
            self.assertEqual(list((vault / "00-收件箱/浮墨笔记").glob("2026-*.md")), [])

    def test_apply_always_creates_markdown_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            self.run_sync(vault, {"memos": []}, apply=True)
            reports = list((vault / "07-AI产出/每日整理报告").glob("*-浮墨增量同步报告.md"))
            self.assertEqual(len(reports), 1)
            self.assertIn("报告与索引在同一批本地事务中写入", reports[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
