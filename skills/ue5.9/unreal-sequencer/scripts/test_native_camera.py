"""Safety checks for create-only UE 5.9 camera sequences."""

import copy
import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from sequencer_tools.native_camera import NativeCameraBuilder, camera_transform, same_root_binding, validate_binding, validate_plan, validate_project, verify_linear_samples


PLAN = {"sequence": "/Game/Demo/Cinematics/LS_Intro", "module_id": "Demo.Intro.v1",
        "description_zh": "开场镜头，退出时恢复相机与输入", "binding_name": "IntroCamera",
        "binding_tag": "Demo.IntroCamera", "display_rate": [30000, 1001], "playback": [0, 120],
        "camera_keys": [{"frame": 0, "location": [0, 1000, 200], "look_at": [0, 0, 200]},
                        {"frame": 119, "location": [100, 1000, 200], "look_at": [100, 0, 200]}]}
SEQ = {"refPath": "/Game/Demo/Cinematics/LS_Intro.LS_Intro"}
BINDING = {"bindingId": "7520973A-856A-41B0-9CCF-6B08399D1ACA", "sequence": SEQ}


class NativeCameraPlanTests(unittest.TestCase):
    def test_rational_rate_and_source_plan_survive_validation(self):
        original = copy.deepcopy(PLAN)
        result = validate_plan(PLAN)
        self.assertEqual(result["display_rate"], [30000, 1001])
        self.assertEqual(PLAN, original)

    def test_camera_looks_from_positive_y_towards_negative_y(self):
        values = camera_transform([0, 1000, 200], [0, 0, 200])
        self.assertEqual(values, [0, 1000, 200, 0, 0, -90, 1, 1, 1])

    def test_yaw_crossing_uses_shortest_rotation(self):
        plan = copy.deepcopy(PLAN)
        plan["camera_keys"][0].update(location=[0, 0, 0], look_at=[-1, 0.01, 0])
        plan["camera_keys"][1].update(location=[0, 0, 0], look_at=[-1, -0.01, 0])
        keys = validate_plan(plan)["camera_keys"]
        self.assertLess(abs(keys[1]["transform"][5] - keys[0]["transform"][5]), 2)

    def test_bad_numbers_and_empty_ranges_refuse_before_editor_access(self):
        changes = [{"playback": [0, 0]}, {"display_rate": [30, 0]}, {"display_rate": [True, 1]},
                   {"playback": [0, 100001]}, {"sequence": "/Engine/Shared/LS"}]
        for values in changes:
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_plan({**PLAN, **values})
        for value in [math.nan, math.inf, True]:
            plan = copy.deepcopy(PLAN)
            plan["camera_keys"][0]["location"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_plan(plan)

    def test_exclusive_end_cannot_be_used_as_visible_pose(self):
        plan = copy.deepcopy(PLAN)
        plan["camera_keys"][-1]["frame"] = 120
        with self.assertRaisesRegex(ValueError, "half-open"):
            validate_plan(plan)

    def test_same_position_target_is_not_a_valid_camera(self):
        with self.assertRaises(ValueError):
            camera_transform([0, 0, 0], [0, 0, 0])

    def test_project_guard_requires_full_uproject_path(self):
        for path in [None, "MCPSI", "Demo.uproject", "C:/Project"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_project(path)
        self.assertEqual(validate_project("E:/Project/Demo.uproject"), "E:/Project/Demo.uproject")

    def test_invalid_and_foreign_binding_never_pass(self):
        for value in [None, {}, {**BINDING, "bindingId": "00000000-0000-0000-0000-000000000000"},
                      {**BINDING, "bindingId": "broken"}, {**BINDING, "sequence": {"refPath": "/Game/Other.Other"}}]:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                validate_binding(value, SEQ)
        self.assertEqual(validate_binding(BINDING, SEQ), BINDING)

    def test_wrong_engine_refuses_without_any_editor_tool(self):
        client = Mock(initialize_result={"_meta": {"com.epicgames.unrealengine/instance": {"engineVersion": "5.8.4"}}})
        with self.assertRaisesRegex(RuntimeError, "requires.*5.9"):
            NativeCameraBuilder(client).build(PLAN)
        client.call_resolved_tool.assert_not_called()

    def test_timeout_is_recorded_without_retry(self):
        client = Mock()
        client.call_resolved_tool.side_effect = TimeoutError("unknown completion")
        builder = NativeCameraBuilder(client)
        with self.assertRaises(TimeoutError):
            builder.call("LevelSequenceEditorBlueprintLibrary", "CreateLevelSequence", packagePath="/Game/Demo", assetName="LS")
        self.assertEqual(client.call_resolved_tool.call_count, 1)
        self.assertEqual(builder.records[0]["error"], "unknown completion")

    def test_root_binding_space_alias_does_not_discard_identity(self):
        local = {"guid": BINDING["bindingId"], "sequenceId": 0, "resolveParentIndex": 0}
        root = {**local, "resolveParentIndex": -1}
        self.assertTrue(same_root_binding(local, root))
        self.assertEqual(local["resolveParentIndex"], 0)
        self.assertEqual(root["resolveParentIndex"], -1)
        self.assertFalse(same_root_binding(local, {**root, "sequenceId": 1}))
        self.assertFalse(same_root_binding(local, {**root, "resolveParentIndex": 2}))
        self.assertFalse(same_root_binding(local, {**root, "guid": "another"}))

    def test_curve_verification_rejects_wrong_interpolation_between_correct_keys(self):
        with self.assertRaisesRegex(RuntimeError, "at 1"):
            verify_linear_samples([0, 0.2, 1], [(0, 0), (2, 1)], 0, 3, "camera")
        verify_linear_samples([0, 0.5, 1], [(0, 0), (2, 1)], 0, 3, "camera")

    def test_curve_verification_checks_piecewise_and_constant_extrapolation(self):
        verify_linear_samples([0, 0, 1, 2, 1, 1], [(1, 0), (3, 2), (4, 1)], 0, 6, "Fade")
        for values in [[0, 0, 1, 2, 1], [0, 0, math.nan, 2, 1, 1], [0, False, 1, 2, 1, 1]]:
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                verify_linear_samples(values, [(1, 0), (3, 2), (4, 1)], 0, 6, "Fade")

    def test_cli_invalid_plan_writes_a_refusal_report_without_editor_access(self):
        from sequence_native_camera import main
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            out = Path(directory) / "report.json"
            plan.write_text(json.dumps({**PLAN, "playback": [0, 0]}), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main([str(plan), "--execute", "--out", str(out)])
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertFalse(report["executed"])
            self.assertEqual(report["outcome"], "refused_before_creation")
            self.assertFalse(report["creation_attempted"])
            self.assertNotIn("identity", report)

    def test_cli_creation_timeout_reports_unknown_completion_without_retry(self):
        from sequence_native_camera import main
        client = Mock(
            initialize_result={"_meta": {"com.epicgames.unrealengine/instance": {"engineVersion": "5.9.0"}}},
            expected_project="E:/Project/Demo.uproject")
        client.call_resolved_tool.side_effect = [False, None, False, TimeoutError("response was lost")]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            plan, out = folder / "plan.json", folder / "report.json"
            plan.write_text(json.dumps(PLAN), encoding="utf-8")
            with patch("sequence_native_camera.connect", return_value=client), \
                    patch.dict("os.environ", {}, clear=False), contextlib.redirect_stdout(io.StringIO()):
                code = main([str(plan), "--execute", "--project", "E:/Project/Demo.uproject",
                             "--state-dir", str(folder / "state"), "--out", str(out)])
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertFalse(report["executed"])
            self.assertTrue(report["creation_attempted"])
            self.assertIsNone(report["created"])
            self.assertEqual(report["outcome"], "unknown_creation_completion")
            self.assertEqual(report["validated_plan"]["sequence"], PLAN["sequence"])
            self.assertEqual(report["calls"][-1]["tool"], "CreateLevelSequence")
            self.assertEqual(report["calls"][-1]["error"], "response was lost")
        self.assertEqual(client.call_resolved_tool.call_count, 4)
        client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
