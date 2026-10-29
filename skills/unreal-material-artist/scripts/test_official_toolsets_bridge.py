import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "unreal-engine-mcp" / "scripts"))
from test_builtin_mcp import server
from unreal_material_tools import official_toolsets_bridge as cli


class DirectMcpTests(unittest.TestCase):
    def run_call(self, url, root):
        report = Path(root) / "report.json"
        args = cli.build_parser().parse_args([
            "asset:exists", "--mcp-url", url, "--root", root,
            "--out", str(report), "--timeout", "5",
        ])
        result = cli.command(args)
        return result, json.loads(report.read_text(encoding="utf-8"))

    def test_default_call_uses_direct_mcp(self):
        with tempfile.TemporaryDirectory() as root, server(native=True) as (client, calls):
            code, report = self.run_call(client.url, root)
            self.assertEqual(code, 0)
            self.assertEqual(report["transport"], "epic-mcp-http")
            self.assertTrue(report["output"]["found"])
            self.assertEqual(report["resolved_toolset_name"], "editor_toolset.toolsets.asset.AssetTools")

    def test_official_failure_reports_failure_without_fallback(self):
        with tempfile.TemporaryDirectory() as root, server(native=True, tool_error=True) as (client, calls):
            code, report = self.run_call(client.url, root)
            self.assertEqual(code, 1)
            self.assertFalse(report["success"])
            self.assertIn("asset unavailable", report["error"])
            self.assertEqual(len([c for c in calls if c["method"] == "tools/call"]), 1)


if __name__ == "__main__":
    unittest.main()
