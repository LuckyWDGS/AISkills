from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import shader_cost_attribution
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def audit_payload() -> dict[str, object]:
    return {
        "tool": "material_audit",
        "material_path": "/Game/Materials/M_Costly",
        "material_info": {"path": "/Game/Materials/M_Costly", "blend_mode": "Additive", "material_domain": "Surface"},
        "analysis": {"max_instructions": 210, "sampler_count": 6, "shader_stats_ready": True},
        "raw_graph": {
            "nodes": [
                {"class_name": "MaterialExpressionTextureSample", "caption": "Texture Sample"},
                {"class_name": "MaterialExpressionCustom", "caption": "Custom HLSL"},
                {"class_name": "MaterialExpressionNoise", "caption": "Noise"},
            ]
        },
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = shader_cost_attribution.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class ShaderCostAttributionTests(unittest.TestCase):
    def test_attribution_ranks_categories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root, "audit.json", audit_payload())
            code, stdout, stderr = run_tool(["--root", str(root), "--audit-report", str(audit)])
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            categories = [item["category"] for item in report["attributions"][0]["categories"]]
            self.assertIn("texture_samples", categories)
            self.assertIn("custom_hlsl", categories)


if __name__ == "__main__":
    unittest.main(verbosity=2)
