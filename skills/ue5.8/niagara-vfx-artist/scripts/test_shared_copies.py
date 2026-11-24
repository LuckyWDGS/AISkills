"""Files that stand-alone skills must each ship, but that have to stay identical."""

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


SKILLS = Path(__file__).resolve().parents[2]
PAIRS = [
    ("niagara-vfx-artist/scripts/vfx_delivery/core.py", "vfx-flipbook-generator/scripts/vfx_flipbook/core.py"),
    ("niagara-vfx-artist/scripts/vfx_delivery/mcp.py", "unreal-material-artist/scripts/unreal_material_tools/mcp.py"),
]


class SharedCopyTests(unittest.TestCase):
    def test_copies_have_not_drifted(self):
        for left, right in PAIRS:
            with self.subTest(left=left):
                self.assertEqual((SKILLS / left).read_bytes(), (SKILLS / right).read_bytes(),
                                 f"{left} and {right} differ; change both or move the code into one owner")


class MissingSiblingTests(unittest.TestCase):
    """A skill installed without its sibling stops with a message naming the missing skill."""

    def load_alone(self, source: str):
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder, "lonely-skill", "scripts", "pkg", Path(source).name)
            copy.parent.mkdir(parents=True)
            shutil.copy(SKILLS / source, copy)
            spec = importlib.util.spec_from_file_location("lonely_skill_module", copy)
            spec.loader.exec_module(importlib.util.module_from_spec(spec))

    def test_mcp_shim_names_unreal_engine_mcp(self):
        with self.assertRaisesRegex(ModuleNotFoundError, "lonely-skill needs the sibling skill unreal-engine-mcp"):
            self.load_alone("niagara-vfx-artist/scripts/vfx_delivery/mcp.py")

    def test_flipbook_reexport_names_the_generator(self):
        with self.assertRaisesRegex(ModuleNotFoundError, "sibling skill vfx-flipbook-generator"):
            self.load_alone("niagara-vfx-artist/scripts/vfx_delivery/flipbook_builder.py")


if __name__ == "__main__":
    unittest.main()
