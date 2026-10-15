import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class AiSummaryTests(unittest.TestCase):
    @patch.object(server, "load_checkpoint_api_key", return_value="sk-test-key")
    @patch("urllib.request.urlopen")
    def test_merges_previous_summary_with_new_message(self, urlopen, _key):
        response = type("Response", (), {
            "__enter__": lambda self: self,
            "__exit__": lambda self, *args: None,
            "read": lambda self: json.dumps({
                "output": [{
                    "content": [{"type": "output_text", "text": "Updated summary: task is checkpointing."}]
                }]
            }).encode()
        })()
        urlopen.return_value = response
        summary = server.ai_merge_checkpoint(
            "Previous: implement checkpoints",
            "user",
            "Make the summary AI-written",
            "conversation-1"
        )
        self.assertIn("Updated summary", summary)
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode())
        prompt = payload["input"][1]["content"]
        self.assertIn("Previous: implement checkpoints", prompt)
        self.assertIn("Make the summary AI-written", prompt)

    @patch.object(server, "load_checkpoint_api_key", return_value="")
    def test_requires_api_key_instead_of_falling_back_to_raw_logs(self, _key):
        with self.assertRaisesRegex(RuntimeError, "OpenAI API key"):
            server.ai_merge_checkpoint("", "user", "new message", "chat")


if __name__ == "__main__":
    unittest.main()
