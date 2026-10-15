import sys
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class LocalDiagnosticsTests(unittest.TestCase):
    @patch.object(server.platform, "system", return_value="Darwin")
    @patch.object(server.platform, "mac_ver", return_value=("15.0", ("", "", ""), ""))
    @patch.object(server.os, "getuid", return_value=501)
    @patch.object(server.subprocess, "run")
    def test_reports_only_allowlisted_launch_service_metadata(self, run, _uid, _mac, _system):
        def launchctl_result(command, **_kwargs):
            label = command[-1].split("/")[-1]
            if label == "com.vibebridge.agent":
                return type("Completed", (), {
                    "returncode": 0,
                    "stdout": "state = running\npid = 1234\nSECRET_SHOULD_NOT_LEAK\n",
                    "stderr": ""
                })()
            return type("Completed", (), {
                "returncode": 1, "stdout": "", "stderr": "Could not find service"
            })()
        run.side_effect = launchctl_result

        result = server.local_diagnostics()

        self.assertTrue(result["ok"])
        self.assertEqual(result["agent"]["pid"], 1234)
        self.assertEqual(result["agent"]["requestPid"], server.os.getpid())
        self.assertTrue(result["agent"]["loaded"])
        self.assertFalse(result["updater"]["loaded"])
        self.assertEqual(result["osVersion"], "15.0")
        self.assertNotIn("SECRET_SHOULD_NOT_LEAK", repr(result))
        self.assertNotIn("logs", result)
        self.assertNotIn("processList", result)
        self.assertEqual(run.call_count, 2)

    @patch.object(server.platform, "system", return_value="Linux")
    @patch.object(server.subprocess, "run")
    def test_non_macos_reports_unavailable_services_without_running_launchctl(self, run, _system):
        result = server.local_diagnostics()
        self.assertEqual(result["platform"], "Linux")
        self.assertEqual(result["agent"]["state"], "unavailable-on-this-platform")
        self.assertEqual(result["updater"]["state"], "unavailable-on-this-platform")
        run.assert_not_called()

    @patch.object(server.platform, "system", return_value="Darwin")
    @patch.object(server.platform, "mac_ver", return_value=("15.0", ("", "", ""), ""))
    @patch.object(server.os, "getuid", return_value=501)
    @patch.object(server.subprocess, "run", side_effect=subprocess.TimeoutExpired("launchctl", 3))
    def test_launchctl_timeout_is_reported_without_failing_endpoint(self, _run, _uid, _mac, _system):
        result = server.local_diagnostics()
        self.assertEqual(result["agent"]["state"], "query-failed")
        self.assertEqual(result["updater"]["state"], "query-failed")


if __name__ == "__main__":
    unittest.main()
