import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
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
        memory = base64.b64encode(b"# Project Memory\nAutofill-only instructions\n\n## Most recent discussion\nResume the latest implementation task.").decode()
        run.side_effect = [
            type("Completed", (), {"returncode": 0, "stdout": readme + "\n", "stderr": ""})(),
            type("Completed", (), {"returncode": 0, "stdout": memory + "\n", "stderr": ""})(),
            type("Completed", (), {"returncode": 1, "stdout": "", "stderr": "404 Not Found"})(),
        ]
        context = server.remote_repo_context("YamaHaroJ/Autofill")
        self.assertIn("\n\nREADME (README.md):", context)
        self.assertIn("PERSISTENT PROJECT MEMORY (VIBEBRIDGE_CONTEXT.md):", context)
        self.assertIn("## Most recent discussion\nResume the latest implementation task.", context)
        self.assertNotIn("\\n\\nREADME", context)

    @patch.object(server.subprocess, "run")
    def test_remote_context_reports_total_failure(self, run):
        run.return_value = type("Completed", (), {"returncode": 1, "stdout": "", "stderr": "HTTP 401: authentication failed"})()
        with self.assertRaisesRegex(RuntimeError, "Could not load useful context"):
            server.remote_repo_context("YamaHaroJ/PrivateRepo")
 
    @patch.object(server, "discover_projects", return_value=[{"name": "VibeBridge", "path": "/Users/test/VibeBridge"}])
    @patch.object(server, "github_projects")
    def test_explicit_full_slug_wins_over_same_named_local_project(self, github_projects, _local):
        github_projects.return_value = [
            {"name": "VibeBridge", "nameWithOwner": "someone/VibeBridge", "localPath": None},
            {"name": "Autofill", "nameWithOwner": "YamaHaroJ/Autofill-Insurance-Extension", "localPath": None},
        ]
        project, reason = server.match_project(
            "Switch to YamaHaroJ/Autofill-Insurance-Extension",
            "/Users/test/VibeBridge",
        )
        self.assertEqual(reason, "message")
        self.assertEqual(project["repository"], "YamaHaroJ/Autofill-Insurance-Extension")

    @patch.object(server, "discover_projects", return_value=[{"name": "VibeBridge", "path": "/Users/test/VibeBridge"}])
    @patch.object(server, "github_projects", side_effect=RuntimeError("GitHub CLI is not authenticated"))
    def test_failed_explicit_switch_never_falls_back_to_active_project(self, _github, _local):
        with self.assertRaisesRegex(RuntimeError, "Could not search GitHub"):
            server.match_project("Switch to Autofill", "/Users/test/VibeBridge")

    @patch.object(server, "discover_projects", return_value=[])
    @patch.object(server, "github_projects", return_value=[])
    def test_unknown_explicit_switch_is_reported_as_error(self, _github, _local):
        with self.assertRaisesRegex(RuntimeError, "requested project could not be resolved"):
            server.match_project("Switch to TotallyMissingProject", "github:YamaHaroJ/VibeBridge")


    @patch.object(server, "discover_projects", return_value=[])
    @patch.object(server, "github_projects")
    def test_resolve_project_set_keeps_multiple_explicit_projects(self, github_projects, _local):
        github_projects.return_value = [
            {"name": "Autofill-Insurance-Extension", "nameWithOwner": "YamaHaroJ/Autofill-Insurance-Extension", "localPath": None},
            {"name": "VibeBridge", "nameWithOwner": "YamaHaroJ/VibeBridge", "localPath": None},
            {"name": "MacOptimizer", "nameWithOwner": "YamaHaroJ/MacOptimizer", "localPath": None},
        ]
        projects = server.resolve_project_set("Update VibeBridge and Autofill Insurance Extension")
        self.assertEqual(
            {project["repository"] for project in projects},
            {"YamaHaroJ/VibeBridge", "YamaHaroJ/Autofill-Insurance-Extension"},
        )

    @patch.object(server, "discover_projects", return_value=[])
    @patch.object(server, "github_projects", side_effect=RuntimeError("temporary GitHub listing failure"))
    def test_resolve_project_set_preserves_known_remote_project_when_listing_fails(self, _github, _local):
        projects = server.resolve_project_set(
            "keep building",
            [{"path": "github:YamaHaroJ/VibeBridge"}],
            "github:YamaHaroJ/VibeBridge",
        )
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["repository"], "YamaHaroJ/VibeBridge")
        self.assertEqual(projects[0]["path"], "github:YamaHaroJ/VibeBridge")

    @patch.object(server, "discover_projects", return_value=[])
    @patch.object(server, "github_projects")
    def test_resolve_project_set_preserves_known_project_and_adds_new_one(self, github_projects, _local):
        github_projects.return_value = [
            {"name": "Autofill-Insurance-Extension", "nameWithOwner": "YamaHaroJ/Autofill-Insurance-Extension", "localPath": None},
            {"name": "VibeBridge", "nameWithOwner": "YamaHaroJ/VibeBridge", "localPath": None},
        ]
        projects = server.resolve_project_set(
            "Now update Autofill Insurance Extension too",
            [{"path": "github:YamaHaroJ/VibeBridge"}],
        )
        self.assertEqual(
            {project["repository"] for project in projects},
            {"YamaHaroJ/VibeBridge", "YamaHaroJ/Autofill-Insurance-Extension"},
        )



if __name__ == "__main__":
    unittest.main()
