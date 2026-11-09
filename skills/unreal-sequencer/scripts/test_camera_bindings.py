"""[CINE.CameraCuts] 完整绑定空间、错误回读及后台官方 MCP 路由回归。"""
import json
import unittest
from copy import deepcopy
from unittest.mock import Mock

from sequencer_tools.editor import Editor, binding_id_data
from sequencer_tools.inspect import mcp_dump

SEQ = {"refPath": "/Game/Test/LS.LS"}
GUID = "D4E25022-1F2A-4D25-937F-BC9A8AE6D21E"
BINDING = {"bindingId": GUID, "sequence": SEQ}
CUT = {"refPath": SEQ["refPath"] + ":MovieScene_0.CutTrack.Cut_0"}
CUT2 = {"refPath": SEQ["refPath"] + ":MovieScene_0.CutTrack.Cut_1"}
EXPECTED = {"guid": GUID, "sequenceId": 17, "resolveParentIndex": -1}
EMPTY = {"guid": "00000000-0000-0000-0000-000000000000", "sequenceId": 0, "resolveParentIndex": -1}


def editor(*, expected=None, initial=None, readback=None, setter=True):
    e = Editor.__new__(Editor)
    e.calls, e.python = [], Mock()
    e.seq = Mock(side_effect=lambda tool, **kw: [BINDING] if tool == "get_bindings" else deepcopy(EXPECTED if expected is None else expected))
    state = {cut["refPath"]: deepcopy(EMPTY if initial is None else initial) for cut in (CUT, CUT2)}
    def call(group, tool, **args):
        if group != "ObjectTools":
            raise AssertionError((group, tool))
        path = args["instance"]["refPath"]
        if tool == "get_properties":
            return json.dumps({"cameraBindingId": state[path]})
        if tool == "set_properties":
            if isinstance(setter, Exception):
                raise setter
            state[path] = deepcopy(readback if readback is not None else json.loads(args["values"])["cameraBindingId"])
            return setter
        raise AssertionError(tool)
    e.call = Mock(side_effect=call)
    return e


def writes(e):
    return [c for c in e.call.call_args_list if c.args[1] == "set_properties"]


