"""EditorAppToolset capture helpers; no Unreal editor required."""

import base64
import json
from pathlib import Path
import struct
import tempfile
import unittest

from ue_mcp import McpError
from ue_mcp import capture


PNG = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 64, 32) + b"\x08\x06\x00\x00\x00"


def tool_result(value):
    return {"content": [{"type": "text", "text": json.dumps({"returnValue": value})}]}


class FakeClient:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def call_resolved_tool(self, toolset, tool, arguments):
        self.calls.append((toolset, tool, arguments))
        if self.fail:
            raise McpError("Function \"CaptureViewport\" failed")
        image = {"mimeType": "image/png", "data": base64.b64encode(PNG + bytes([len(self.calls)])).decode()}
        if tool == "CaptureAssetImage":
            return tool_result(image)
        return tool_result({"image": image, "cameraLocation": {"x": 1, "y": 2, "z": 3},
                            "cameraRotation": {"pitch": 0, "yaw": 90, "roll": 0}, "cameraFOV": 90})


class ModernClient:
    def __init__(self, missing_image=False, changed_view=""):
        self.calls = []
        self.missing_image = missing_image
        self.changed_view = changed_view

    def list_toolsets(self):
        return [{"name": "SceneCaptureToolset.SceneCaptureToolset"}]

    def call_resolved_tool(self, toolset, tool, arguments):
        self.calls.append((toolset, tool, arguments))
        if tool == "GetActiveEditorView":
            view = {"world":{"refPath":"/Game/Test.Test"},
                "camera":{"location":{"x":1,"y":2,"z":3},
                    "rotation":{"pitch":0,"yaw":90,"roll":0},"fOV":80},
                "sourceDimensions":{"x":64,"y":32}}
            if len(self.calls) > 1:
                if self.changed_view == "camera":
                    view["camera"]["location"]["z"] = 4
                elif self.changed_view == "world":
                    view["world"]["refPath"] = "/Game/Other.Other"
            return tool_result(view)
        value = "urn:toolresult:Asset:image" if tool == "CaptureAssetImage" else {
            "image":"urn:toolresult:SceneCapture:image", "width":64,"height":32,
            "metadata":{"camera":arguments["camera"]},"warnings":[]}
        result = tool_result(value)
        if not self.missing_image:
            result["content"].append({"type":"image","mimeType":"image/png", "data":base64.b64encode(PNG).decode()})
        return result


