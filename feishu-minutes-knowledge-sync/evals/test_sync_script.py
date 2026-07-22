import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = SKILL_ROOT / "scripts" / "sync_minutes.py"


FAKE_CLI = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("lark-cli version test")
    raise SystemExit(0)
if args[:2] == ["auth", "status"]:
    print(json.dumps({"ok": True, "data": {"verified": True, "identities": {"user": {"status": "active"}}}}))
    raise SystemExit(0)
if args[:2] == ["minutes", "+search"]:
    updated = os.environ.get("FAKE_UPDATE", "2026-07-10T10:00:00+08:00")
    participant = "--participant-ids" in args
    page = args[args.index("--page-token") + 1] if "--page-token" in args else ""
    if not participant and not page:
        data = {"items": [{"token": "obcn-one", "title": "Weekly / Review", "created_at": "2026-07-10", "updated_at": updated}], "has_more": True, "page_token": "p2"}
    elif not participant:
        data = {"items": [{"token": "obcn-two", "title": "Planning", "created_at": "2026-07-11", "updated_at": updated}], "has_more": False}
    else:
        data = {"items": [{"token": "obcn-one", "title": "Duplicate", "updated_at": updated}], "has_more": False}
    print(json.dumps({"ok": True, "data": data}))
    raise SystemExit(0)
if args[:2] == ["minutes", "+detail"]:
    token = args[args.index("--minute-tokens") + 1]
    out = Path(args[args.index("--output-dir") + 1]) / ("artifact-" + token)
    out.mkdir(parents=True, exist_ok=True)
    transcript = out / "transcript.txt"
    transcript.write_text("Speaker A: exact source text for " + token + "\n", encoding="utf-8")
    minute = {
        "minute_token": token,
        "title": "Weekly Review" if token == "obcn-one" else "Planning",
        "note_id": "note-" + token,
        "created_at": "2026-07-10" if token == "obcn-one" else "2026-07-11",
        "url": "https://example.invalid/minutes/" + token,
        "artifacts": {
            "summary": "source summary " + token,
            "todos": [{"content": "source todo"}],
            "chapters": [{"title": "chapter"}],
            "keywords": ["keyword"],
            "transcript_file": str(transcript),
        },
    }
    print(json.dumps({"ok": True, "data": {"minutes": [minute]}}))
    raise SystemExit(0)