class CameraBindingTests(unittest.TestCase):
    def test_complete_id_is_written_and_read_only_through_mcp(self):
        e = editor()
        rows = e.bind_camera_cuts('/Game/Test/LS', [(CUT, GUID.lower())])
        self.assertEqual(rows[0]['binding_id'], EXPECTED)
        self.assertTrue(rows[0]['ok'])
        self.assertTrue(rows[0]['changed'])
        self.assertEqual(json.loads(writes(e)[0].kwargs['values']), {'cameraBindingId': EXPECTED})
        self.assertEqual({c.args[0] for c in e.seq.call_args_list}, {'get_bindings', 'get_binding_id'})
        e.python.assert_not_called()

    def test_already_bound_cut_does_not_repeat_write(self):
        e = editor(initial=EXPECTED)
        rows = e.bind_camera_cuts('/Game/Test/LS.LS', [(CUT, GUID)])
        self.assertFalse(rows[0]['changed'])
        self.assertEqual(writes(e), [])
        e.python.assert_not_called()

    def test_unknown_or_cross_sequence_targets_fail_before_any_write(self):
        other = {'refPath': '/Game/Other.Other:MovieScene_0.CutTrack.Cut_0'}
        for cuts in [[(CUT, GUID), (other, GUID)], [(CUT, GUID), (CUT, GUID)],
                     [(CUT, '05099539-89F4-4EDB-A08C-2FBA43BF44D4')]]:
            e = editor()
            with self.subTest(cuts=cuts), self.assertRaises(RuntimeError):
                e.bind_camera_cuts('/Game/Test/LS', cuts)
            self.assertEqual(writes(e), [])
            e.python.assert_not_called()

    def test_incomplete_id_or_different_guid_cannot_reach_a_setter(self):
        for expected in [{'guid': GUID}, {**EXPECTED, 'sequenceId': True},
                         {**EXPECTED, 'guid': EMPTY['guid']}]:
            e = editor(expected=expected)
            with self.subTest(expected=expected), self.assertRaises(RuntimeError):
                e.bind_camera_cuts('/Game/Test/LS', [(CUT, GUID)])
            self.assertEqual(writes(e), [])

    def test_matching_guid_in_wrong_resolution_space_fails_readback(self):
        for field in ['sequenceId', 'resolveParentIndex']:
            e = editor(readback={**EXPECTED, field: 0})
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, 'readback failed'):
                e.bind_camera_cuts('/Game/Test/LS', [(CUT, GUID), (CUT2, GUID)])
            self.assertEqual(len(writes(e)), 1)
            e.python.assert_not_called()

    def test_false_setter_is_not_accepted_even_when_values_match(self):
        e = editor(setter=False)
        with self.assertRaisesRegex(RuntimeError, 'readback failed'):
            e.bind_camera_cuts('/Game/Test/LS', [(CUT, GUID), (CUT2, GUID)])
        self.assertEqual(len(writes(e)), 1)
        e.python.assert_not_called()

    def test_timeout_stops_without_alternate_write_or_python(self):
        e = editor(setter=TimeoutError('completion unknown'))
        with self.assertRaises(TimeoutError):
            e.bind_camera_cuts('/Game/Test/LS', [(CUT, GUID), (CUT2, GUID)])
        self.assertEqual(len(writes(e)), 1)
        e.python.assert_not_called()

    def test_missing_property_refuses_writing(self):
        e = editor()
        e.call.return_value, e.call.side_effect = '{}', None
        with self.assertRaisesRegex(RuntimeError, 'property is unavailable'):
            e.bind_camera_cuts('/Game/Test/LS', [(CUT, GUID)])
        self.assertEqual(writes(e), [])

    def test_unknown_or_duplicate_inventory_refuses_writing(self):
        for inventory in [None, [BINDING, BINDING]]:
            e = editor()
            e.seq.return_value, e.seq.side_effect = inventory, None
            with self.subTest(inventory=inventory), self.assertRaises(RuntimeError):
                e.bind_camera_cuts('/Game/Test/LS', [(CUT, GUID)])
            e.call.assert_not_called()

    def test_empty_request_does_not_contact_editor(self):
        e = editor()
        self.assertEqual(e.bind_camera_cuts('/Game/Test/LS', []), [])
        e.seq.assert_not_called()
        e.call.assert_not_called()

    def test_zero_guid_is_preserved_for_unbound_cut_inspection(self):
        e = editor()
        self.assertEqual(e.camera_binding_id(CUT), EMPTY)
        self.assertEqual(binding_id_data({**EXPECTED, 'guid': GUID.lower()}), EXPECTED)

    def test_cut_inspection_uses_mcp_without_python_metadata_request(self):
        e = Mock(spec=Editor)
        track = {'refPath': SEQ['refPath'] + ':MovieScene_0.CutTrack'}
        def seq(tool, **kw):
            if tool in ('get_display_rate', 'get_tick_resolution'): return {'numerator': 30, 'denominator': 1}
            if tool == 'get_playback_range' or tool == 'get_section_range': return {'start': 0, 'end': 30}
            if tool == 'get_tracks_on_sequence': return [track]
            if tool == 'get_sections': return [CUT]
            if tool in ('has_section_start_frame', 'has_section_end_frame'): return True
            if tool == 'get_track_display_name': return '切镜'
            return []
        e.seq.side_effect, e.key.return_value = seq, []
        e.call.side_effect = lambda group, tool, **kw: {'refPath': '/Script/MovieSceneTracks.' + (
            'MovieSceneCameraCutTrack' if kw['instance'] == track else 'MovieSceneCameraCutSection')}
        e.camera_binding_id.return_value = EXPECTED
        dump = mcp_dump(e, '/Game/Test/LS')
        self.assertEqual(dump['tracks'][0]['sections'][0]['camera'], GUID.replace('-', ''))
        self.assertEqual(dump['tracks'][0]['sections'][0]['camera_binding'], EXPECTED)
        e.python.assert_not_called()


if __name__ == '__main__':
    unittest.main()
