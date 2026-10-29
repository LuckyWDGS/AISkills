"""Retired-tool registry: BridgeClient refuses unported live steps early, and the registries stay accurate."""

import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from ue_mcp import legacy_bridge


SKILLS = Path(__file__).resolve().parents[2]
PACKAGES = {
    "unreal-material-artist": SKILLS / "unreal-material-artist" / "scripts" / "unreal_material_tools",
    "niagara-vfx-artist": SKILLS / "niagara-vfx-artist" / "scripts" / "vfx_delivery",
}


def construct(skill_root):
    return legacy_bridge.BridgeClient(skill_root, project="P")


class RefusalTests(unittest.TestCase):
    def skill(self, folder, registry):
        (Path(folder) / "scripts").mkdir()
        (Path(folder) / "scripts" / "retired_tools.json").write_text(json.dumps(registry), encoding="utf-8")
        return Path(folder)

    def test_registered_caller_is_refused_before_any_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.skill(folder, {"test_retired_tools": {"instead": "material_audit.py", "offline": "list"}})
            with patch.object(legacy_bridge, "_load_python_remote", side_effect=AssertionError("network")):
                with self.assertRaisesRegex(legacy_bridge.RetiredTool,
                                            r"test_retired_tools's live editor step .* Instead: material_audit.py\. Still works offline: list\."):
                    construct(root)

    def test_unregistered_caller_proceeds(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.skill(folder, {"other_tool": {"instead": "x"}})
            with patch.object(legacy_bridge, "_load_python_remote", return_value=object()):
                self.assertEqual(construct(root).project, "P")

    def test_bridge_errors_print_one_line(self):
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            legacy_bridge._print_bridge_errors(legacy_bridge.RetiredTool, legacy_bridge.RetiredTool("x is not ported"), None)
        self.assertEqual(stderr.getvalue(), "error: x is not ported\n")


class RegistryConsistencyTests(unittest.TestCase):
    def test_registry_matches_modules_still_on_retired_apis(self):
        for skill, package in PACKAGES.items():
            with self.subTest(skill=skill):
                registry = json.loads((SKILLS / skill / "scripts" / "retired_tools.json").read_text(encoding="utf-8"))
                listed = {name for name in registry if not name.startswith("_")}
                retired = set()
                for module in package.glob("*.py"):
                    text = module.read_text(encoding="utf-8")
                    if "BridgeClient(" in text and re.search(r"UnrealBridge\w*Library", text):
                        retired.add(module.stem)
                self.assertEqual(listed, retired,
                                 "Ported tools must leave retired_tools.json; tools still on UnrealBridge APIs must be listed")
                for name, entry in registry.items():
                    if not name.startswith("_"):
                        self.assertTrue(entry.get("instead"), f"{name} needs an 'instead' route")


if __name__ == "__main__":
    unittest.main()
