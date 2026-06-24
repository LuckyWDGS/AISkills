from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_instance_batch


class MaterialInstanceBatchTests(unittest.TestCase):
    def test_build_ue_script_includes_static_switch_tool_candidates(self) -> None:
        spec = {
            "effect": "WingEcho",
            "parent_path": "/Game/Materials/M_WingEcho_Master",
            "instances": [
                {
                    "path": "/Game/Materials/MI_WingEcho_Default",
                    "parent_path": "/Game/Materials/M_WingEcho_Master",
                    "params": [
                        {"name": "UseNoise", "type": "static_switch", "value": True},
                    ],
                }
            ],
        }
        script = material_instance_batch.build_ue_script(spec)
        self.assertIn("set_static_switch_parameter", script)
        self.assertIn("parse_bool", script)
        self.assertIn("set_static_switch_param", script)

    def test_build_ue_script_recognizes_already_exists_for_reuse(self) -> None:
        spec = {
            "effect": "WingEcho",
            "parent_path": "/Game/Materials/M_WingEcho_Master",
            "reuse_existing": True,
            "instances": [
                {
                    "path": "/Game/Materials/MI_WingEcho_Default",
                    "parent_path": "/Game/Materials/M_WingEcho_Master",
                    "params": [],
                }
            ],
        }
        script = material_instance_batch.build_ue_script(spec)
        self.assertIn('"already exists" in create_error_text', script)
        self.assertIn('row["create"]["reused_existing"] = True', script)
        self.assertIn('row["create"]["success"] = True', script)


if __name__ == "__main__":
    unittest.main(verbosity=2)
