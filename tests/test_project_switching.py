import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class ProjectSwitchTests(unittest.TestCase):
    def test_get_rejects_non_extension_browser_origin(self):
        handler = object.__new__(server.Handler)
        handler.headers = {"Origin": "https://attacker.example"}
        with patch.object(handler, "send_json") as send:
            self.assertFalse(handler.require_extension_origin())
        send.assert_called_once_with(403, {"error": "Untrusted browser origin"})

    def test_get_rejects_unrelated_extension_origin(self):
        handler = object.__new__(server.Handler)
        handler.headers = {"Origin": "chrome-extension://abcdefghijklmnop"}
        with patch.object(server, "expected_extension_origin", return_value="chrome-extension://ponmlkjihgfedcba"), patch.object(handler, "send_json") as send:
            self.assertFalse(handler.require_extension_origin())
        send.assert_called_once_with(403, {"error": "Untrusted browser origin"})

    def test_get_allows_pinned_extension_origin(self):
        handler = object.__new__(server.Handler)
        handler.headers = {"Origin": "chrome-extension://ponmlkjihgfedcba"}
        with patch.object(server, "expected_extension_origin", return_value="chrome-extension://ponmlkjihgfedcba"), patch.object(handler, "send_json") as send:
            self.assertTrue(handler.require_extension_origin())
        send.assert_not_called()

    def test_get_allows_non_browser_local_client_without_origin(self):
        handler = object.__new__(server.Handler)
        handler.headers = {}
        with patch.object(handler, "send_json") as send:
            self.assertTrue(handler.require_extension_origin())
        send.assert_not_called()

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
    def test_remote_context_survives_optional_checkpoint_timeout(self, run):
        readme = base64.b64encode(b"# VibeBridge").decode()
        memory = base64.b64encode(b"# Project Memory").decode()
        run.side_effect = [
            type("Completed", (), {"returncode": 0, "stdout": readme, "stderr": ""})(),
            type("Completed", (), {"returncode": 0, "stdout": memory, "stderr": ""})(),
            server.subprocess.TimeoutExpired(cmd="gh api", timeout=4),
        ]
        context = server.remote_repo_context("YamaHaroJ/VibeBridge")
        self.assertIn("# VibeBridge", context)
        self.assertIn("# Project Memory", context)
        self.assertNotIn("ROLLING CONVERSATION CHECKPOINTS", context)

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
    @patch.object(server, "github_projects", return_value=[])
    def test_resolve_project_set_includes_active_project_for_short_followup(self, _github, _local):
        projects = server.resolve_project_set(
            "keep building",
            [],
            "github:YamaHaroJ/VibeBridge",
        )
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["repository"], "YamaHaroJ/VibeBridge")

    @patch.object(server, "discover_projects", return_value=[])
    @patch.object(server, "github_projects", return_value=[
        {"name": "VibeBridge", "nameWithOwner": "YamaHaroJ/VibeBridge", "localPath": None},
        {"name": "Autofill-Insurance-Extension", "nameWithOwner": "YamaHaroJ/Autofill-Insurance-Extension", "localPath": None},
    ])
    def test_explicit_switch_does_not_keep_old_active_project(self, _github, _local):
        projects = server.resolve_project_set(
            "switch to Autofill Insurance Extension",
            [],
            "github:YamaHaroJ/VibeBridge",
        )
        self.assertEqual(
            {project["repository"] for project in projects},
            {"YamaHaroJ/Autofill-Insurance-Extension"},
        )

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


    @patch.object(server, "github_projects", side_effect=RuntimeError("repository listing unavailable"))
    @patch.object(server, "remote_repo_context", return_value="PROJECT: VibeBridge\\nREMOTE MEMORY")
    def test_selected_remote_context_does_not_require_repository_listing(self, remote_context, _github):
        context = server.project_context("github:YamaHaroJ/VibeBridge")
        self.assertEqual(context, "PROJECT: VibeBridge\\nREMOTE MEMORY")
        remote_context.assert_called_once_with("YamaHaroJ/VibeBridge")

    @patch.object(server, "ROOTS", [Path("/Users/test/Projects"), Path("/Users/test/Developer"), Path("/Users/test/VibeBridge")])
    @patch.object(server, "local_repo_map", return_value={"yamaharoj/vibebridge": "/Users/test/VibeBridge"})
    @patch.object(server, "discover_projects", return_value=[{"name": "VibeBridge", "path": "/Users/test/VibeBridge"}])
    def test_terminal_project_path_resolves_selected_github_slug_to_local_checkout(self, _projects, _local_map):
        with patch.object(Path, "is_dir", return_value=True):
            path = server.project_path("github:YamaHaroJ/VibeBridge")
        self.assertEqual(str(path), "/Users/test/VibeBridge")

    @patch.object(server, "local_repo_map", return_value={})
    def test_terminal_project_path_rejects_uncloned_github_repo(self, _local_map):
        with self.assertRaisesRegex(ValueError, "not cloned locally"):
            server.project_path("github:YamaHaroJ/RemoteOnly")

    @patch.object(server.subprocess, "run", side_effect=server.subprocess.TimeoutExpired(cmd="git", timeout=5))
    def test_safe_git_metadata_timeout_returns_empty_value(self, _run):
        self.assertEqual(server.safe_git_output(["git", "status", "--short"], Path("/tmp")), "")

    def test_multiple_project_contexts_use_real_line_breaks(self):
        context = server.format_project_context_sections([
            ("VibeBridge", "first project memory"),
            ("Autofill", "second project memory"),
        ])
        self.assertIn("===== PROJECT CONTEXT: VibeBridge =====\nfirst project memory", context)
        self.assertNotIn("===== PROJECT CONTEXT: VibeBridge =====\\\\n", context)
        self.assertIn("\n\n===== PROJECT CONTEXT: Autofill =====\nsecond project memory", context)

    def test_remote_project_context_rejects_invalid_slug(self):
        with self.assertRaisesRegex(ValueError, "Invalid GitHub repository path"):
            server.project_context("github:../VibeBridge")



if __name__ == "__main__":
    unittest.main()
