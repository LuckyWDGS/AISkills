"""Files that stand-alone skills must each ship, but that have to stay identical."""

from pathlib import Path
import unittest


SKILLS = Path(__file__).resolve().parents[2]
PAIRS = [
    ("niagara-vfx-artist/scripts/vfx_delivery/core.py", "vfx-flipbook-generator/scripts/vfx_delivery/core.py"),
    ("niagara-vfx-artist/scripts/vfx_delivery/mcp.py", "unreal-material-artist/scripts/unreal_material_tools/mcp.py"),
    ("niagara-vfx-artist/scripts/vfx_delivery/bridge.py", "unreal-material-artist/scripts/unreal_material_tools/bridge.py"),
]


class SharedCopyTests(unittest.TestCase):
    def test_copies_have_not_drifted(self):
        for left, right in PAIRS:
            with self.subTest(left=left):
                self.assertEqual((SKILLS / left).read_bytes(), (SKILLS / right).read_bytes(),
                                 f"{left} and {right} differ; change both or move the code into one owner")


if __name__ == "__main__":
    unittest.main()
