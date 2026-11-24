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


class CaptureTests(unittest.TestCase):
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