class CaptureTests(unittest.TestCase):
    def test_modern_scene_capture_retains_image_block_and_camera_state(self):
        client = ModernClient()
        pose = capture.parse_pose("10,20,30,-30,180,0")
        with tempfile.TemporaryDirectory() as folder:
            report = capture.capture_report(client,"viewport",Path(folder),"modern",pose=pose)
            self.assertEqual(Path(report["frames"][0]["path"]).read_bytes(),PNG)
        self.assertTrue(report["ok"])
        self.assertEqual(report["transport"],"epic-mcp SceneCaptureToolset")
        self.assertTrue(report["frames"][0]["camera_unchanged"])
        self.assertEqual(report["frames"][0]["camera_location"],pose["location"])
        args = client.calls[1][2]
        self.assertEqual(args["options"],{"width":64,"height":32,"screenPercentage":1})
        self.assertEqual([call[1] for call in client.calls],["GetActiveEditorView","Capture","GetActiveEditorView"])

    def test_modern_asset_thumbnail_retains_image_block(self):
        with tempfile.TemporaryDirectory() as folder:
            report = capture.capture_report(ModernClient(),"asset",Path(folder),"asset",asset_path="/Game/Test")
            self.assertTrue(report["ok"])
            self.assertEqual(Path(report["frames"][0]["path"]).read_bytes(),PNG)

    def test_changed_editor_view_fails_without_discarding_evidence_or_restoring(self):
        for changed in ("camera", "world"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                client = ModernClient(changed_view=changed)
                report = capture.capture_report(client,"viewport",Path(folder),"changed",frames=3)
                self.assertFalse(report["ok"])
                self.assertIn("changed during capture",report["error"])
                self.assertEqual(len(report["frames"]),1)
                frame = report["frames"][0]
                self.assertFalse(frame["camera_unchanged"])
                self.assertEqual(Path(frame["path"]).read_bytes(),PNG)
                self.assertFalse((Path(folder)/"changed-f01.png").exists())
                if changed == "camera":
                    self.assertEqual(frame["camera_before"]["location"]["z"],3)
                    self.assertEqual(frame["camera_after"]["location"]["z"],4)
                else:
                    self.assertEqual(frame["world_before"]["refPath"],"/Game/Test.Test")
                    self.assertEqual(frame["world_after"]["refPath"],"/Game/Other.Other")
                self.assertEqual([call[1] for call in client.calls],
                                 ["GetActiveEditorView","Capture","GetActiveEditorView"])

    def test_media_reference_without_bytes_is_not_a_valid_image(self):
        with tempfile.TemporaryDirectory() as folder:
            report = capture.capture_report(ModernClient(missing_image=True),"asset",Path(folder),"asset",asset_path="/Game/Test")
            self.assertFalse(report["ok"])
            self.assertIn("not a downloadable URL", report["error"])
            self.assertFalse((Path(folder)/"asset.png").exists())

    def test_invalid_or_truncated_image_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"invalid.png"
            for data in ("broken base64",base64.b64encode(PNG[:17]).decode()):
                with self.assertRaises(McpError):
                    capture.save_image({"data":data},path)
                self.assertFalse(path.exists())

    def test_pose_and_paths(self):
        pose = capture.parse_pose("1,2,3,-10,90,0")
        self.assertEqual((pose["location"]["z"], pose["rotation"]["yaw"]), (3.0, 90.0))
        with self.assertRaises(McpError):
            capture.parse_pose("1,2,3")
        self.assertEqual(capture.asset_package_path("/Game/M/M_X.M_X"), "/Game/M/M_X")
        self.assertEqual(capture.asset_package_path("/Game/M/M_X"), "/Game/M/M_X")

    def test_asset_capture(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as folder:
            report = capture.capture_report(client, "asset", Path(folder), "m", asset_path="/Game/M/M_X.M_X")
            self.assertTrue(Path(report["frames"][0]["path"]).read_bytes().startswith(PNG))
        self.assertTrue(report["ok"])
        self.assertEqual(report["schema_version"], capture.SCHEMA_VERSION)
        self.assertEqual((report["frames"][0]["width"], report["frames"][0]["height"]), (64, 32))
        self.assertEqual(client.calls, [("EditorAppToolset", "CaptureAssetImage", {"assetPath": "/Game/M/M_X"})])

    def test_viewport_frames_send_every_optional_argument(self):
        client = FakeClient()
        pose = capture.parse_pose("0,0,100,0,0,0")
        with tempfile.TemporaryDirectory() as folder:
            report = capture.capture_report(client, "viewport", Path(folder), "fx", pose=pose, frames=2)
        self.assertEqual(len(report["frames"]), 2)
        self.assertEqual(report["distinct_frames"], 2)
        self.assertEqual(report["frames"][0]["camera_rotation"]["yaw"], 90)
        self.assertTrue(report["ok"])
        self.assertEqual(report["error"], "")
        self.assertNotIn("camera_unchanged", report["frames"][0])
        arguments = client.calls[0][2]
        # UE 5.8 rejects omitted optional arguments ("needs a default value").
        self.assertEqual(set(arguments), {"annotations", "bShowUI", "captureTransform"})
        self.assertEqual(arguments["annotations"], capture.NO_ANNOTATIONS)

    def test_failure_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as folder:
            report = capture.capture_report(FakeClient(fail=True), "viewport", Path(folder), "fx")
        self.assertFalse(report["ok"])
        self.assertIn("CaptureViewport", report["error"])


if __name__ == "__main__":
    unittest.main()