print(json.dumps({"ok": False, "error": {"message": "unexpected args", "args": args}}), file=sys.stderr)
raise SystemExit(1)
'''


class SyncScriptTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cli = self.root / "lark-cli"
        self.cli.write_text(FAKE_CLI, encoding="utf-8")
        self.cli.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def run_sync(self, update=None, extra=None):
        cmd = [
            sys.executable, str(SYNC_SCRIPT), "sync",
            "--cli", str(self.cli), "--profile", "team-a",
            "--knowledge-base", str(self.root),
            "--target-dir", "inbox/minutes",
            "--index-path", "inbox/minutes/index.md",
            "--report-path", "reports/sync.md",
            "--start", "2026-07-01", "--end", "2026-07-17",
            "--scope", "all-related", "--confidentiality", "private",
        ]
        cmd.extend(extra or [])
        env = os.environ.copy()
        if update:
            env["FAKE_UPDATE"] = update
        return subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    def test_sync_then_idempotent_resync(self):
        first = self.run_sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        result = json.loads(first.stdout)
        self.assertEqual(result["added"], 2)
        self.assertEqual(result["skipped"], 0)

        notes = sorted((self.root / "inbox" / "minutes").glob("*.md"))
        content_notes = [p for p in notes if p.name != "index.md"]
        self.assertEqual(len(content_notes), 4)
        summaries = [p for p in content_notes if p.name.endswith("智能纪要.md")]
        transcripts = [p for p in content_notes if p.name.endswith("原始逐字稿.md")]
        self.assertEqual(len(summaries), 2)
        self.assertEqual(len(transcripts), 2)
        for summary in summaries:
            text = summary.read_text(encoding="utf-8")
            self.assertIn("[[", text)
            self.assertIn("source summary", text)
            self.assertIn("capture_types: []", text)
            self.assertIn('ai_processing_status: "unprocessed"', text)
            self.assertIn('article_extraction_status: "not_applicable"', text)
            self.assertIn("<!-- AI:START -->", text)
            self.assertIn("<!-- AI:END -->", text)
        for transcript in transcripts:
            text = transcript.read_text(encoding="utf-8")
            self.assertIn("[[", text)
            self.assertIn("exact source text", text)
            self.assertIn('transcript_review_status: "pending_review"', text)
            self.assertIn('transcript_text_source: ""', text)
            self.assertIn('corrected_transcript: ""', text)
            self.assertIn("人工校订闸门", text)

        index = (self.root / "inbox" / "minutes" / "index.md").read_text(encoding="utf-8")
        self.assertIn("FEISHU_MINUTES_SYNC_STATE:START", index)
        self.assertEqual(index.count('"minute_token": "obcn-'), 2)

        second = self.run_sync()
        self.assertEqual(second.returncode, 0, second.stderr)
        second_result = json.loads(second.stdout)
        self.assertEqual(second_result["added"], 0)
        self.assertEqual(second_result["skipped"], 2)
        self.assertEqual(len([p for p in (self.root / "inbox" / "minutes").glob("*.md") if p.name != "index.md"]), 4)

    def test_deleted_is_permanent_and_excluded_paths_are_not_read(self):
        first = self.run_sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        index_path = self.root / "inbox" / "minutes" / "index.md"
        text = index_path.read_text(encoding="utf-8")
        start = "<!-- FEISHU_MINUTES_SYNC_STATE:START -->"
        end = "<!-- FEISHU_MINUTES_SYNC_STATE:END -->"
        raw = text.split(start, 1)[1].split(end, 1)[0].strip()[len("```json"):].strip()
        raw = raw[:-3].strip()
        state = json.loads(raw)
        one, two = state["items"]
        one["local_state"] = "deleted"
        one["pair_state"] = "deleted"
        one["sync_action"] = "deleted"
        two["summary_path"] = "archive/summary.md"
        two["transcript_path"] = "archive/transcript.md"
        two["local_state"] = "present"
        replacement = start + "\n```json\n" + json.dumps(state, ensure_ascii=False, indent=2) + "\n```\n" + end
        before, rest = text.split(start, 1)
        _, after = rest.split(end, 1)
        index_path.write_text(before + replacement + after, encoding="utf-8")

        second = self.run_sync(extra=["--skip-local-validation-prefix", "archive"])
        self.assertEqual(second.returncode, 0, second.stderr)
        result = json.loads(second.stdout)
        self.assertEqual(result["deleted_skipped"], 1)
        self.assertEqual(result["added"], 0)
        rebuilt = index_path.read_text(encoding="utf-8")
        self.assertIn("| deleted |", rebuilt)
        self.assertIn('"local_validation": "skipped"', rebuilt)

    def test_source_update_is_reported_without_overwrite(self):
        first = self.run_sync(update="2026-07-10T10:00:00+08:00")
        self.assertEqual(first.returncode, 0, first.stderr)
        summary = next((self.root / "inbox" / "minutes").glob("*Weekly Review*智能纪要.md"))
        original = summary.read_text(encoding="utf-8")
        second = self.run_sync(update="2026-07-12T10:00:00+08:00")
        self.assertEqual(second.returncode, 0, second.stderr)
        result = json.loads(second.stdout)
        self.assertEqual(result["source_updates_pending"], 2)
        self.assertEqual(summary.read_text(encoding="utf-8"), original)

    def test_selected_folder_beats_user_input(self):
        selected = self.root / "selected"
        selected.mkdir()
        result = self.run_sync(extra=["--selected-folder", str(selected)])
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["knowledge_base_source"], "selected-folder")
        self.assertEqual(Path(payload["knowledge_base"]).resolve(), selected.resolve())
        self.assertTrue((selected / "inbox" / "minutes" / "index.md").exists())
        self.assertFalse((self.root / "inbox" / "minutes" / "index.md").exists())

    def test_default_folder_is_created_when_no_other_path_exists(self):
        cmd = [
            sys.executable, str(SYNC_SCRIPT), "sync",
            "--cli", str(self.cli), "--profile", "team-a",
            "--default-folder", "default-kb",
            "--target-dir", "minutes", "--index-path", "minutes/index.md",
            "--report-path", "reports/sync.md", "--start", "2026-07-01", "--end", "2026-07-17",
        ]
        result = subprocess.run(cmd, cwd=self.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["knowledge_base_source"], "default-folder")
        self.assertTrue((self.root / "default-kb" / "minutes" / "index.md").exists())


if __name__ == "__main__":
    unittest.main()
