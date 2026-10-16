import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extension"


class ExtensionContractTests(unittest.TestCase):
    def test_manifest_version_is_valid_and_release_format(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text())
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["manifest_version"], 3)

    def test_chatgpt_command_button_matches_background_allowlist(self):
        page = (EXTENSION / "chatgpt.js").read_text()
        background = (EXTENSION / "background.js").read_text()
        self.assertIn('type: "VIBEBRIDGE_RUN_COMMAND"', page)
        self.assertIn('"VIBEBRIDGE_RUN_COMMAND"', background)
        self.assertIn("payload.command", page)

    def test_command_success_requires_zero_exit_code(self):
        background = (EXTENSION / "background.js").read_text()
        page = (EXTENSION / "chatgpt.js").read_text()
        self.assertIn("ok: data.exitCode === 0", background)
        self.assertIn('run.textContent = result?.ok ? "Run again" : "Retry command"', page)

    def test_run_request_is_authenticated_and_targets_selected_project(self):
        background = (EXTENSION / "background.js").read_text()
        start = background.index('if (message.type === "VIBEBRIDGE_RUN_COMMAND")')
        end = background.index("const multiProject", start)
        handler = background[start:end]
        self.assertIn('fetchAgent("/run"', handler)
        self.assertIn('"Authorization": "Bearer " + saved.token', handler)
        self.assertIn("JSON.stringify({project: active, command})", handler)
        self.assertIn("!active", handler)
        self.assertIn("command.length > 40", handler)

    def test_chatgpt_tab_activation_recovers_content_script_heartbeat(self):
        background = (EXTENSION / "background.js").read_text()
        self.assertIn('chrome.tabs?.onActivated?.addListener?.(({tabId}) => { ensureChatGPTTabHeartbeat(tabId); });', background)
        self.assertIn('chrome.tabs?.onUpdated?.addListener?.((tabId, changeInfo)', background)
        self.assertIn('files: ["chatgpt.js"]', background)


if __name__ == "__main__":
    unittest.main()
