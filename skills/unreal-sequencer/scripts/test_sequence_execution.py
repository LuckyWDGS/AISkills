"""Regressions for project/UI guards, exact frame rates, fresh render evidence and cleanup."""

import json
import re
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

import sequence_plan_apply as apply
import sequence_render as render
from sequence_sample import check_keys, occlusion_checks, sample_session, verification
from sequencer_tools.editor import Editor
from sequencer_tools.inspect import mcp_dump
from sequencer_tools.plan import frame_rate, normalize


def build_editor(exists=False):
    editor = Mock(spec=Editor)
    editor.call.return_value = False
    editor.sequence_state.return_value = {'sequence': None}
    editor.asset_exists.return_value = exists
    editor.sequence_session.return_value = MagicMock()
    editor.seq.side_effect = lambda tool, **kw: {'refPath': '/Game/T/LS.LS'} if tool == 'create_level_sequence' else []
    return editor


class RateAndBuildTests(unittest.TestCase):
    def test_fractional_and_ntsc_rates_reach_mcp_without_truncation(self):
        for rate, exact in [(29.97, Fraction(2997, 100)), ('30000/1001', Fraction(30000, 1001)),
                            ({'numerator': 24000, 'denominator': 1001}, Fraction(24000, 1001))]:
            with self.subTest(rate=rate):
                plan = normalize({'sequence': {'path': '/Game/T/LS', 'fps': rate, 'seconds': 10}})
                editor = build_editor()
                apply.build(plan, editor, allow_editor_ui=True)
                call = next(c for c in editor.seq.call_args_list if c.args[0] == 'set_display_rate')
                self.assertEqual((call.kwargs['numerator'], call.kwargs['denominator']), (exact.numerator, exact.denominator))
                self.assertEqual(plan['sequence']['end_frame'], round(10 * exact))
                self.assertEqual(normalize(plan), plan)

    def test_invalid_rates_fail_offline(self):
        for rate in (0, -1, True, 'nan', 'inf', '30000/0', {'numerator': 30, 'denominator': 0}):
            with self.subTest(rate=rate), self.assertRaises((ValueError, ZeroDivisionError)):
                frame_rate(rate)

    def test_default_ui_refusal_precedes_any_asset_write(self):
        editor = build_editor()
        editor.sequence_state.side_effect = lambda **kw: Editor.sequence_state(editor, **kw)
        with self.assertRaises(RuntimeError):
            apply.build(normalize({'sequence': {'path': '/Game/T/LS', 'seconds': 1}}), editor)
        editor.seq.assert_not_called()
        editor.backup_asset.assert_not_called()

    def test_replace_requires_saved_backup_before_creation(self):
        editor = build_editor(exists=True)
        with self.assertRaises(RuntimeError):
            apply.build(normalize({'sequence': {'path': '/Game/T/LS', 'seconds': 1}}), editor,
                        replace=True, allow_editor_ui=True)
        editor.seq.assert_not_called()
        editor.backup_asset.assert_not_called()

    def test_backup_failure_preserves_original(self):
        editor = build_editor(exists=True)
        editor.backup_asset.side_effect = RuntimeError('save failed')
        with self.assertRaises(RuntimeError):
            apply.build(normalize({'sequence': {'path': '/Game/T/LS', 'seconds': 1}}), editor,
                        replace=True, save=True, backup_path='/Game/T/LS_Backup', allow_editor_ui=True)
        editor.seq.assert_not_called()

    def test_currently_open_sequence_is_never_deleted_for_replace(self):
        editor = build_editor(exists=True)
        editor.sequence_state.return_value = {'sequence': {'refPath': '/Game/T/LS.LS'}}
        with self.assertRaisesRegex(RuntimeError, 'currently open'):
            apply.build(normalize({'sequence': {'path': '/Game/T/LS', 'seconds': 1}}), editor,
                        replace=True, save=True, backup_path='/Game/T/LS_Backup', allow_editor_ui=True)
        editor.backup_asset.assert_not_called()
        editor.seq.assert_not_called()


