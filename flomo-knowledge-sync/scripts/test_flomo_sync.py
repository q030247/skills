#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("flomo_sync.py")


class SyncTest(unittest.TestCase):
    def run_sync(self, vault: Path, payload: dict, apply: bool = False):
        source = vault / "memos.json"
        source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        cmd = [sys.executable, str(SCRIPT), "--vault", str(vault), "--input", str(source)]
        if apply:
            cmd.append("--apply")
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
            self.assertEqual(dry["counts"], {"add": 1})
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
            self.assertEqual(result["operations"], [])

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


if __name__ == "__main__":
    unittest.main()
