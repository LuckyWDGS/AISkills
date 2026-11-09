"""Real background failure modes: invalid official proxies and cameras without child bindings."""

import unittest
from unittest.mock import Mock

from sequencer_tools.editor import Editor, valid_binding
from sequencer_tools.inspect import camera_ids, lint, summarize

SEQ = {"refPath": "/Game/Test/LS.LS"}
GUID = "D4E25022-1F2A-4D25-937F-BC9A8AE6D21E"
BINDING = {"bindingId": GUID, "sequence": SEQ}
INVALID = {"bindingId": "00000000-0000-0000-0000-000000000000", "sequence": "None"}


class BackgroundBindingTests(unittest.TestCase):
    def editor(self, native=BINDING, inventories=None, focused=None):
        e = Editor.__new__(Editor)
        e.calls = []
        e.python = Mock(return_value={"binding": BINDING})
        inventory = iter(inventories if inventories is not None else [[], [BINDING]])
        def seq(tool, **args):
            if tool == "get_bindings":
                return next(inventory)
            if tool == "get_focused_sequence":
                return focused
            if tool == "add_spawnable_from_class":
                if isinstance(native, Exception):
                    raise native
                return native
            raise AssertionError(tool)
        e.seq = Mock(side_effect=seq)
        return e

    def test_invalid_proxy_cannot_reach_a_setter(self):
        e = Editor.__new__(Editor)
        e.client = Mock()
        e.calls = []
        with self.assertRaisesRegex(RuntimeError, "Invalid Sequencer binding"):
            e.call("SequencerTools", "set_binding_name", binding=INVALID, name="中文")
        e.client.call_resolved_tool.assert_not_called()

    def test_malformed_or_wrong_sequence_proxy_is_rejected(self):
        for binding in [None, {}, {**BINDING, "bindingId": "not-a-guid"}, {**BINDING, "sequence": {"refPath":"None"}},
                        {**BINDING, "sequence":{"refPath":"/Game/Other.Other"}}]:
            with self.subTest(binding=binding), self.assertRaises(RuntimeError):
                valid_binding(binding, SEQ)

    def test_valid_native_binding_stays_on_mcp(self):
        e = self.editor()
        self.assertEqual(e.add_spawnable_from_class(SEQ, "/Script/Engine.CameraActor"), BINDING)
        e.python.assert_not_called()

    def test_missing_editor_session_can_use_verified_background_api(self):
        e = self.editor(native=INVALID, inventories=[[], [], [BINDING]], focused="None")
        self.assertEqual(e.add_spawnable_from_class(SEQ, "/Script/Engine.CameraActor"), BINDING)
        e.python.assert_called_once()
        script = e.python.call_args.args[0]
        self.assertIn("MovieSceneSequenceExtensions.add_spawnable_from_class", script)
        self.assertNotIn("open_level_sequence", script)

    def test_changed_inventory_refuses_fallback(self):
        e = self.editor(native=INVALID, inventories=[[], [BINDING]])
        with self.assertRaisesRegex(RuntimeError, "partial work"):
            e.add_spawnable_from_class(SEQ, "/Script/Engine.CameraActor")
        e.python.assert_not_called()

    def test_timeout_never_repeats_creation_through_python(self):
        e = self.editor(native=TimeoutError("unknown completion"), inventories=[[]])
        with self.assertRaises(TimeoutError):
            e.add_spawnable_from_class(SEQ, "/Script/Engine.CameraActor")
        e.python.assert_not_called()

    def test_invalid_result_with_focused_target_is_not_the_known_gap(self):
        e = self.editor(native=INVALID, inventories=[[], []], focused=SEQ)
        with self.assertRaisesRegex(RuntimeError, "unproven"):
            e.add_spawnable_from_class(SEQ, "/Script/Engine.CameraActor")
        e.python.assert_not_called()

    def test_unknown_editor_state_refuses_fallback(self):
        e = self.editor(native=INVALID, inventories=[[], []], focused={})
        with self.assertRaisesRegex(RuntimeError, "unknown"):
            e.add_spawnable_from_class(SEQ, "/Script/Engine.CameraActor")
        e.python.assert_not_called()

    def test_missing_created_binding_fails_readback(self):
        e = self.editor(inventories=[[], []])
        with self.assertRaisesRegex(RuntimeError, "readback"):
            e.add_spawnable_from_class(SEQ, "/Script/Engine.CameraActor")

    def test_unrecognized_invalid_proxy_never_triggers_another_creation(self):
        for native in [None, {}, {**BINDING, 'bindingId': 'damaged'},
                       {**BINDING, 'sequence': {'refPath': '/Game/Other.Other'}}]:
            e = self.editor(native=native, inventories=[[], [], [BINDING]])
            with self.subTest(native=native), self.assertRaisesRegex(RuntimeError, 'unrecognized'):
                e.add_spawnable_from_class(SEQ, '/Script/Engine.CameraActor')
            e.python.assert_not_called()

    def test_extra_new_binding_is_partial_work_not_a_clean_creation(self):
        extra = {**BINDING, 'bindingId': '05099539-89F4-4EDB-A08C-2FBA43BF44D4'}
        e = self.editor(inventories=[[], [BINDING, extra]])
        with self.assertRaisesRegex(RuntimeError, 'readback'):
            e.add_spawnable_from_class(SEQ, '/Script/Engine.CameraActor')
        e.python.assert_not_called()


class CameraClassificationTests(unittest.TestCase):
    def dump(self, camera=True):
        return {"sequence":"/Game/Test/LS.LS", "display_rate":[30,1], "tick_resolution":[24000,1],
                "playback":[0,90], "tracks":[], "bindings":[{"id":GUID,"name":"Actor", "display":"摄影机",
                    "children":[], "parent":None,"tracks":[],"is_camera":camera}]}

    def test_camera_actor_without_child_binding_is_listed(self):
        dump = self.dump()
        self.assertEqual(camera_ids(dump), {GUID})
        self.assertEqual(summarize(dump)["cameras"], ["摄影机"])

    def test_camera_without_child_still_needs_a_cut_track(self):
        self.assertIn("no_camera_cuts", {r["rule"] for r in lint(self.dump())})

    def test_display_name_does_not_turn_a_non_camera_into_a_camera(self):
        self.assertEqual(camera_ids(self.dump(camera=False)), set())


if __name__ == "__main__":
    unittest.main()
