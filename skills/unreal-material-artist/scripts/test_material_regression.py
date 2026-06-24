from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_regression
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def preview_payload(material_path: str, shaded_path: str) -> dict[str, object]:
    return {
        "tool": "material_preview",
        "mode": "render",
        "material_path": material_path,
        "options": {"carrier": "sprite", "lighting": "hdri"},
        "outputs": {"shaded_png": shaded_path, "shaded_ok": True, "complexity_png": "", "complexity_ok": False},
    }


class MaterialRegressionTests(unittest.TestCase):
    def test_explicit_preview_report_overrides_package_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_preview = write_json(root, "preview-old.json", preview_payload("/Game/Materials/M_Old", str(root / "old.png")))
            new_preview = write_json(root, "preview-new.json", preview_payload("/Game/Materials/M_New", str(root / "new.png")))
            package = write_json(
                root,
                "package.json",
                {
                    "tool": "delivery_packager",
                    "effect": "WingEcho",
                    "layer": "RibbonTrail",
                    "summaries": {"reports": {"preview": [{"path": str(old_preview)}]}},
                },
            )

            args = material_regression.argparse.Namespace(
                package=str(package),
                preview_report=str(new_preview),
                effect="WingEcho",
                layer="RibbonTrail",
            )

            effect, layer, preview = material_regression.resolve_preview_source(args)

            self.assertEqual(effect, "WingEcho")
            self.assertEqual(layer, "RibbonTrail")
            self.assertEqual(preview["report_path"], str(new_preview))
            self.assertEqual(preview["material_path"], "/Game/Materials/M_New")


if __name__ == "__main__":
    unittest.main(verbosity=2)
