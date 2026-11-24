"""Every tools/*.py entry point of the UE skills is the shared shim and resolves to a module with main()."""

import importlib.util
from pathlib import Path
import unittest


SKILLS = Path(__file__).resolve().parents[2]
TOOL_SKILLS = ["unreal-material-artist", "niagara-vfx-artist", "vfx-flipbook-generator"]


def load_launcher(skill: str):
    spec = importlib.util.spec_from_file_location(f"_launch_{skill.replace('-', '_')}", SKILLS / skill / "tools" / "_launch.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ToolEntryPointTests(unittest.TestCase):
    def test_shims_share_one_body(self):
        bodies = {}
        for skill in TOOL_SKILLS:
            for shim in (SKILLS / skill / "tools").glob("*.py"):
                if shim.name != "_launch.py":
                    bodies.setdefault(shim.read_bytes().replace(b"\r\n", b"\n"), []).append(f"{skill}/{shim.name}")
        self.assertEqual(len(bodies), 1, f"tool shims differ from the shared body: {sorted(bodies.values(), key=len)[:-1]}")

    def test_every_shim_resolves_to_a_main(self):
        for skill in TOOL_SKILLS:
            launcher = load_launcher(skill)
            shims = [path for path in (SKILLS / skill / "tools").glob("*.py") if path.name != "_launch.py"]
            self.assertTrue(shims, skill)
            for shim in shims:
                with self.subTest(tool=f"{skill}/{shim.name}"):
                    module = launcher.module_name(str(shim))
                    source = launcher.SCRIPTS.joinpath(*module.split(".")).with_suffix(".py")
                    self.assertTrue(source.is_file(), f"{shim.name} -> missing {source}")
                    # Defined there, or re-exported from a sibling skill (niagara flipbook_builder).
                    self.assertRegex(source.read_text(encoding="utf-8"), r"def main\(|import main\b")

    def test_aliases_point_at_existing_shims(self):
        for skill in TOOL_SKILLS:
            launcher = load_launcher(skill)
            for tool in launcher.ALIASES:
                with self.subTest(skill=skill, tool=tool):
                    self.assertTrue((SKILLS / skill / "tools" / f"{tool}.py").is_file())


if __name__ == "__main__":
    unittest.main()
