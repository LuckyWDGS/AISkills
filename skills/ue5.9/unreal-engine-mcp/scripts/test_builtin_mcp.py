"""Protocol regressions for the Epic MCP client; no Unreal editor required."""

import contextlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from unittest.mock import patch
from ue_mcp.protocol import _parse_toolsets

from builtin_mcp import (
    McpError, SessionExpired, UnrealMcpClient, _decode_text_value, brief_tools, check_expected_project,
    endpoint_owner, load_batch, render_brief, run_batch,
)


@contextlib.contextmanager
def server(*, native=False, modern=False, describe_error=False, sse=False, tool_error=False, sessions=None,
           schema_override=None):
    """``sessions``: a set of live session ids; when given, unknown ids get HTTP 404 like UE."""
    calls = []
    schema = schema_override if schema_override is not None else {
        "name": "exists", "inputSchema": {"type": "object", "properties": {"asset_path": {"type": "string"}}}}
    qualified = "editor_toolset.toolsets.asset.AssetTools"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_DELETE(self):
            calls.append({"method": "DELETE"})
            self.send_response(204)
            self.end_headers()

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            method = data["method"]
            session = self.headers.get("Mcp-Session-Id")
            if sessions is not None and method != "initialize" and session not in sessions:
                calls.append({**data, "rejected": True})
                body = b'{"jsonrpc":"2.0","id":1,"error":{"code":-32600,"message":"Unknown session id"}}'
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            calls.append(data)
            if method == "notifications/initialized":
                self.send_response(202)
                self.end_headers()
                return
            params = data.get("params", {})
            if method == "initialize":
                result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}}
                if sessions is not None:
                    sessions.add("test-session")
            elif method == "tools/list":
                if native:
                    if params.get("cursor"):
                        result = {"tools": [{**schema, "name": qualified + ".exists"}]}
                    else:
                        result = {"tools": [], "nextCursor": "page2"}
                elif modern:
                    result = {"tools": [{"name": n} for n in (
                        "list_toolsets", "describe_toolsets", "describe_tools", "call_tool")]}
                else:
                    result = {"tools": [{"name": n} for n in ("list_toolsets", "describe_toolset", "call_tool")]}
            elif method == "tools/call":
                name = params["name"]
                if name == "list_toolsets":
                    value = "- " + qualified + "\n"  # Description may be absent.
                elif name == "describe_toolset":
                    value = json.dumps({"tools": [schema]})
                elif name == "describe_toolsets":
                    assert params["arguments"] == {"toolset_names": [qualified], "include_schemas": True}
                    value = json.dumps({"toolsets": {qualified: {"tools": {"exists": schema}}}})
                elif name == "describe_tools":
                    assert params["arguments"]["tool_names"] == [qualified + ".exists"]
                    value = json.dumps({"errors": {qualified + ".exists": "fixture unavailable"}} if describe_error
                                       else {"tools": {qualified + ".exists": schema}})
                else:
                    value = json.dumps({"found": True, "label": "材质"}, ensure_ascii=False)
                result = {"content": [{"type": "text", "text": value}]}
                if tool_error and name not in {"list_toolsets", "describe_toolset", "describe_toolsets", "describe_tools"}:
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
    def test_description_bullets_do_not_become_fake_toolsets(self):
        rows = _parse_toolsets('- Editor.Toolset: description\n- Graph: ""\n- Node: Name\n- Other.Tools\n')
        self.assertEqual([row['name'] for row in rows], ['Editor.Toolset', 'Other.Tools'])
        self.assertIn('- Graph:', rows[0]['description'])

    def test_modern_per_tool_discovery_and_validated_dispatch(self):
        with server(modern=True) as (client, calls):
            result = client.call_resolved_tool("AssetTools", "exists", {"asset_path": "/Game/Test"})
            self.assertTrue(_decode_text_value(result)["found"])
            names = [c["params"]["name"] for c in calls if c["method"] == "tools/call"]
            self.assertEqual(names, ["list_toolsets", "describe_tools", "call_tool"])
            with self.assertRaisesRegex(McpError, "unknown argument"):
                client.call_resolved_tool("AssetTools", "exists", {"asset_pat": "/Game/Test"})
            self.assertEqual(sum(c["method"] == "tools/call" and c["params"]["name"] == "call_tool" for c in calls), 1)

    def test_modern_full_toolset_envelope(self):
        with server(modern=True) as (client, calls):
            value = client.describe_toolset("AssetTools")
            self.assertIn("exists", value["tools"])
            self.assertNotIn("toolsets", value)

    def test_modern_partial_discovery_failure_never_dispatches(self):
        with server(modern=True, describe_error=True) as (client, calls):
            with self.assertRaisesRegex(McpError, "fixture unavailable"):
                client.call_resolved_tool("AssetTools", "exists", {})
            self.assertFalse(any(c["method"] == "tools/call" and c["params"]["name"] == "call_tool" for c in calls))

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
            with self.assertRaisesRegex(McpError, "'invented_write' is not in AssetTools"):
                client.call_resolved_tool("AssetTools", "invented_write", {})
            self.assertFalse(any(c["method"] == "tools/call" for c in calls))