def ui_editor(*, playing=False, focused=None, open_timeout=False):
    old, new = {'refPath': '/Game/T/Old.Old'}, {'refPath': '/Game/T/New.New'}
    state = {'current': old}
    editor = Editor.__new__(Editor)
    editor.project, editor.calls, editor.client = 'Project', [], Mock()

    def call(ts, tool, args):
        if tool == 'get_current_sequence': return state['current']
        if tool == 'get_focused_sequence': return focused or state['current']
        if tool == 'is_playing': return playing
        if tool == 'get_playhead_frame': return 44
        if tool == 'get_playback_speed': return 0.5
        if tool == 'get_loop_mode': return False
        if tool == 'open_sequence':
            state['current'] = args['sequence']
            if open_timeout and args['sequence'] == new:
                raise TimeoutError('opened but response lost')
        if tool == 'close_sequence': state['current'] = None
        return True
    editor.client.call_resolved_tool.side_effect = call
    return editor, state, old, new


class SessionTests(unittest.TestCase):
    def test_failed_keep_open_without_prior_sequence_closes_own_tab(self):
        editor, state, _, new = ui_editor()
        state['current'] = None
        before = editor.sequence_state(allow_editor_ui=True)
        with self.assertRaises(ValueError):
            with editor.sequence_session(new, before, keep_open=True):
                raise ValueError('failed')
        self.assertIsNone(state['current'])

    def test_exception_restores_prior_sequence_and_playhead(self):
        editor, state, old, new = ui_editor()
        before = editor.sequence_state(allow_editor_ui=True)
        with self.assertRaises(ValueError):
            with editor.sequence_session(new, before):
                raise ValueError('key write failed')
        self.assertEqual(state['current'], old)
        self.assertTrue(any(c.get('tool', '').endswith('set_playhead_frame') and c['args']['frame'] == 44 for c in editor.calls))

    def test_open_timeout_still_restores_owned_session(self):
        editor, state, old, new = ui_editor(open_timeout=True)
        before = editor.sequence_state(allow_editor_ui=True)
        with self.assertRaises(TimeoutError):
            with editor.sequence_session(new, before):
                self.fail('opening should have raised')
        self.assertEqual(state['current'], old)

    def test_active_playback_and_nested_focus_are_preserved(self):
        for options in ({'playing': True}, {'focused': {'refPath': '/Game/T/Sub.Sub'}}):
            editor, state, old, _ = ui_editor(**options)
            with self.assertRaises(RuntimeError):
                editor.sequence_state(allow_editor_ui=True)
            self.assertEqual(state['current'], old)
            self.assertFalse(any(c.get('tool', '').endswith(('open_sequence', 'close_sequence', '.pause')) for c in editor.calls))

    def test_user_switch_during_operation_is_not_overwritten(self):
        editor, state, _, new = ui_editor()
        before = editor.sequence_state(allow_editor_ui=True)
        other = {'refPath': '/Game/T/UserChoice.UserChoice'}
        with editor.sequence_session(new, before):
            state['current'] = other
        self.assertEqual(state['current'], other)

    def test_asset_queries_and_save_use_official_mcp(self):
        editor = Editor.__new__(Editor)
        editor.call, editor.python = Mock(side_effect=[True, True, False]), Mock()
        self.assertTrue(editor.asset_exists('/Game/T/LS.LS'))
        self.assertTrue(editor.save_asset('/Game/T/LS.LS'))
        self.assertEqual([c.args[:2] for c in editor.call.call_args_list],
                         [('AssetTools', 'exists'), ('AssetTools', 'save_assets'), ('AssetTools', 'is_dirty')])
        editor.python.assert_not_called()

    def test_unknown_asset_existence_is_not_treated_as_missing(self):
        editor = Editor.__new__(Editor)
        for value in (None, 'false', {}):
            editor.call = Mock(return_value=value)
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'existence is unknown'):
                editor.asset_exists('/Game/T/LS')

    def test_background_structure_reads_need_no_python_for_empty_sequence(self):
        editor = Mock()
        def seq(tool, **kw):
            if tool in ('get_display_rate', 'get_tick_resolution'): return {'numerator': 30, 'denominator': 1}
            if tool == 'get_playback_range': return {'start': 0, 'end': 30}
            return []
        editor.seq.side_effect = seq
        result = mcp_dump(editor, '/Game/T/LS')
        self.assertEqual(result['playback'], [0, 30])
        editor.python.assert_not_called()

    def test_nonempty_structure_keys_use_mcp_and_python_only_supplies_missing_metadata(self):
        editor = Mock()
        ref = lambda path: {'refPath': path}
        track, section = ref('LS.Track'), ref('LS.Track.Section')
        binding = {'bindingId': 'AB-CD', 'sequence': ref('/Game/T/LS.LS')}
        def seq(tool, **kw):
            if tool in ('get_display_rate', 'get_tick_resolution'): return {'numerator': 30000, 'denominator': 1001}
            if tool == 'get_playback_range': return json.dumps({'start': 0, 'end': 60})
            if tool == 'get_bindings': return [binding]
            if tool == 'get_binding_name': return '镜头'
            if tool == 'get_tracks_on_binding': return [track]
            if tool == 'get_track_display_name': return 'Transform'
            if tool == 'get_sections': return [section]
            if tool in ('has_section_start_frame', 'has_section_end_frame'): return True
            if tool == 'get_section_range': return {'start': 0, 'end': 60}
            return []
        editor.seq.side_effect = seq
        editor.key.side_effect = lambda tool, **kw: ['Location.X'] if tool == 'get_channel_names' else '[{"frame": 0, "value": 12.5}]'
        editor.call.side_effect = lambda ts, tool, **kw: ref('/Script/MovieSceneTracks.' + ('MovieScene3DTransformTrack' if kw['instance'] == track else 'MovieScene3DTransformSection'))
        editor.python.return_value = {'bindings': {'ABCD': {'name': 'CineCameraActor', 'parent': None}}, 'sections': {}}
        result = mcp_dump(editor, '/Game/T/LS')
        row = result['bindings'][0]
        self.assertEqual((row['name'], row['display']), ('CineCameraActor', '镜头'))
        self.assertEqual(row['tracks'][0]['sections'][0]['channels'][0]['keys'], [[0, 12.5]])
        self.assertEqual(result['display_rate'], [30000, 1001])
        script = editor.python.call_args.args[0]
        self.assertNotIn('get_keys(', script)
        self.assertFalse(any(c.args[0] in ('open_sequence', 'set_playhead_frame') for c in editor.seq.call_args_list))


