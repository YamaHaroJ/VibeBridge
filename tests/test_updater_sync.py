import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from agent import updater
from agent.updater import deploy_current_checkout, sync_extension_tree


class ExtensionTreeSyncTests(unittest.TestCase):

    def test_dirty_managed_runtime_changes_are_never_overwritten(self):
        source = Path(updater.__file__).read_text(encoding="utf-8")
        self.assertIn('if managed_status and not force_managed:', source)
        self.assertIn('if managed_status and force_managed:', source)
        self.assertIn('Update deferred because managed runtime paths have local edits.', source)
        self.assertIn('preserving all files', source)
    def test_stale_revision_marker_cannot_hide_extension_version_mismatch(self):
        source = Path(updater.__file__).read_text(encoding="utf-8")
        self.assertIn("if synced == target and previous == target:", source)
        self.assertIn('target_manifest_text = run(["git", "show", target + ":extension/manifest.json"])', source)
        self.assertIn('files_match = local_manifest.get("version") == target_manifest.get("version")', source)
        self.assertIn("Deployment marker matched GitHub but extension manifest did not; repairing deployment.", source)


    @patch("agent.updater.shutil.which", return_value=None)
    @patch("agent.updater.run")
    def test_validation_runs_full_regression_suite_before_deployment(self, run, _node):
        updater.validate()
        first_command = run.call_args_list[0].args[0]
        first_timeout = run.call_args_list[0].kwargs["timeout"]
        self.assertEqual(first_command[1:5], ["-m", "unittest", "discover", "-s"])
        self.assertIn("tests", first_command)
        self.assertEqual(first_timeout, 120)


    def test_failed_agent_restart_does_not_mark_revision_deployed(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "last-synced-revision"
            marker.write_text("previous\n")
            with patch("agent.updater.SYNC_MARKER", marker), \
                 patch("agent.updater.validate") as validate, \
                 patch("agent.updater.launch_agent", side_effect=RuntimeError("launchctl failed")):
                with self.assertRaisesRegex(RuntimeError, "launchctl failed"):
                    deploy_current_checkout("target-revision")
            validate.assert_called_once_with()
            self.assertEqual(marker.read_text(), "previous\n")

    def test_successful_deployment_marks_revision_after_agent_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "last-synced-revision"
            with patch("agent.updater.SYNC_MARKER", marker), \
                 patch("agent.updater.validate") as validate, \
                 patch("agent.updater.launch_agent") as launch:
                deploy_current_checkout("target-revision")
            validate.assert_called_once_with()
            launch.assert_called_once_with()
            self.assertEqual(marker.read_text(), "target-revision\n")

    def test_sync_preserves_registered_root_and_publishes_new_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "staged-extension"
            destination = base / "installed-extension"
            source.mkdir()
            destination.mkdir()

            (source / "manifest.json").write_text(json.dumps({
                "manifest_version": 3,
                "name": "VibeBridge",
                "version": "0.2.23",
                "background": {"service_worker": "background.js"},
            }))
            (source / "background.js").write_text("self.version = 'new';")
            (destination / "manifest.json").write_text(json.dumps({
                "manifest_version": 3,
                "name": "VibeBridge",
                "version": "0.2.22",
            }))
            (destination / "background.js").write_text("self.version = 'old';")
            (destination / "stale.js").write_text("obsolete")

            root_before = destination.resolve()
            sync_extension_tree(source, destination)

            self.assertTrue(destination.is_dir())
            self.assertEqual(destination.resolve(), root_before)
            self.assertEqual(json.loads((destination / "manifest.json").read_text())["version"], "0.2.23")
            self.assertEqual((destination / "background.js").read_text(), "self.version = 'new';")
            self.assertFalse((destination / "stale.js").exists())
            self.assertFalse(list(destination.rglob("*.vibebridge-tmp")))

    def test_missing_manifest_fails_without_deleting_existing_extension(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "staged-extension"
            destination = base / "installed-extension"
            source.mkdir()
            destination.mkdir()
            existing_manifest = destination / "manifest.json"
            existing_manifest.write_text('{"manifest_version":3,"name":"VibeBridge"}')
            (source / "background.js").write_text("new")

            with self.assertRaisesRegex(RuntimeError, "missing manifest"):
                sync_extension_tree(source, destination)

            self.assertTrue(existing_manifest.is_file())
            self.assertEqual(json.loads(existing_manifest.read_text())["name"], "VibeBridge")


if __name__ == "__main__":
    unittest.main()
