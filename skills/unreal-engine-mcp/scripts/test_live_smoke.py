"""Smoke-runner routing and target isolation; never connects to Unreal."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import live_smoke


class SmokeRoutingTests(unittest.TestCase):
    def smoke(self, folder=".", **args):
        smoke = live_smoke.Smoke.__new__(live_smoke.Smoke)
        smoke.args = SimpleNamespace(**{**live_smoke.DEFAULTS, "project": r"E:\Game\MCPSI.uproject",
                                       "probe_remote": False, "full": False, "write": False, **args})
        smoke.work = Path(folder)
        smoke.client = SimpleNamespace(pie_running=lambda: False, close=Mock())
        smoke.results = []
        return smoke

    def planned_checks(self, **args):
        smoke = self.smoke(**args)
        names, sources = [], []
        smoke.material = lambda source: sources.append(source)

        def check(name, assets, body):
            names.append(name)
            if name.startswith("material_audit"):
                body()

        smoke.check = check
        self.assertEqual(smoke.run(), 0)
        return names, sources

    def test_default_run_uses_mcp_graph_without_remote_discovery(self):
        names, sources = self.planned_checks()
        self.assertEqual(sources, ["mcp"])
        self.assertFalse(any("python_remote" in name for name in names))

    def test_remote_discovery_is_an_explicit_diagnostic(self):
        names, sources = self.planned_checks(probe_remote=True)
        self.assertEqual(sources, ["mcp"])
        self.assertTrue(any("python_remote" in name for name in names))

    def test_child_processes_inherit_the_selected_project_guard(self):
        smoke = self.smoke()
        completed = SimpleNamespace(returncode=0, stdout="ok", stderr="")
        with patch("live_smoke.subprocess.run", return_value=completed) as run:
            self.assertEqual(smoke.tool("builtin_mcp", "status"), (0, "ok"))
        self.assertEqual(run.call_args.kwargs["env"]["UE_MCP_PROJECT"], smoke.args.project)

    def test_material_domain_read_uses_the_mcp_route(self):
        with tempfile.TemporaryDirectory() as folder:
            smoke = self.smoke(folder)
            report = {"domain_contract": {"domain": "Surface", "blend_mode": "Opaque", "shading_models": ["DefaultLit"]}}
            (Path(folder) / "domain.json").write_text(json.dumps(report), encoding="utf-8")
            with patch("live_smoke.run_tool", return_value=(0, "")) as run:
                self.assertIn("Surface", smoke.domain())
            argv = run.call_args.args
            self.assertEqual(argv[argv.index("--graph-source") + 1], "mcp")
            self.assertEqual(run.call_args.kwargs["project"], smoke.args.project)

    def binding_check(self, verdict, texture_link, renderer_link):
        with tempfile.TemporaryDirectory() as folder:
            smoke = self.smoke(folder)
            report = {"texture_asset_exists": True, "material_exists": True, "renderer_exists": True,
                      "verification_passed": verdict, "material_references_target_texture": texture_link,
                      "renderer_references_material": renderer_link}
            (Path(folder) / "live-verify.json").write_text(json.dumps(report), encoding="utf-8")
            with patch.object(smoke, "tool", return_value=(0, "")):
                smoke.check("live_asset_verify", [], smoke.live_verify)
            return smoke.results[0]

    def test_existing_but_unbound_assets_are_not_a_binding_pass(self):
        row = self.binding_check(False, False, False)
        self.assertEqual(row["status"], "collected")

    def test_complete_binding_chain_can_pass(self):
        self.assertEqual(self.binding_check(True, True, True)["status"], "pass")

    def test_binding_verdict_requires_consistent_link_evidence(self):
        self.assertEqual(self.binding_check(True, False, True)["status"], "fail")

    def test_missing_verdict_is_not_a_pass(self):
        self.assertEqual(self.binding_check(None, True, True)["status"], "fail")

    def test_report_evidence_survives_workspace_exit_without_reusing_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "nested" / "smoke.json"
            with live_smoke.evidence_workspace(report) as first:
                (first / "evidence.json").write_text('{"measured": true}', encoding="utf-8")
            with live_smoke.evidence_workspace(report) as second:
                self.assertNotEqual(first, second)
            self.assertTrue((first / "evidence.json").is_file())

    def test_unrequested_temporary_evidence_is_cleaned(self):
        with live_smoke.evidence_workspace(None) as work:
            self.assertTrue(work.is_dir())
        self.assertFalse(work.exists())

    def test_cli_retains_partial_evidence_and_closes_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "smoke.json"
            client = SimpleNamespace(close=Mock())
            smoke = SimpleNamespace(client=client, results=[{"check": "started", "status": "collected"}])
            smoke.run = Mock(side_effect=RuntimeError("interrupted"))
            with patch("live_smoke.Smoke", return_value=smoke), patch("sys.argv", ["live_smoke.py", "--out", str(report)]):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    live_smoke.main()
            result = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(Path(result["artifact_directory"]).is_dir())
            self.assertEqual(result["results"], smoke.results)
            client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
