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
        self.assertIn('run.textContent = result?.ok ? "Run again" : "Retry"', page)

    def test_file_read_write_list_tools_are_wired_like_run(self):
        # These exist so file edits go through a clean overwrite instead of
        # ChatGPT constructing shell heredocs/sed for every change — closer to
        # how an actual coding agent works.
        background = (EXTENSION / "background.js").read_text()
        page = (EXTENSION / "chatgpt.js").read_text()
        for message_type in ("VIBEBRIDGE_FILESYSTEM_READ", "VIBEBRIDGE_FILESYSTEM_WRITE", "VIBEBRIDGE_FILESYSTEM_LIST"):
            self.assertIn('"' + message_type + '"', background)
            self.assertIn(message_type, page)
        self.assertIn("const ACTIONS = {", page)
        self.assertIn("autoRunCommands !== false", page)

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

    def test_periodic_check_reloads_extension_after_manifest_version_changes_on_disk(self):
        background = (EXTENSION / "background.js").read_text()
        start = background.index("async function checkForInstalledExtensionUpdate()")
        end = background.index("chrome.alarms?.onAlarm?.addListener?.(alarm => {", start)
        check = background[start:end]
        self.assertIn('fetchAgent("/diagnostics/local"', check)
        self.assertIn("data?.checkout?.extensionVersion", check)
        self.assertIn("diskVersion !== loadedVersion", check)
        self.assertIn("chrome.runtime.reload()", check)

    def test_periodic_chatgpt_recovery_alarm_is_declared_and_registered(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text())
        background = (EXTENSION / "background.js").read_text()
        self.assertIn("alarms", manifest["permissions"])
        self.assertIn('chrome.alarms?.create?.(CHATGPT_RECOVERY_ALARM, {periodInMinutes: 1})', background)
        self.assertIn('chrome.alarms?.onAlarm?.addListener?.(alarm => {', background)
        self.assertIn("if (alarm?.name === CHATGPT_RECOVERY_ALARM) {", background)
        self.assertIn("recoverOpenChatGPTTabs();", background)
        self.assertIn("checkForInstalledExtensionUpdate();", background)

    def test_chatgpt_tab_activation_recovers_content_script_heartbeat(self):
        background = (EXTENSION / "background.js").read_text()
        self.assertIn('chrome.tabs?.onActivated?.addListener?.(({tabId}) => { ensureChatGPTTabHeartbeat(tabId); });', background)
        self.assertIn('chrome.tabs?.onUpdated?.addListener?.((tabId, changeInfo)', background)
        self.assertIn('files: ["chatgpt.js"]', background)

    def test_manual_chatgpt_probe_retries_heartbeat_after_script_injection(self):
        background = (EXTENSION / "background.js").read_text()
        start = background.index('if (message?.type === "VIBEBRIDGE_PROBE_CHATGPT_TABS")')
        end = background.index('(async () => {', start)
        probe = background[start:end]
        self.assertIn('await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ["chatgpt.js"]})', probe)
        self.assertIn('for (let attempt = 0; attempt < 4 && !reply?.alive; attempt++)', probe)
        self.assertIn('setTimeout(resolve, 100)', probe)
        self.assertIn('contentScript: reply?.alive === true', probe)

    def test_heartbeat_recovery_pings_before_injecting_to_avoid_duplicate_setup(self):
        background = (EXTENSION / "background.js").read_text()
        start = background.index("async function ensureChatGPTTabHeartbeat")
        end = background.index("async function recoverOpenChatGPTTabs", start)
        recovery = background[start:end]
        ping = recovery.index('chrome.tabs.sendMessage(tabId, {type: "VIBEBRIDGE_CONTENT_SCRIPT_PING"})')
        inject = recovery.index('chrome.scripting.executeScript({target: {tabId}, files: ["chatgpt.js"]})')
        self.assertLess(ping, inject, "check for a live content script before injecting")
        self.assertIn("if (reply?.alive) return;", recovery)
        self.assertIn("catch (_) {}", recovery, "failed ping must fall through to reinjection")


if __name__ == "__main__":
    unittest.main()
