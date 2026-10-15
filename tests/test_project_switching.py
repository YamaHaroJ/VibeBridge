import base64
import unittest
from unittest.mock import patch

import server


class ProjectSwitchTests(unittest.TestCase):
    @patch.object(server, "discover_projects", return_value=[])
    @patch.object(server, "github_projects")
    def test_explicit_autofill_alias_overrides_active_vibebridge(self, github_projects, _local):
        github_projects.return_value = [
            {"name": "Autofill-Insurance-Extension", "nameWithOwner": "YamaHaroJ/Autofill-Insurance-Extension", "localPath": None},
            {"name": "VibeBridge", "nameWithOwner": "YamaHaroJ/VibeBridge", "localPath": "/Users/test/VibeBridge"},
        ]
        project, reason = server.match_project("switch to Autofill", "/Users/test/VibeBridge")
        self.assertEqual(reason, "message")
        self.assertEqual(project["repository"], "YamaHaroJ/Autofill-Insurance-Extension")

    @patch.object(server, "discover_projects", return_value=[])
    @patch.object(server, "github_projects")
    def test_explicit_vibebridge_mention_overrides_active_autofill(self, github_projects, _local):
        github_projects.return_value = [
            {"name": "Autofill-Insurance-Extension", "nameWithOwner": "YamaHaroJ/Autofill-Insurance-Extension", "localPath": None},
            {"name": "VibeBridge", "nameWithOwner": "YamaHaroJ/VibeBridge", "localPath": "/Users/test/VibeBridge"},
        ]
        project, reason = server.match_project("switch to VibeBridge", "github:YamaHaroJ/Autofill-Insurance-Extension")
        self.assertEqual(reason, "message")
        self.assertEqual(project["path"], "/Users/test/VibeBridge")

    @patch.object(server.subprocess, "run")
    def test_remote_context_has_real_line_breaks_and_project_memory(self, run):
        readme = base64.b64encode(b"# Autofill\nRemote repository README").decode()
        memory = base64.b64encode(b"# Project Memory\nAutofill-only instructions").decode()
        run.side_effect = [
            type("Completed", (), {"returncode": 0, "stdout": readme + "\n", "stderr": ""})(),
            type("Completed", (), {"returncode": 0, "stdout": memory + "\n", "stderr": ""})(),
        ]
        context = server.remote_repo_context("YamaHaroJ/Autofill")
        self.assertIn("\n\nREADME (README.md):", context)
        self.assertIn("PERSISTENT PROJECT MEMORY (VIBEBRIDGE_CONTEXT.md):", context)
        self.assertNotIn("\\n\\nREADME", context)

    @patch.object(server.subprocess, "run")
    def test_remote_context_reports_total_failure(self, run):
        run.return_value = type("Completed", (), {"returncode": 1, "stdout": "", "stderr": "HTTP 401: authentication failed"})()
        with self.assertRaisesRegex(RuntimeError, "Could not load useful context"):
            server.remote_repo_context("YamaHaroJ/PrivateRepo")


if __name__ == "__main__":
    unittest.main()
