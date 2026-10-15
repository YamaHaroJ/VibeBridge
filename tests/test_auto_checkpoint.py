import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class AutomaticCheckpointTests(unittest.TestCase):
    def test_empty_summary_is_rejected_before_github_access(self):
        with self.assertRaisesRegex(ValueError, "assistant summary is empty"):
            server.sync_message_checkpoint("  ", "chat")

    def test_missing_projects_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "No project summaries"):
            server.sync_message_checkpoint(json.dumps({"projects": []}), "chat")

    @patch("server.subprocess.run")
    def test_saves_each_project_separately(self, run):
        run.side_effect = [
            Result(stdout="owner/alpha\\n"), Result(1, stderr="404 Not Found"), Result(),
            Result(stdout="owner/beta\\n"), Result(1, stderr="404 Not Found"), Result(),
        ]
        payload = {"projects": [
            {"repository": "owner/alpha", "summary": "Alpha state"},
            {"repository": "owner/beta", "summary": "Beta state"},
        ]}
        result = server.sync_message_checkpoint(json.dumps(payload), "conversation-1")
        self.assertEqual([item["repository"] for item in result["projects"]], ["owner/alpha", "owner/beta"])
        calls = run.call_args_list
        self.assertIn("owner/alpha/contents/memory/AUTO_CHECKPOINT.md", " ".join(calls[2].args[0]))
        self.assertIn("owner/beta/contents/memory/AUTO_CHECKPOINT.md", " ".join(calls[5].args[0]))


if __name__ == "__main__":
    unittest.main()