class SchemaCacheTests(unittest.TestCase):
    OWNER = {"known": True, "pid": 42, "process_started": "time-1", "executable": "UE/UnrealEditor.exe",
             "uproject": "X/Test.uproject", "engine_version": "5.9.0"}

    def setUp(self):
        lookup = patch("ue_mcp.client.endpoint_owner", return_value=self.OWNER.copy())
        self.owner_lookup = lookup.start()
        self.addCleanup(lookup.stop)

    def test_changed_editor_refetches_changed_schema_with_identical_inventory(self):
        for change in ({"process_started": "time-2"}, {"uproject": "Y/Test.uproject"},
                       {"engine_version": "5.9.1"}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as cache:
                self.owner_lookup.return_value = self.OWNER.copy()
                schema = {"name": "exists", "inputSchema": {"type": "object", "properties": {
                    "asset_path": {"type": "string"}}}}
                with server(modern=True, schema_override=schema) as (base, calls):
                    first = UnrealMcpClient(base.url, "2025-11-25", 5, cache_dir=Path(cache))
                    first.find_tool("AssetTools", "exists")
                    schema["inputSchema"] = {"type": "object", "properties": {"path": {"type": "string"}},
                                             "required": ["path"]}
                    self.owner_lookup.return_value = {**self.OWNER, **change}
                    second = UnrealMcpClient(base.url, "2025-11-25", 5, cache_dir=Path(cache))
                    second.call_resolved_tool("AssetTools", "exists", {"path": "/Game/Test"})
                    self.assertEqual(sum(c["method"] == "tools/call" and c["params"]["name"] == "describe_tools"
                                         for c in calls), 2)

    def test_unknown_instance_never_reuses_disk_schema(self):
        self.owner_lookup.return_value = {"known": False}
        with tempfile.TemporaryDirectory() as cache, server() as (base, calls):
            for _ in range(2):
                client = UnrealMcpClient(base.url, "2025-11-25", 5, cache_dir=Path(cache))
                client.describe_toolset("AssetTools")
            self.assertEqual(len(self.describes(calls)), 2)
            self.assertEqual(list(Path(cache).iterdir()), [])

    def test_server_instance_allows_reuse_but_new_instance_or_build_refetches(self):
        self.owner_lookup.return_value = {"known": False}
        with tempfile.TemporaryDirectory() as cache, server() as (base, calls):
            for instance_id, version in (("a", "5.9-1"), ("a", "5.9-1"), ("b", "5.9-1"), ("b", "5.9-2")):
                client = UnrealMcpClient(base.url, "2025-11-25", 5, cache_dir=Path(cache))
                client.initialize()
                client.initialize_result.update({"serverInfo": {"version": version}, "_meta": {
                    "com.epicgames.unrealengine/instance": {"instanceId": instance_id}}})
                client.describe_toolset("AssetTools")
                client.close()
            self.assertEqual(len(self.describes(calls)), 3)

    def test_modern_descriptor_cache_and_no_retry_after_write_failure(self):
        with tempfile.TemporaryDirectory() as cache, server(modern=True, tool_error=True) as (base, calls):
            first = UnrealMcpClient(base.url, "2025-11-25", 5, cache_dir=Path(cache))
            first.find_tool("AssetTools", "exists")
            cached = UnrealMcpClient(base.url, "2025-11-25", 5, cache_dir=Path(cache))
            with self.assertRaisesRegex(McpError, "asset unavailable"):
                cached.call_resolved_tool("AssetTools", "exists", {})
            self.assertEqual(sum(c["method"] == "tools/call" and c["params"]["name"] == "describe_tools" for c in calls), 1)
            self.assertEqual(sum(c["method"] == "tools/call" and c["params"]["name"] == "call_tool" for c in calls), 1)
            self.assertFalse(cached._cache_file("editor_toolset.toolsets.asset.AssetTools.exists").exists())

    def describes(self, calls):
        return [c for c in calls if c["method"] == "tools/call" and c["params"]["name"] == "describe_toolset"]

    def test_second_client_reads_schema_from_cache(self):
        with tempfile.TemporaryDirectory() as cache, server() as (client, calls):
            for _ in range(2):
                fresh = UnrealMcpClient(client.url, "2025-11-25", 5, cache_dir=Path(cache))
                fresh.call_resolved_tool("AssetTools", "exists", {})
                fresh.close()
            self.assertEqual(len(self.describes(calls)), 1)
            self.assertEqual(fresh._schema_source["editor_toolset.toolsets.asset.AssetTools"], "cache")

    def test_refresh_ignores_cache_and_stale_inventories_are_pruned(self):
        with tempfile.TemporaryDirectory() as cache, server() as (client, calls):
            first = UnrealMcpClient(client.url, "2025-11-25", 5, cache_dir=Path(cache))
            first.describe_toolset("AssetTools")
            stale = Path(cache) / f"{first._url_key()}-0000000000000000"
            stale.mkdir()
            refreshed = UnrealMcpClient(client.url, "2025-11-25", 5, cache_dir=Path(cache), refresh_schema=True)
            refreshed.describe_toolset("AssetTools")
            self.assertEqual(len(self.describes(calls)), 2)
            self.assertFalse(stale.exists())

    def test_tool_error_on_cached_schema_invalidates_it_without_retry(self):
        with tempfile.TemporaryDirectory() as cache, server(tool_error=True) as (client, calls):
            UnrealMcpClient(client.url, "2025-11-25", 5, cache_dir=Path(cache)).describe_toolset("AssetTools")
            cached = UnrealMcpClient(client.url, "2025-11-25", 5, cache_dir=Path(cache))
            with self.assertRaisesRegex(McpError, "asset unavailable"):
                cached.call_resolved_tool("AssetTools", "exists", {})
            self.assertFalse(cached._cache_file("editor_toolset.toolsets.asset.AssetTools").exists())
            dispatched = [c for c in calls if c["method"] == "tools/call" and c["params"]["name"] == "call_tool"]
            self.assertEqual(len(dispatched), 1)

    def test_no_cache_dir_means_no_files(self):
        with server() as (client, calls):
            client.describe_toolset("AssetTools")
            self.assertIsNone(client._cache_file("editor_toolset.toolsets.asset.AssetTools"))


class SessionReuseTests(unittest.TestCase):
    OWNER = {"known": True, "pid": 42, "process_started": "2026-11-04T01:00:00Z",
             "executable": "X/UnrealEditor.exe", "project": "MCPSI", "uproject": "X/MCPSI.uproject"}

    def setUp(self):
        lookup = patch("ue_mcp.client.endpoint_owner", return_value=self.OWNER.copy())
        self.owner_lookup = lookup.start()
        self.addCleanup(lookup.stop)

    def count(self, calls, method, rejected=False):
        return len([c for c in calls if c["method"] == method and bool(c.get("rejected")) == rejected])

    def client(self, url, folder, **extra):
        return UnrealMcpClient(url, "2025-11-25", 5, session_dir=Path(folder), **extra)

    def test_second_run_resumes_without_initialize_or_discovery(self):
        live = set()
        with tempfile.TemporaryDirectory() as folder, server(sessions=live) as (base, calls):
            first = self.client(base.url, folder).open()
            first.call_resolved_tool("AssetTools", "exists", {})
            first.close()
            self.assertFalse(any(c["method"] == "DELETE" for c in calls))
            second = self.client(base.url, folder).open()
            self.assertTrue(second.session_reused)
            second.call_resolved_tool("AssetTools", "exists", {})
            self.assertEqual(self.count(calls, "initialize"), 1)
            self.assertEqual(self.count(calls, "tools/list"), 1)

    def test_rejected_session_reinitializes_and_resends_once(self):
        live = set()
        with tempfile.TemporaryDirectory() as folder, server(sessions=live) as (base, calls):
            first = self.client(base.url, folder).open()
            first.call_resolved_tool("AssetTools", "exists", {})
            first.close()
            live.clear()  # The server forgot the saved token, without an OS process change.
            resumed = self.client(base.url, folder).open()
            result = resumed.call_resolved_tool("AssetTools", "exists", {})
            self.assertTrue(_decode_text_value(result)["found"])
            self.assertFalse(resumed.session_reused)
            self.assertEqual(self.count(calls, "initialize"), 2)
            executed = [c for c in calls if c["method"] == "tools/call" and not c.get("rejected")
                        and c["params"]["name"] == "call_tool"]
            self.assertEqual(len(executed), 2)  # One per run; the rejected attempt never executed.

    def test_fresh_session_rejection_is_not_retried(self):
        live = set()
        with server(sessions=live) as (base, calls):
            base.initialize()
            live.clear()
            with self.assertRaises(SessionExpired):
                base.call("tools/list")

    def test_stale_saved_owner_is_revalidated_before_refusing(self):
        live = set()
        with tempfile.TemporaryDirectory() as folder, server(sessions=live) as (base, calls):
            first = self.client(base.url, folder).open()
            first._owner = {"known": True, "project": "OldProject", "uproject": "X/OldProject.uproject"}
            first.close()
            with patch("ue_mcp.client.endpoint_owner", return_value={"known": True, "project": "MCPSI", "uproject": "X/MCPSI.uproject"}):
                resumed = self.client(base.url, folder, expected_project="MCPSI").open()
            self.assertEqual(resumed.editor_owner()["project"], "MCPSI")
            self.assertEqual(self.count(calls, "initialize"), 2)

    def test_matching_saved_project_cannot_hide_a_different_current_project(self):
        with tempfile.TemporaryDirectory() as folder, server() as (base, calls):
            first = self.client(base.url, folder, expected_project="MCPSI").open()
            first.close()
            before = len(calls)
            self.owner_lookup.return_value = {**self.OWNER, "pid": 43, "project": "Other",
                                              "uproject": "X/Other.uproject"}
            with self.assertRaisesRegex(McpError, "not 'MCPSI'"):
                self.client(base.url, folder, expected_project="MCPSI").open()
            self.assertEqual(len(calls), before)  # Refuse before sending even initialize.

    def test_unknown_current_owner_cannot_use_saved_identity(self):
        with tempfile.TemporaryDirectory() as folder, server() as (base, calls):
            first = self.client(base.url, folder, expected_project="MCPSI").open()
            first.close()
            before = len(calls)
            self.owner_lookup.return_value = {"known": False, "reason": "lookup unavailable"}
            with self.assertRaisesRegex(McpError, "Cannot confirm"):
                self.client(base.url, folder, expected_project="MCPSI").open()
            self.assertEqual(len(calls), before)

    def test_process_change_discards_session_and_inventory_even_if_token_is_accepted(self):
        for changed in ({"pid": 43}, {"process_started": "2026-11-04T02:00:00Z"},
                        {"uproject": "Y/MCPSI.uproject"}, {"known": False}):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder, server() as (base, calls):
                self.owner_lookup.return_value = self.OWNER.copy()
                first = self.client(base.url, folder).open()
                first.list_toolsets()
                first.close()
                self.owner_lookup.return_value = {**self.OWNER, **changed}
                resumed = self.client(base.url, folder).open()
                self.assertFalse(resumed.session_reused)
                self.assertIsNone(resumed._toolsets)
                resumed.list_toolsets()
                self.assertEqual(resumed.editor_owner(), self.owner_lookup.return_value)
                self.assertEqual(self.count(calls, "initialize"), 2)
                self.assertEqual(self.count(calls, "tools/list"), 2)

    def test_refresh_schema_also_refreshes_a_resumed_inventory(self):
        with tempfile.TemporaryDirectory() as folder, server() as (base, calls):
            first = self.client(base.url, folder).open()
            first.list_toolsets()
            first._toolsets = [{"name": "StaleTools"}]
            first.close()
            refreshed = self.client(base.url, folder, refresh_schema=True).open()
            self.assertTrue(refreshed.session_reused)
            self.assertEqual(refreshed.list_toolsets()[0]["name"], "editor_toolset.toolsets.asset.AssetTools")
            self.assertEqual(self.count(calls, "initialize"), 1)
            self.assertEqual(self.count(calls, "tools/list"), 2)

    def test_expired_session_rechecks_owner_before_resending(self):
        live = set()
        with tempfile.TemporaryDirectory() as folder, server(sessions=live) as (base, calls):
            first = self.client(base.url, folder, expected_project="MCPSI").open()
            first.call_resolved_tool("AssetTools", "exists", {})
            first.close()
            resumed = self.client(base.url, folder, expected_project="MCPSI").open()
            live.clear()
            self.owner_lookup.return_value = {**self.OWNER, "project": "Other", "uproject": "X/Other.uproject"}
            with self.assertRaisesRegex(McpError, "not 'MCPSI'"):
                resumed.call_resolved_tool("AssetTools", "exists", {})
            executed = [c for c in calls if c["method"] == "tools/call" and not c.get("rejected")
                        and c["params"]["name"] == "call_tool"]
            self.assertEqual(len(executed), 1)
            self.assertEqual(self.count(calls, "initialize"), 1)


class FakeBatchClient:
    def __init__(self, fail=(), pie=False, dirty_after=()):
        self.fail, self.sent, self.pie = set(fail), [], pie
        self.dirty, self.dirty_after = set(), set(dirty_after)

    def pie_running(self):
        return self.pie

    def package_dirty(self, package):
        return package in self.dirty

    def missing_tool_message(self, toolset, tool):
        return f"Tool {tool!r} is not in {toolset}"

    def find_tool(self, toolset, tool):
        if tool == "missing":
            return None
        return {"name": tool, "inputSchema": {"required": ["path"] if tool == "needs_path" else []}}

    def call_resolved_tool(self, toolset, tool, arguments):
        self.sent.append(tool)
        if tool in self.fail:
            raise McpError(f"{tool} failed")
        self.dirty |= self.dirty_after  # a write that also touches other packages
        return {"content": [{"type": "text", "text": json.dumps({"returnValue": {"tool": tool, "value": 1}})}]}


class BatchTests(unittest.TestCase):
    def entries(self, *rows):
        return [{"toolset": "T", "_line": index + 1, **row} for index, row in enumerate(rows)]

    def test_validation_blocks_everything(self):
        client = FakeBatchClient()
        report = run_batch(client, self.entries({"tool": "missing"}, {"tool": "needs_path", "args": {}}, {"tool": "ok"}))
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["problems"]), 2)
        self.assertEqual(client.sent, [])

    def test_stops_at_first_failure_and_skips_rest(self):
        client = FakeBatchClient(fail={"write"})
        report = run_batch(client, self.entries({"tool": "a"}, {"tool": "write"}, {"tool": "b"}))
        self.assertEqual([row["status"] for row in report["results"]], ["ok", "error", "skipped"])
        self.assertEqual(client.sent, ["a", "write"])

    def test_readback_expectation_and_continue(self):
        client = FakeBatchClient()
        rows = self.entries(
            {"tool": "set", "readback": {"toolset": "T", "tool": "get"}, "expect": {"value": 2}},
            {"tool": "set2", "readback": {"toolset": "T", "tool": "get"}, "expect": {"value": 1}},
        )
        report = run_batch(client, rows, continue_on_error=True)
        self.assertEqual([row["status"] for row in report["results"]], ["mismatch", "ok"])
        self.assertEqual(report["counts"], {"mismatch": 1, "ok": 1})

    def test_expectation_tolerates_float32_but_not_type_changes(self):
        from builtin_mcp import _expectation_met
        self.assertTrue(_expectation_met(0.4, 0.4000000059604645))
        self.assertTrue(_expectation_met({"x": [1, 2.5]}, {"x": [1, 2.5000001], "y": 0}))
        self.assertFalse(_expectation_met(0.4, 0.5))
        self.assertFalse(_expectation_met(True, 1))
        self.assertFalse(_expectation_met([1], [1, 2]))

    def test_json_string_results_and_ref_forms(self):
        from builtin_mcp import _expectation_met, unwrap_result
        wrapped = {"content": [{"type": "text", "text": json.dumps({"returnValue": '{"parent":{"refPath":"/Game/M.M"}}'})}]}
        self.assertEqual(unwrap_result(wrapped), {"parent": {"refPath": "/Game/M.M"}})
        self.assertTrue(_expectation_met({"parent": {"refPath": "/Game/M.M"}}, {"parent": "/Game/M.M"}))
        self.assertFalse(_expectation_met({"refPath": "/Game/A.A"}, "/Game/B.B"))

    def test_pie_refuses_execution_but_not_validation(self):
        client = FakeBatchClient(pie=True)
        report = run_batch(client, self.entries({"tool": "a"}))
        self.assertEqual((report["ok"], report["refused"]), (False, "pie"))
        self.assertEqual(client.sent, [])
        self.assertTrue(run_batch(client, self.entries({"tool": "a"}), dry_run=True)["ok"])
        self.assertTrue(run_batch(client, self.entries({"tool": "a"}), allow_pie=True)["ok"])

    def test_side_effects_on_referenced_packages_are_reported(self):
        # The create step names the parent; the edit leaves it unsaved although only the instance is saved.
        client = FakeBatchClient(dirty_after={"/Game/M/M_Parent"})
        report = run_batch(client, self.entries(
            {"tool": "create", "args": {"folder_path": "/Game/S", "asset_name": "MI", "parent": {"refPath": "/Game/M/M_Parent.M_Parent"}}},
            {"tool": "save", "args": {"asset_paths": ["/Game/S/MI"]}}))
        self.assertTrue(report["ok"])
        self.assertEqual(report["left_dirty"], ["/Game/M/M_Parent"])
        self.assertIn("/Game/S/MI", report["checked_packages"])

    def test_packages_dirty_before_are_not_blamed(self):
        client = FakeBatchClient(dirty_after={"/Game/M/M_Parent"})
        client.dirty.add("/Game/M/M_Parent")
        report = run_batch(client, self.entries({"tool": "a", "args": {"m": {"refPath": "/Game/M/M_Parent.M_Parent"}}}))
        self.assertEqual(report["left_dirty"], [])

    def test_failed_package_precheck_refuses_all_writes(self):
        client = FakeBatchClient()
        rows = self.entries({"tool": "write", "args": {"path": "/Game/Test"}})
        with patch.object(client, "package_dirty", side_effect=McpError("Not run: slow task")):
            report = run_batch(client, rows)
        self.assertFalse(report["ok"])
        self.assertEqual(report["refused"], "package_state")
        self.assertEqual(report["unknown_dirty"], ["/Game/Test"])
        self.assertEqual(client.sent, [])

    def test_failed_package_postcheck_keeps_results_and_does_not_replay(self):
        client = FakeBatchClient()
        rows = self.entries({"tool": "write", "args": {"path": "/Game/Test"}})
        with patch.object(client, "package_dirty", side_effect=[False, McpError("Not run: slow task")]) as query:
            report = run_batch(client, rows)
        self.assertFalse(report["ok"])
        self.assertEqual(report["counts"], {"ok": 1})
        self.assertEqual(report["results"][0]["status"], "ok")
        self.assertEqual(report["unknown_dirty"], ["/Game/Test"])
        self.assertIn("slow task", report["package_state_errors"]["after"]["/Game/Test"])
        self.assertEqual(client.sent, ["write"])
        self.assertEqual(query.call_count, 2)

    def test_referenced_packages(self):
        from ue_mcp.batch import referenced_packages
        entries = [{"args": {"expr": {"refPath": "/Game/M/M_X.M_X:MaterialExpressionAdd_3"}, "cls": "/Script/Engine.Material",
                             "name": "Roughness"}, "readback": {"args": {"path": "/Engine/BasicShapes/Cube"}}}]
        self.assertEqual(referenced_packages(entries), ["/Engine/BasicShapes/Cube", "/Game/M/M_X"])

    def test_dry_run_sends_nothing(self):
        client = FakeBatchClient()
        report = run_batch(client, self.entries({"tool": "a"}), dry_run=True)
        self.assertTrue(report["ok"])
        self.assertEqual(client.sent, [])

    def test_load_batch_skips_comments(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "b.jsonl"
            path.write_text('# plan\n\n{"toolset": "T", "tool": "a"}\n', encoding="utf-8")
            self.assertEqual(load_batch(path), [{"toolset": "T", "tool": "a", "_line": 3}])


class HintTests(unittest.TestCase):
    TOOL = {"name": "x.ObjectTools.get_properties", "inputSchema": {
        "type": "object", "required": ["instance", "properties"],
        "properties": {"instance": {"type": "object", "title": "/Script/CoreUObject.Object"},
                       "properties": {"type": "array", "items": {"type": "string"}}}}}

    def test_suggestions(self):
        from ue_mcp.schema import suggest
        self.assertEqual(suggest("IsPieRunning", ["IsPIERunning", "StopPIE"]), "IsPIERunning")
        self.assertEqual(suggest("EditorAppTools", ["EditorAppToolset", "LogsToolset"]), "EditorAppToolset")
        self.assertIsNone(suggest("zzz", ["EditorAppToolset"]))

    def test_argument_problems(self):
        from ue_mcp.schema import argument_problems, signature
        self.assertEqual(argument_problems(self.TOOL, {"instance": {}, "properties": []}), [])
        self.assertEqual(argument_problems(self.TOOL, {"instanse": {}, "properties": []}),
                         ["unknown argument 'instanse' (did you mean 'instance'?)", "missing required argument 'instance'"])
        open_schema = {"inputSchema": {"properties": {"a": {}}, "additionalProperties": True}}
        self.assertEqual(argument_problems(open_schema, {"b": 1}), [])
        self.assertEqual(signature(self.TOOL), "get_properties(instance*: Object, properties*: list[string])")

    def test_client_rejects_bad_arguments_before_dispatch(self):
        with server() as (client, calls):
            with self.assertRaisesRegex(McpError, r"AssetTools.exists: unknown argument 'pth'.*Expected exists\("):
                client.call_resolved_tool("AssetTools", "exists", {"pth": "/Game"})
            self.assertFalse(any(c["params"].get("name") == "call_tool" for c in calls if c["method"] == "tools/call"))
            with self.assertRaisesRegex(McpError, "did you mean 'AssetTools'"):
                client.resolve_toolset("AssetTool")


class BriefAndProjectTests(unittest.TestCase):
    SCHEMA = {"tools": [{
        "name": "editor_toolset.toolsets.material.MaterialTools.get_property_input",
        "description": "\n        Returns the expression feeding an output.\n\n        Args: ...",
        "inputSchema": {"type": "object", "required": ["material"], "properties": {
            "verbose": {"type": "boolean"},
            "material": {"type": "object", "title": "/Script/Engine.Material"},
            "names": {"type": "array", "items": {"type": "string"}},
        }},
        "outputSchema": {"properties": {"returnValue": {"title": "MaterialInputSource", "type": "object"}}},
    }]}

    def test_brief_signature(self):
        rows = brief_tools(self.SCHEMA)
        self.assertEqual([p["name"] for p in rows[0]["params"]], ["material", "verbose", "names"])
        line = render_brief("MaterialTools", rows).splitlines()[1]
        self.assertEqual(line, "  get_property_input(material*: Material, verbose: boolean, names: list[string])"
                               " -> MaterialInputSource  # Returns the expression feeding an output.")

    def test_expected_project(self):
        owner = {"known": True, "project": "MCPSI", "uproject": r"E:\P\MCPSI\MCPSI.uproject"}
        check_expected_project(owner, "mcpsi")
        check_expected_project(owner, r"E:\P\MCPSI\MCPSI.uproject")
        with self.assertRaisesRegex(McpError, "not 'VR53'"):
            check_expected_project(owner, "VR53")
        with self.assertRaisesRegex(McpError, "Cannot confirm"):
            check_expected_project({"known": False, "reason": "no listener"}, "MCPSI")

    def test_full_project_path_distinguishes_same_named_projects(self):
        owner = {"known": True, "project": "MCPSI", "uproject": r"E:\P\MCPSI\MCPSI.uproject"}
        check_expected_project(owner, "e:/p/MCPSI/MCPSI.uproject")
        check_expected_project(owner, "MCPSI.uproject")
        with self.assertRaisesRegex(McpError, "not"):
            check_expected_project(owner, r"E:\Other\MCPSI\MCPSI.uproject")

    def test_remote_endpoint_is_not_probed(self):
        self.assertFalse(endpoint_owner("http://10.0.0.5:8000/mcp")["known"])


class CliReadinessTests(unittest.TestCase):
    def run_command(self, command, error=None):
        from unittest.mock import Mock
        from ue_mcp import cli
        client = Mock(session_id='s', session_reused=False, initialize_result={'protocolVersion': '2025-11-25'})
        client.editor_owner.return_value = {'known': True, 'project': 'Test'}
        if error:
            client.current_level.side_effect = McpError(error)
        else:
            client.current_level.return_value = '/Game/Map'
        with patch.object(cli, '_connect', return_value=client), patch.object(cli, '_emit') as emit, \
                patch('sys.argv', ['builtin_mcp.py', command]):
            code = cli.main()
        client.current_level.assert_called_once_with()
        client.close.assert_called_once_with()
        return code, emit.call_args.args[0]

    def test_initialization_without_state_read_is_not_ready(self):
        for command in ('status', 'ensure'):
            with self.subTest(command=command):
                code, value = self.run_command(command, 'Not run: editor slow task')
                self.assertEqual(code, 1)
                self.assertFalse(value['ready'])
                self.assertIn('slow task', value['editor']['state_read_error'])
                self.assertEqual(value['editor']['current_level'], '')

    def test_ready_requires_successful_editor_read(self):
        code, value = self.run_command('ensure')
        self.assertEqual(code, 0)
        self.assertTrue(value['ready'])
        self.assertEqual(value['editor']['current_level'], '/Game/Map')


class ToolScriptTests(unittest.TestCase):
    def test_legacy_script_is_not_dispatched_or_translated_to_modern_python(self):
        client = UnrealMcpClient("http://127.0.0.1:1/mcp", "2025-11-25", 1)
        client.list_toolsets = lambda: [{"name": "Editor.PythonScriptingTools"}]
        with patch.object(client, "call_resolved_tool") as call:
            with self.assertRaisesRegex(McpError, "No script was sent"):
                client.run_tool_script("def run():\n    return execute_tool('old.write', '{}')")
            call.assert_not_called()

    def test_legacy_contract_remains_available_when_both_executors_are_registered(self):
        client = UnrealMcpClient("http://127.0.0.1:1/mcp", "2025-11-25", 1)
        client.list_toolsets = lambda: [{"name": name} for name in (
            "Editor.ProgrammaticToolset", "Editor.PythonScriptingTools")]
        with patch.object(client, "call_resolved_tool", return_value={"content": []}) as call:
            client.run_tool_script("def run():\n    return {}")
            self.assertEqual(call.call_args.args[:2], ("ProgrammaticToolset", "execute_tool_script"))

    def test_official_python_preserves_top_level_await_and_unicode(self):
        client = UnrealMcpClient("http://127.0.0.1:1/mcp", "2025-11-25", 1)
        script = "await asyncio.sleep(0)\n{'中文': 9}"
        with patch.object(client, 'call_resolved_tool', return_value={
                'content': [{'type': 'text', 'text': json.dumps({'returnValue': '{"中文":9}'})}]}) as call:
            self.assertEqual(client.execute_python(script), {'中文': 9})
        call.assert_called_once_with('PythonScriptingTools', 'execute_python', {
            'script': {'content': script, 'language': 'Python'}})

    def test_modern_level_and_dirty_helpers_use_native_argument_names(self):
        client = UnrealMcpClient("http://127.0.0.1:1/mcp", "2025-11-25", 1)
        client.list_toolsets = lambda: [{'name': 'EditorToolset.LevelToolset'}, {'name': 'EditorToolset.AssetToolset'}]
        with patch.object(client, 'call_resolved_tool', return_value={
                'content': [{'type': 'text', 'text': '{"returnValue":"/Game/Test"}'}]}) as call:
            self.assertEqual(client.current_level(), '/Game/Test')
            call.assert_called_once_with('LevelToolset', 'GetCurrentLevel', {})
        with patch.object(client, 'call_resolved_tool', side_effect=[
                {'content': [{'type': 'text', 'text': '{"returnValue":true}'}]},
                {'content': [{'type': 'text', 'text': '{"returnValue":false}'}]}]) as call:
            self.assertIs(client.package_dirty('/Game/Test'), False)
            self.assertEqual([c.args for c in call.call_args_list], [
                ('AssetToolset', 'Exists', {'path': '/Game/Test'}),
                ('AssetToolset', 'IsDirty', {'assetPath': '/Game/Test'})])

    def test_dirty_helpers_confirm_absence_and_propagate_errors_on_both_versions(self):
        for modern in (False, True):
            with self.subTest(modern=modern):
                client = UnrealMcpClient("http://127.0.0.1:1/mcp", "2025-11-25", 1)
                toolset = 'AssetToolset' if modern else 'AssetTools'
                client.list_toolsets = lambda: [{'name': toolset}]
                with patch.object(client, 'call_resolved_tool', return_value={
                        'content': [{'type': 'text', 'text': '{"returnValue":false}'}]}) as call:
                    self.assertIsNone(client.package_dirty('/Game/Missing'))
                    call.assert_called_once_with(toolset, 'Exists' if modern else 'exists', {'path': '/Game/Missing'})
                with patch.object(client, 'call_resolved_tool', side_effect=McpError('Not run: slow task')):
                    with self.assertRaisesRegex(McpError, 'slow task'):
                        client.package_dirty('/Game/Test')
                with patch.object(client, 'call_resolved_tool', side_effect=[
                        {'content': [{'type': 'text', 'text': '{"returnValue":true}'}]},
                        {'content': [{'type': 'text', 'text': '{"unexpected":false}'}]}]):
                    with self.assertRaisesRegex(McpError, 'non-boolean'):
                        client.package_dirty('/Game/Test')

    def run_with(self, text):
        client = UnrealMcpClient("http://127.0.0.1:1/mcp", "2025-11-25", 1)
        client.list_toolsets = lambda: [{"name": "Editor.ProgrammaticToolset"}]
        sent = []

        def fake(toolset, tool, arguments):
            sent.append((toolset, tool, arguments))
            return {"content": [{"type": "text", "text": text}]}

        client.call_resolved_tool = fake
        return client.run_tool_script("def run():\n    return {}"), sent

    def test_unwraps_return_value_and_inner_json(self):
        value, sent = self.run_with(json.dumps({"returnValue": json.dumps({"n": 3})}))
        self.assertEqual(value, {"n": 3})
        self.assertEqual(sent[0][:2], ("ProgrammaticToolset", "execute_tool_script"))
        self.assertIn("def run()", sent[0][2]["script"])

    def test_plain_dict_passes_through(self):
        value, _ = self.run_with(json.dumps({"a": 1, "b": 2}))
        self.assertEqual(value, {"a": 1, "b": 2})


if __name__ == "__main__":
    unittest.main()
