"""Large Unicode tool payloads must travel through stdin without argv limits."""

import io
import json
import subprocess
import threading
import time
import unittest
from unittest.mock import patch

from test_builtin_mcp import server
from ue_mcp.client import UnrealMcpClient
from ue_mcp.protocol import McpError


class FakeProcess:
    def __init__(self, stdout=b"", *, stderr=b"", running=False):
        self.stdout = io.BytesIO(stdout)
        self.stderr = stderr
        self.running = running
        self.terminated = self.killed = False
        self.communicate_calls = 0

    def poll(self):
        return None if self.running else 0

    def terminate(self):
        self.terminated = True
        self.running = False

    def kill(self):
        self.killed = True
        self.running = False

    def communicate(self, timeout=None):
        self.communicate_calls += 1
        return b"", self.stderr


class CurlPayloadTests(unittest.TestCase):
    def client(self, timeout=5):
        return UnrealMcpClient("http://127.0.0.1:8000/mcp", "2025-11-25", timeout)

    def payload(self):
        return {"jsonrpc": "2.0", "id": 41, "method": "tools/call", "params": {
            "name": "PythonScriptingTools.execute_python", "arguments": {"script": {
                "language": "Python", "content": '中文分类|调试🎬𠮷 "quoted"\\\n' * 10000}}}}

    def test_large_unicode_payload_reaches_real_json_and_sse_servers_unchanged(self):
        payload = self.payload()
        self.assertGreater(len(json.dumps(payload)), 32767)
        for sse in (False, True):
            with self.subTest(sse=sse), server(sse=sse) as (client, calls):
                result = client.call_tool(payload["params"]["name"], payload["params"]["arguments"])
                self.assertIn("content", result)
                dispatched = [c for c in calls if c["method"] == "tools/call"]
                self.assertEqual(len(dispatched), 1)
                self.assertEqual(dispatched[0]["params"], payload["params"])

    def test_binary_stdin_keeps_argv_short_and_preserves_session_headers(self):
        payload = self.payload()
        client = self.client()
        client.session_id = "session-41"
        captured = {}
        response = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"id":41,"result":{}}\n'
        process = FakeProcess(response)

        def fake_popen(command, **kwargs):
            captured.update(command=command, source=kwargs["stdin"], body=kwargs["stdin"].read())
            self.assertIsNot(kwargs["stdin"], subprocess.PIPE)
            return process

        with patch("ue_mcp.client.shutil.which", return_value="curl"), \
                patch("ue_mcp.client.subprocess.Popen", side_effect=fake_popen) as start:
            self.assertEqual(client._streaming_request(payload), {"id": 41, "result": {}})
        self.assertEqual(start.call_count, 1)
        self.assertLess(len(subprocess.list2cmdline(captured["command"])), 2048)
        self.assertEqual(captured["command"][captured["command"].index("--data-binary") + 1], "@-")
        self.assertIn("Mcp-Session-Id: session-41", captured["command"])
        self.assertIn("Mcp-Protocol-Version: 2025-11-25", captured["command"])
        self.assertEqual(json.loads(captured["body"].decode("utf-8")), payload)
        self.assertIn("🎬".encode("utf-8"), captured["body"])
        self.assertTrue(captured["source"].closed)

    def test_process_start_error_closes_stdin_without_retry(self):
        captured = {}

        def fail_start(command, **kwargs):
            captured["source"] = kwargs["stdin"]
            raise OSError("cannot launch curl")

        with patch("ue_mcp.client.shutil.which", return_value="curl"), \
                patch("ue_mcp.client.subprocess.Popen", side_effect=fail_start) as start:
            with self.assertRaisesRegex(OSError, "cannot launch curl"):
                self.client()._streaming_request(self.payload())
        self.assertEqual(start.call_count, 1)
        self.assertTrue(captured["source"].closed)

    def test_stdin_preparation_error_never_starts_a_request(self):
        class FailingInput(io.BytesIO):
            def write(self, value):
                raise OSError("request input storage unavailable")

        source = FailingInput()
        with patch("ue_mcp.client.shutil.which", return_value="curl"), \
                patch("ue_mcp.client.tempfile.TemporaryFile", return_value=source), \
                patch("ue_mcp.client.subprocess.Popen") as start:
            with self.assertRaisesRegex(OSError, "input storage unavailable"):
                self.client()._streaming_request(self.payload())
        start.assert_not_called()
        self.assertTrue(source.closed)

    def test_curl_stderr_failure_is_reported_once(self):
        process = FakeProcess(stderr=b"Failed to connect to endpoint")
        with patch("ue_mcp.client.shutil.which", return_value="curl"), \
                patch("ue_mcp.client.subprocess.Popen", return_value=process) as start, \
                patch("ue_mcp.client.connection_hint", return_value="connection hint"):
            with self.assertRaisesRegex(McpError, "curl failed.*Failed to connect.*connection hint"):
                self.client()._streaming_request(self.payload())
        self.assertEqual(start.call_count, 1)
        self.assertEqual(process.communicate_calls, 1)

    def test_silent_timeout_terminates_then_kills_without_resending(self):
        released = threading.Event()

        class BlockingOutput:
            def readline(self):
                released.wait(1)
                return b""

        class SlowProcess(FakeProcess):
            def terminate(self):
                super().terminate()
                released.set()

            def communicate(self, timeout=None):
                self.communicate_calls += 1
                if self.communicate_calls == 1:
                    raise subprocess.TimeoutExpired("curl", timeout)
                return b"", b""

        process = SlowProcess(running=True)
        process.stdout = BlockingOutput()
        with patch("ue_mcp.client.shutil.which", return_value="curl"), \
                patch("ue_mcp.client.subprocess.Popen", return_value=process) as start:
            begin = time.monotonic()
            with self.assertRaisesRegex(McpError, "Timed out waiting for the final SSE event"):
                self.client(timeout=0.02)._streaming_request(self.payload())
            self.assertLess(time.monotonic() - begin, 1)
        self.assertTrue(process.terminated)
        self.assertTrue(process.killed)
        self.assertEqual(process.communicate_calls, 2)
        self.assertEqual(start.call_count, 1)


if __name__ == "__main__":
    unittest.main()