class FakeRenderer:
    def __init__(self, *, callback=True, write=True, size=(32, 24)):
        self.callback, self.write, self.size, self.token = callback, write, size, ''

    def python(self, script, **kwargs):
        folder = Path(json.loads(re.search(r'unreal.DirectoryPath\(("[^\n]+")\)', script).group(1)))
        self.token = re.search(r'unreal.log\("(CODEX_RENDER_\w+) ', script).group(1)
        if self.write:
            Image.new('RGB', self.size).save(folder / 'LS.0000.png')
        return {'started': True, 'mrq': False}

    def call(self, *args, **kwargs):
        return [] if self.callback is None else [{'message': self.token + ' ' + str(self.callback)}]


class RenderTests(unittest.TestCase):
    def run_render(self, renderer, out):
        with patch.object(render.time, 'monotonic', side_effect=[0, 0, 1]), patch.object(render.time, 'sleep'):
            return render.render_range(renderer, '/Game/T/LS', out, 0, 1, (32, 24), 0.5, allow_editor_ui=True)

    def test_stale_parent_images_cannot_prove_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            old = out / 'LS.0000.png'
            Image.new('RGB', (32, 24)).save(old)
            result = self.run_render(FakeRenderer(callback=None, write=False), out)
            self.assertFalse(result['ok'])
            self.assertEqual(result['status'], 'unknown')
            self.assertTrue(old.exists())

    def test_callback_and_current_decodable_frames_are_both_required(self):
        for renderer, success in ((FakeRenderer(), True), (FakeRenderer(callback=None), False),
                                  (FakeRenderer(write=False), False), (FakeRenderer(size=(8, 8)), False),
                                  (FakeRenderer(callback=False), False)):
            with self.subTest(renderer=renderer.__dict__), tempfile.TemporaryDirectory() as tmp:
                result = self.run_render(renderer, Path(tmp))
                self.assertEqual(result['ok'], success)
                if success:
                    self.assertEqual(len(result['images']), 1)
                    self.assertTrue(Path(result['images'][0]).is_file())

    def test_render_cannot_open_ui_by_default(self):
        editor = Mock()
        with self.assertRaises(RuntimeError):
            render.render_range(editor, '/Game/T/LS', Path('.'), 0, 1, (32, 24), 1)
        editor.python.assert_not_called()


