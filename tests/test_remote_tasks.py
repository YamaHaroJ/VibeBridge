import sys
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class RemoteTaskTests(unittest.TestCase):
    def test_only_predefined_tasks_are_accepted(self):
        with self.assertRaisesRegex(ValueError, "Unsupported remote task"):
            server.run_remote_task("rm -rf ~")

    @patch.object(server.subprocess, "run")
    @patch.object(server.Path, "home", return_value=Path("/tmp"))
    def test_validation_task_uses_fixed_commands(self, _home, run):
        with patch.object(Path, "is_dir", return_value=True):
            run.return_value = type("Completed", (), {
                "returncode": 0, "stdout": "ok", "stderr": ""
            })()
            ok, output = server.run_remote_task("validate")
        self.assertTrue(ok)
        self.assertIn("python3 -m py_compile", output)
        self.assertEqual(run.call_count, 6)
        for call in run.call_args_list:
            self.assertIsInstance(call.args[0], list)
            self.assertNotIn("shell", call.kwargs)


    @patch.object(server, "local_diagnostics", return_value={
        "ok": True, "service": "VibeBridge",
        "agent": {"loaded": True, "state": "running", "pid": 1234},
        "updater": {"loaded": False, "state": "not-loaded", "pid": None}
    })
    @patch.object(server.Path, "home", return_value=Path("/tmp"))
    def test_diagnostics_returns_allowlisted_local_service_snapshot_without_shell_commands(self, _home, diagnostics):
        with patch.object(Path, "is_dir", return_value=False):
            ok, output = server.run_remote_task("diagnostics")
        self.assertTrue(ok)
        self.assertIn('"service": "VibeBridge"', output)
        self.assertIn('"pid": 1234', output)
        self.assertIn('"schedule"', output)
        self.assertIn('"startIntervalSeconds": null', output)
        self.assertNotIn("tail -n", output)
        self.assertNotIn("process arguments", output)
        diagnostics.assert_called_once_with()

    @patch.object(server.subprocess, "run")
    @patch.object(server.Path, "home", return_value=Path("/tmp"))
    def test_test_task_runs_python_and_both_javascript_suites(self, _home, run):
        with patch.object(Path, "is_dir", return_value=True):
            run.return_value = type("Completed", (), {
                "returncode": 0, "stdout": "passed", "stderr": ""
            })()
            ok, output = server.run_remote_task("test")
        self.assertTrue(ok)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands, [
            ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            ["node", "tests/test_extension_bridge.js"],
            ["node", "tests/test_chatgpt_content_script.js"],
        ])
        self.assertIn("node tests/test_chatgpt_content_script.js", output)

    @patch.object(server.subprocess, "run")
    @patch.object(server.platform, "system", return_value="Darwin")
    @patch.object(server.platform, "mac_ver", return_value=("15.8.2", ("", "", ""), ""))
    def test_local_diagnostics_reports_revision_version_and_dirty_boolean_without_file_names(
            self, _mac_ver, _system, run):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "VibeBridge"
            manifest = root / "extension" / "manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"version": "0.2.87"}), encoding="utf-8")
            def result_for(args, **kwargs):
                if args[:2] == ["/bin/launchctl", "print"]:
                    return type("Completed", (), {
                        "returncode": 0, "stdout": "state = running\n pid = 1234\n", "stderr": ""
                    })()
                if args[:3] == ["git", "rev-parse", "--short"]:
                    return type("Completed", (), {
                        "returncode": 0, "stdout": "abc1234\n", "stderr": ""
                    })()
                if args[:3] == ["git", "status", "--porcelain"]:
                    return type("Completed", (), {
                        "returncode": 0, "stdout": " M private-file.txt\n", "stderr": ""
                    })()
                raise AssertionError("Unexpected diagnostics command: " + repr(args))
            run.side_effect = result_for
            with patch.object(server.Path, "home", return_value=Path(tmp)):
                (root / "agent").mkdir()
                result = server.local_diagnostics()
        self.assertEqual(result["checkout"]["revision"], "abc1234")
        self.assertEqual(result["checkout"]["extensionVersion"], "0.2.87")
        self.assertTrue(result["checkout"]["dirty"])
        self.assertNotIn("private-file.txt", json.dumps(result))
        self.assertEqual(run.call_count, 4)

    def test_task_enum_is_closed(self):
        self.assertEqual(server.REMOTE_TASK_POLL_SECONDS, 1)
        self.assertNotIn("--order", server.REMOTE_TASK_LIST_ARGS)
        self.assertEqual(server.REMOTE_TASK_LIST_ARGS[-2:], ["--limit", "100"])
        self.assertEqual(server.REMOTE_TASKS, {"validate", "test", "diagnostics", "terminal-smoke", "chatgpt-tabs", "macoptimizer-build", "macoptimizer-dedupe"})
        self.assertEqual(server.REMOTE_TASK_OWNER, "YamaHaroJ")


if __name__ == "__main__":
    unittest.main()
