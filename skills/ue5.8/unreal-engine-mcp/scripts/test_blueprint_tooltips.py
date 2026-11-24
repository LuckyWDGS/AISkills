"""blueprint_tooltips reporting and the MCPBlueprintMetadata plugin installer's file sync (offline)."""

import tempfile
import unittest
from pathlib import Path

import blueprint_tooltips as tooltips
import install_blueprint_metadata_plugin as installer


class TooltipReportTests(unittest.TestCase):
    def test_missing_plugin_is_reported(self):
        result = tooltips.report("/Game/BP_T", {"plugin": False})
        self.assertFalse(result["plugin"])
        self.assertIn("install_blueprint_metadata_plugin", result["message"])

    def test_members_without_tooltips_are_listed(self):
        state = {"plugin": True, "failed": [], "locals": {},
                 "functions": {"Fire": {"tooltip": "开火", "category": "武器"}, "Reload": {"tooltip": "", "category": ""}},
                 "variables": {"Ammo": "弹药数", "bDebugLog": ""}}
        result = tooltips.report("/Game/BP_T", state)
        self.assertEqual(result["missing"], {"functions": ["Reload"], "variables": ["bDebugLog"]})

    def test_script_reads_without_writing_by_default(self):
        self.assertIn("__WRITE__", tooltips.SCRIPT)
        self.assertIn("set_function_tooltip", tooltips.SCRIPT)


class InstallerTests(unittest.TestCase):
    def test_plugin_source_is_complete(self):
        files = {p.relative_to(installer.SOURCE).as_posix() for p in installer.SOURCE.rglob("*") if p.is_file()}
        self.assertIn("MCPBlueprintMetadata.uplugin", files)
        self.assertIn("Source/MCPBlueprintMetadata/MCPBlueprintMetadata.Build.cs", files)
        self.assertIn("Source/MCPBlueprintMetadata/Private/MCPBlueprintMetadataLibrary.cpp", files)

    def test_sync_copies_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Plugins" / installer.PLUGIN
            first = installer.sync(installer.SOURCE, target)
            self.assertIn("MCPBlueprintMetadata.uplugin", first)
            self.assertEqual(installer.sync(installer.SOURCE, target), [])


if __name__ == "__main__":
    unittest.main()
