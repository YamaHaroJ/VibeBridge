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
    def test_unchanged_checkpoint_skips_github_write(self, run):
        import base64
        existing_body = (
            "_Last updated: 2026-10-16T10:00:00+00:00_\n\n"
            "### Durable project summary\nAlpha state"
        )
        existing = "## Conversation: conversation-1\n" + existing_body + "\n"
        encoded = base64.b64encode(existing.encode()).decode()
        run.side_effect = [
            Result(stdout="owner/alpha\n"),
            Result(stdout=json.dumps({"sha": "existing-sha", "content": encoded})),
        ]
        payload = {"projects": [{"repository": "owner/alpha", "summary": "Alpha state"}]}
        result = server.sync_message_checkpoint(json.dumps(payload), "conversation-1")
        self.assertTrue(result["saved"])
        self.assertTrue(result["projects"][0]["unchanged"])
        self.assertEqual(run.call_count, 2)

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


    def test_checkpoint_redaction_removes_common_tokens_and_passwords(self):
        sample = (
            "Bearer abcdefghijklmnop sk-proj-abcdefghijklmnopqrstuvwxyz "
            "ghp_abcdefghijklmnopqrstuvwxyz123456 password=hunter2 "
            "client_secret:supersecret"
        )
        cleaned = server.redact_checkpoint_text(sample)
        self.assertNotIn("abcdefghijklmnop", cleaned)
        self.assertNotIn("sk-proj-abcdefghijklmnopqrstuvwxyz", cleaned)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz123456", cleaned)
        self.assertNotIn("hunter2", cleaned)
        self.assertNotIn("supersecret", cleaned)
        self.assertIn("[REDACTED API KEY]", cleaned)



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
        cls.popup_source = (root / "extension" / "popup.js").read_text()
        cls.popup_html = (root / "extension" / "popup.html").read_text()
        cls.manifest = json.loads((root / "extension" / "manifest.json").read_text())

    def test_send_flow_automatically_attaches_detected_context_without_user_request_wrapper(self):
        self.assertIn('"VIBEBRIDGE_RESOLVE_CONTEXTS"', self.content_script)
        self.assertIn('conversationProjects[conversation] = merged.slice(-8)', self.content_script)
        self.assertIn('chrome.storage.local.get(["conversationProjects"])', self.content_script)
        self.assertNotIn("savedConversation.activeProject", self.content_script)
        self.assertNotIn("savedConversation.project", self.content_script)
        self.assertIn('if (!enabledState || !original', self.content_script)
        self.assertIn('function showNotice(_text) {}', self.content_script)
        self.assertIn('Automatically attach detected project context', self.content_script)
        self.assertIn('writeComposer(composer, addition + original)', self.content_script)
        self.assertNotIn('USER REQUEST:\\n', self.content_script)
        self.assertNotIn('function showContextChoice', self.content_script)
        self.assertIn('readComposer(composer).trim() !== original', self.content_script)
        self.assertIn('"Loaded Chrome extension version: " + extensionVersion', self.content_script)

    def test_assistant_memory_block_is_detected_and_forwarded(self):
        self.assertIn('language-vibebridge-memory|vibebridge-memory', self.content_script)
        self.assertIn('"VIBEBRIDGE_CHECKPOINT_MESSAGE"', self.content_script)
        self.assertIn('summary, conversation: conversationKey()', self.content_script)
        self.assertIn('pre.style.display = "none"', self.content_script)

    def test_background_routes_checkpoint_to_authenticated_local_agent(self):
        self.assertIn('"/checkpoint"', self.background)
        self.assertIn('"Authorization": "Bearer " + saved.token', self.background)
        self.assertIn('summary: payload.summary', self.background)


    def test_automatic_memory_is_explicitly_opt_in_and_scoped_to_matched_repository(self):
        self.assertEqual(self.manifest["version"], "0.2.93")
        self.assertIn('id="auto-memory"', self.popup_html)
        self.assertIn("autoMemoryCheckpoints", self.popup_source)
        self.assertIn("savedPreferences.autoMemoryCheckpoints", self.content_script)
        self.assertIn("When useful, append a compact fenced vibebridge-memory JSON checkpoint", self.content_script)
        self.assertIn('Include only durable project summary, handoff, todos, and decisions', self.content_script)
        self.assertIn("automatic saving", self.content_script)
        self.assertIn('pre.style.display = "none"', self.content_script)

    def test_browser_heartbeat_reports_loaded_version_without_conversation_data(self):
        self.assertIn('"VIBEBRIDGE_BROWSER_HEARTBEAT"', self.content_script)
        self.assertIn('window.__vibeBridgeHeartbeatTimer = window.setInterval(reportHeartbeatFromThisFile, 30000)', self.content_script)
        self.assertIn('id="browser-status"', self.popup_html)
        self.assertIn('refreshBrowserStatus(saved.token)', self.popup_source)
        self.assertIn('"ChatGPT extension heartbeat: "', self.popup_source)
        self.assertIn('chrome.runtime.getManifest().version', self.background)
        self.assertIn('"/extension-status"', self.background)
        self.assertIn('"VIBEBRIDGE_BROWSER_STATUS"', self.background)
        self.assertIn('"VIBEBRIDGE_PROBE_CHATGPT_TABS"', self.background)
        self.assertIn('"VIBEBRIDGE_CONTENT_SCRIPT_PING"', self.content_script)
        self.assertIn('chrome.scripting.executeScript', self.background)
        self.assertIn('data.browserExtension || {connected: false, version: null, host: null, lastSeen: null}', self.background)
        self.assertIn('browser_extension_snapshot()', self.server_source)
        self.assertIn('BROWSER_STATUS.update', self.server_source)
        self.assertIn('Unrecognized ChatGPT host', self.server_source)

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
