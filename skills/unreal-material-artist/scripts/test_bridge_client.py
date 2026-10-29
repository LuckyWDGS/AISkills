from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from unreal_material_tools import bridge


SKILL_ROOT = Path(__file__).resolve().parents[1]


class ParseJsonTests(unittest.TestCase):
    def test_indented_value_after_log_lines(self):
        self.assertEqual(bridge.parse_json_output('log\n{\n  "a": [1,\n 2]\n}'), {"a": [1, 2]})

    def test_last_value_wins(self):
        self.assertEqual(bridge.parse_json_output('{"x":1}\nlog\n{"y":2}'), {"y": 2})

    def test_no_json_raises(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.parse_json_output("only text")


class ClientTests(unittest.TestCase):
    def test_retired_library_fails_before_contacting_editor(self):
        remote = MagicMock()
        with patch.object(bridge, "_load_python_remote", return_value=remote):
            client = bridge.BridgeClient(SKILL_ROOT, project="P")
            with self.assertRaisesRegex(bridge.BridgeError, "UnrealBridgeMaterialLibrary"):
                client.exec_python("unreal.UnrealBridgeMaterialLibrary.get_material_graph('/Game/M')")
        remote.run_python.assert_not_called()

    def test_endpoint_is_rejected(self):
        with self.assertRaisesRegex(bridge.BridgeError, "retired"):
            bridge.BridgeClient(SKILL_ROOT, endpoint="127.0.0.1:9876")

    def test_stock_script_runs_over_remote_execution(self):
        remote = MagicMock()
        remote.run_python.return_value = {"success": True, "output": []}
        remote.stdout_of.side_effect = lambda result, kinds=("Info",): '{"ok": true}' if kinds == ("Info",) else ""
        with patch.object(bridge, "_load_python_remote", return_value=remote):
            result = bridge.BridgeClient(SKILL_ROOT, project="P").exec_json("print('{}')")
        self.assertEqual(result, {"ok": True})
        remote.run_python.assert_called_once_with("print('{}')", project="P")


if __name__ == "__main__":
    unittest.main()