class EvidenceTests(unittest.TestCase):
    def test_manual_focus_value_does_not_pass_when_tracking_is_active(self):
        planned = {'Cam': {'binding': 'A', 'keys': [{'frame': 0, 'focus': 100}]}}
        samples = {0: {'bindings': {'A': {'camera': {'ManualFocusDistance': 100, 'FocusMethod': 'TRACKING'}}}}}
        self.assertFalse(check_keys(samples, planned)[0]['ok'])
        samples[0]['bindings']['A']['camera']['FocusMethod'] = 'MANUAL'
        self.assertTrue(check_keys(samples, planned)[0]['ok'])
    def test_empty_checks_are_collection_not_pass(self):
        self.assertEqual(verification([]), {'status': 'collected', 'checks_performed': 0, 'passed': None})

    def test_roll_focus_and_aperture_mismatch_fail(self):
        planned = {'Cam': {'binding': 'A', 'keys': [{'frame': 0, 'rotation': [0, 0, 0], 'focus': 100, 'aperture': 2.8}]}}
        samples = {0: {'bindings': {'A': {'transform': {'rotation': {'pitch': 0, 'yaw': 0, 'roll': 90}},
                                        'camera': {'ManualFocusDistance': 200, 'CurrentAperture': 4}}}}}
        row = check_keys(samples, planned)[0]
        self.assertFalse(row['ok'])
        self.assertEqual(set(row['checked']), {'rotation_pitch_yaw_roll', 'focus', 'aperture'})

    def test_occlusion_uses_current_camera_and_moving_target(self):
        editor = Mock()
        editor.find_actor.return_value = {'refPath': 'Hero'}
        editor.actor_bounds.return_value = [[190, -10, -10], [210, 10, 10]]
        editor.call.return_value = None
        cameras = {'Cam': {'binding': 'A', 'keys': [{'frame': 20, 'look_at': 'Hero', 'location': [0, 0, 0], 'aim_point': [100, 0, 0]}]}}
        current = {'bindings': {'A': {'transform': {'location': {'x': 10, 'y': 0, 'z': 0}}}}}
        checks = occlusion_checks(editor, cameras, current, 20)
        self.assertTrue(checks[0]['ok'])
        args = editor.call.call_args.kwargs
        self.assertEqual((args['start']['x'], args['end']['x']), (10, 200))

    def test_sampling_traces_before_session_cleanup(self):
        editor = Mock()
        editor.sequence_state.return_value = {'sequence': None}
        editor.call.return_value = False
        events = []
        session = MagicMock()
        session.__exit__.side_effect = lambda *args: events.append('close') or False
        editor.sequence_session.return_value = session
        with patch('sequence_sample.sample', side_effect=lambda *args: {args[2][0]: {'bindings': {}}}), \
             patch('sequence_sample.occlusion_checks', side_effect=lambda *args: events.append(f'trace{args[-1]}') or []):
            sample_session(editor, '/Game/T/LS', [0, 20], [], {'bindings': []}, {}, allow_editor_ui=True)
        self.assertEqual(events, ['trace0', 'trace20', 'close'])


if __name__ == '__main__':
    unittest.main()
