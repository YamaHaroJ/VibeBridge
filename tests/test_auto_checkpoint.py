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

    def test_malformed_structured_json_is_rejected_without_github_access(self):
        with patch("server.subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "JSON is malformed"):
                server.sync_message_checkpoint('{"projects": [broken', "chat")
            run.assert_not_called()

    @patch("server.subprocess.run")
    def test_saves_each_project_separately(self, run):
        run.side_effect = [
            Result(stdout="owner/alpha" + chr(10)), Result(1, stderr="404 Not Found"), Result(),
            Result(stdout="owner/beta" + chr(10)), Result(1, stderr="404 Not Found"), Result(),
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


class ExtensionFlowContractTests(unittest.TestCase):
    """Regression tests for the browser-to-checkpoint handoff contract.

    These tests inspect the shipped content script and background bridge so the
    test suite fails if the key message types or persistence steps are removed.
    These are source-contract tests, not a full browser DOM simulation.
    """

    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.content_script = (root / "extension" / "chatgpt.js").read_text()
        cls.background = (root / "extension" / "background.js").read_text()
        cls.server_source = (root / "agent" / "server.py").read_text()

    def test_send_flow_resolves_context_without_mutating_user_composer(self):
        self.assertIn('"VIBEBRIDGE_RESOLVE_CONTEXTS"', self.content_script)
        self.assertIn('conversationProjects[conversation] = merged.slice(-8)', self.content_script)
        self.assertIn('if (!enabledState || !original', self.content_script)
        self.assertIn('Automatic injection is paused to protect your message', self.content_script)
        self.assertNotIn('writeComposer(composer, addition + original)', self.content_script)

    def test_assistant_memory_block_is_detected_and_forwarded(self):
        self.assertIn('language-vibebridge-memory|vibebridge-memory', self.content_script)
        self.assertIn('"VIBEBRIDGE_CHECKPOINT_MESSAGE"', self.content_script)
        self.assertIn('summary, conversation: conversationKey()', self.content_script)
        self.assertIn('pre.style.display = "none"', self.content_script)

    def test_background_routes_checkpoint_to_authenticated_local_agent(self):
        self.assertIn('"/checkpoint"', self.background)
        self.assertIn('"Authorization": "Bearer " + saved.token', self.background)
        self.assertIn('summary: payload.summary', self.background)

    def test_server_persists_handoff_todos_and_decisions(self):
        self.assertIn('### Latest conversation handoff', self.server_source)
        self.assertIn('### Living todo list', self.server_source)
        self.assertIn('### Durable decisions', self.server_source)
        self.assertIn('memory/AUTO_CHECKPOINT.md', self.server_source)

    def test_context_recovery_reads_shared_checkpoint(self):
        self.assertIn('AUTO_CHECKPOINT.md', self.server_source)
        self.assertIn('remote_repo_context', self.server_source)


if __name__ == "__main__":
    unittest.main()
