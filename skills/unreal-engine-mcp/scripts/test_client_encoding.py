"""Tool calls with Chinese arguments must reach UE intact (curl argv is re-encoded on Windows)."""

import json
import unittest
from unittest.mock import patch

from ue_mcp.client import UnrealMcpClient


class CurlPayloadTests(unittest.TestCase):
    def test_tools_call_payload_is_ascii_json(self):
        client = UnrealMcpClient("http://127.0.0.1:8000/mcp", "2025-11-25", 5)
        captured = {}

        def fake_popen(command, **kwargs):
            captured["data"] = command[command.index("--data-binary") + 1]
            raise RuntimeError("stop after capturing the command")

        payload = {"method": "tools/call", "params": {"arguments": {"category": "抛物线投掷|调试"}}}
        with patch("ue_mcp.client.shutil.which", return_value="curl"), \
                patch("ue_mcp.client.subprocess.Popen", side_effect=fake_popen):
            with self.assertRaises(RuntimeError):
                client._streaming_request(payload)
        self.assertTrue(captured["data"].isascii(), captured["data"])
        self.assertEqual(json.loads(captured["data"])["params"]["arguments"]["category"], "抛物线投掷|调试")


if __name__ == "__main__":
    unittest.main()
