"""Protocol regressions for the Epic MCP client; no Unreal editor required."""

import contextlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest

from builtin_mcp import McpError, UnrealMcpClient, _decode_text_value


@contextlib.contextmanager
def server(*, native=False, sse=False, tool_error=False):
    calls = []
    schema = {"name": "exists", "inputSchema": {"type": "object"}}
    qualified = "editor_toolset.toolsets.asset.AssetTools"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_DELETE(self):
            self.send_response(204)
            self.end_headers()

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(data)
            method = data["method"]
            if method == "notifications/initialized":
                self.send_response(202)
                self.end_headers()
                return
            params = data.get("params", {})
            if method == "initialize":
                result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}}
            elif method == "tools/list":
                if native:
                    if params.get("cursor"):
                        result = {"tools": [{**schema, "name": qualified + ".exists"}]}
                    else:
                        result = {"tools": [], "nextCursor": "page2"}
                else:
                    result = {"tools": [{"name": n} for n in ("list_toolsets", "describe_toolset", "call_tool")]}
            elif method == "tools/call":
                name = params["name"]
                if name == "list_toolsets":
                    value = "- " + qualified + "\n"  # Description may be absent.
                elif name == "describe_toolset":
                    value = json.dumps({"tools": [schema]})
                else:
                    value = json.dumps({"found": True, "label": "材质"}, ensure_ascii=False)
                result = {"content": [{"type": "text", "text": value}]}
                if tool_error and name not in {"list_toolsets", "describe_toolset"}:
                    result = {"isError": True, "content": [{"type": "text", "text": "asset unavailable"}]}
            else:
                raise AssertionError(method)
            response = {"jsonrpc": "2.0", "id": data["id"], "result": result}
            body = json.dumps(response, ensure_ascii=False).encode("utf-8")
            streaming = sse and method == "tools/call"
            if streaming:
                # Include a notification before the matching response event.
                body = b'data: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n' + b"data: " + body + b"\n\n"
            self.send_response(200)
            self.send_header("Mcp-Session-Id", "test-session")
            self.send_header("Content-Type", "text/event-stream" if streaming else "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    client = UnrealMcpClient(f"http://127.0.0.1:{httpd.server_port}/mcp", "2025-11-25", 5)
    try:
        yield client, calls
    finally:
        client.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


class ClientTests(unittest.TestCase):
    def test_search_discovery_and_json_call(self):
        with server() as (client, calls):
            result = client.call_resolved_tool("AssetTools", "exists", {"asset_path": "/Game/Test"})
            self.assertEqual(_decode_text_value(result)["label"], "材质")
            dispatched = [c["params"] for c in calls if c["method"] == "tools/call"][-1]
            self.assertEqual(dispatched["name"], "call_tool")
            self.assertEqual(dispatched["arguments"]["arguments"], {"asset_path": "/Game/Test"})

    def test_native_discovery_pagination_and_sse(self):
        with server(native=True, sse=True) as (client, calls):
            result = client.call_resolved_tool("AssetTools", "exists", {})
            self.assertTrue(_decode_text_value(result)["found"])
            dispatched = [c["params"] for c in calls if c["method"] == "tools/call"]
            self.assertEqual(len(dispatched), 1)
            self.assertEqual(dispatched[0]["name"], "editor_toolset.toolsets.asset.AssetTools.exists")
            self.assertEqual(len([c for c in calls if c["method"] == "tools/list"]), 2)

    def test_tool_error_is_failure_without_retry(self):
        with server(native=True, tool_error=True) as (client, calls):
            with self.assertRaisesRegex(McpError, "asset unavailable"):
                client.call_resolved_tool("AssetTools", "exists", {})
            self.assertEqual(len([c for c in calls if c["method"] == "tools/call"]), 1)

    def test_missing_tool_is_rejected_before_dispatch(self):
        with server(native=True) as (client, calls):
            with self.assertRaisesRegex(McpError, "not found in live schema"):
                client.call_resolved_tool("AssetTools", "invented_write", {})
            self.assertFalse(any(c["method"] == "tools/call" for c in calls))


if __name__ == "__main__":
    unittest.main()
