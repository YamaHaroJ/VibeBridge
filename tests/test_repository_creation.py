import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class RepositoryCreationTests(unittest.TestCase):
    @patch.object(server.subprocess, "run")
    def test_new_repository_is_seeded_with_readme_and_project_memory(self, run):
        def completed(stdout="", stderr="", returncode=0):
            return type("Completed", (), {
                "stdout": stdout, "stderr": stderr, "returncode": returncode
            })()

        run.side_effect = [
            completed(stdout="https://github.com/Example/NewProject\n"),
            completed(stdout='{"content": "ignored"}'),
            completed(stdout='{"content": "ignored"}'),
        ]

        result = server.create_github_repo("NewProject", "Demo project", private=True)

        self.assertEqual(result["nameWithOwner"], "Example/NewProject")
        self.assertTrue(result["private"])
        self.assertTrue(result["initialized"])
        self.assertEqual(run.call_count, 3)

        readme_call = run.call_args_list[1].args[0]
        memory_call = run.call_args_list[2].args[0]
        self.assertIn("repos/Example/NewProject/contents/README.md", readme_call)
        self.assertIn("repos/Example/NewProject/contents/VIBEBRIDGE_CONTEXT.md", memory_call)

        readme_encoded = readme_call[-1].split("=", 1)[1]
        memory_encoded = memory_call[-1].split("=", 1)[1]
        self.assertIn("# NewProject", base64.b64decode(readme_encoded).decode())
        self.assertIn("## Current state", base64.b64decode(memory_encoded).decode())

    @patch.object(server.subprocess, "run")
    def test_invalid_repository_name_is_rejected_before_github_call(self, run):
        with self.assertRaisesRegex(ValueError, "Repository name"):
            server.create_github_repo("../unsafe", private=True)
        run.assert_not_called()

    @patch.object(server.subprocess, "run")
    def test_failed_seed_reports_that_repository_already_exists(self, run):
        run.side_effect = [
            type("Completed", (), {"stdout": "https://github.com/Example/Partial\n", "stderr": "", "returncode": 0})(),
            type("Completed", (), {"stdout": "", "stderr": "HTTP 403: Resource not accessible", "returncode": 1})(),
        ]
        with self.assertRaisesRegex(RuntimeError, "Repository Example/Partial was created, but initializing README.md failed"):
            server.create_github_repo("Partial", private=True)


if __name__ == "__main__":
    unittest.main()
