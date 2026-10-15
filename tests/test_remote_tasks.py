import sys
import unittest
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

    def test_task_enum_is_closed(self):
        self.assertEqual(server.REMOTE_TASK_POLL_SECONDS, 2)
        self.assertNotIn("--order", server.REMOTE_TASK_LIST_ARGS)
        self.assertEqual(server.REMOTE_TASK_LIST_ARGS[-2:], ["--limit", "100"])
        self.assertEqual(server.REMOTE_TASKS, {"validate", "test", "diagnostics"})
        self.assertEqual(server.REMOTE_TASK_OWNER, "YamaHaroJ")


if __name__ == "__main__":
    unittest.main()
