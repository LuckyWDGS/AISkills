"""Each UE skill bundle talks to its own engine line only; no Unreal editor required."""

import unittest

from ue_mcp import BUNDLE_ENGINE, McpError, check_bundle_engine


class BundleEngineTests(unittest.TestCase):
    def test_bundle_declares_its_engine(self):
        self.assertEqual(BUNDLE_ENGINE, "5.9")

    def test_matching_or_unidentified_engine_is_accepted(self):
        for owner in ({"engine_version": "5.9.0"}, {"engine_version": "5.9.4"}, {}, {"known": False}):
            with self.subTest(owner=owner):
                check_bundle_engine(owner)

    def test_other_engine_line_is_refused_with_the_bundle_to_link(self):
        with self.assertRaisesRegex(McpError, r"UE 5.8\.1.*-UEVersion 5.8"):
            check_bundle_engine({"engine_version": "5.8.1", "uproject": "X/Test.uproject"})
        with self.assertRaisesRegex(McpError, "No request was sent|no request was sent"):
            check_bundle_engine({"engine_version": "5.10.0"})


class FakeClient:
    def __init__(self, toolsets, version=""):
        self.toolsets, self.version, self.closed = toolsets, version, False

    def list_toolsets(self):
        return [{"name": f"owner.{name}"} for name in self.toolsets]

    def editor_owner(self):
        return {"engine_version": self.version} if self.version else {"known": False}


class UnportedHelperTests(unittest.TestCase):
    def test_58_contract_helper_is_refused_on_a_59_editor_before_any_call(self):
        from ue_mcp.skill_api import refuse_unported
        for client in (FakeClient(["NiagaraToolset_System", "PythonScriptingTools"]),
                       FakeClient(["NiagaraToolset_System"], version="5.9.0")):
            with self.subTest(toolsets=client.toolsets), self.assertRaisesRegex(McpError, "not ported to UE 5.9"):
                refuse_unported(client, "niagara_audit")

    def test_58_inventory_without_an_identified_engine_is_left_to_the_offline_fixtures(self):
        from ue_mcp.skill_api import refuse_unported
        refuse_unported(FakeClient(["MaterialTools", "ProgrammaticToolset"]))

    def test_legacy_shims_declare_the_58_contract(self):
        from pathlib import Path
        bundle = Path(__file__).resolve().parents[2]
        for shim in ("unreal-material-artist/scripts/unreal_material_tools/mcp.py",
                     "niagara-vfx-artist/scripts/vfx_delivery/mcp.py"):
            with self.subTest(shim=shim):
                self.assertIn('LEGACY_CONTRACT = "5.8"', (bundle / shim).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
