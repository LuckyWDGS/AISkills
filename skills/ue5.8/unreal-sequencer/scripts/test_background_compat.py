"""Upgrade/missing-API preflight and warning/failure evidence for the compatibility route."""

import io
import json
import sys
import unittest
import warnings
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sequencer_tools.background_compat import AUDITED_ENGINE_VERSIONS, spawnable_script
from sequencer_tools.editor import Editor


class CompatibilityGuardTests(unittest.TestCase):
    def unreal(self, version=AUDITED_ENGINE_VERSIONS[0], available=True):
        binding = SimpleNamespace(is_valid=lambda: True, get_id=lambda: 'D4E250221F2A4D25937FBC9A8AE6D21E')
        api = Mock(return_value=binding)
        return SimpleNamespace(
            SystemLibrary=SimpleNamespace(get_engine_version=lambda: version),
            MovieSceneSequenceExtensions=SimpleNamespace(add_spawnable_from_class=api) if available else None,
            load_asset=Mock(return_value=SimpleNamespace(get_path_name=lambda: '/Game/T/LS.LS')),
            load_class=Mock(return_value=object()),
            GuidLibrary=SimpleNamespace(conv_guid_to_string=lambda guid: guid),
        ), api

    def run_script(self, unreal):
        with patch.dict(sys.modules, unreal=unreal), redirect_stdout(io.StringIO()) as out:
            exec(spawnable_script('/Game/T/LS.LS', '/Script/Engine.CameraActor'), {})
        return json.loads(out.getvalue().split('CODEX_SEQ ', 1)[1])

    def test_other_builds_refuse_before_loading_or_writing(self):
        for version in ['5.8.5-60000000+++UE5+Release-5.8', '5.9.0-1+++UE5+Release-5.9',
                        '5.8.4-1+++UE5+Release-5.8', '5.8.4-58902052+++CustomBranch']:
            unreal, api = self.unreal(version)
            with self.subTest(version=version), self.assertRaisesRegex(RuntimeError, 'No fallback write attempted'):
                self.run_script(unreal)
            unreal.load_asset.assert_not_called()
            unreal.load_class.assert_not_called()
            api.assert_not_called()

    def test_missing_api_refuses_before_asset_load(self):
        unreal, api = self.unreal(available=False)
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            self.run_script(unreal)
        unreal.load_asset.assert_not_called()
        api.assert_not_called()

    def test_known_build_creates_once_and_reports_its_compatibility_debt(self):
        unreal, api = self.unreal()
        result = self.run_script(unreal)
        api.assert_called_once()
        self.assertTrue(result['compatibility']['deprecated'])
        self.assertEqual(result['compatibility']['engine_version'], AUDITED_ENGINE_VERSIONS[0])
        self.assertEqual(result['binding']['sequence'], {'refPath': '/Game/T/LS.LS'})

    def test_native_deprecation_warning_is_not_filtered(self):
        unreal, api = self.unreal()
        binding = api.return_value
        def deprecated(*args):
            warnings.warn('native deprecation', DeprecationWarning)
            return binding
        api.side_effect = deprecated
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter('always', DeprecationWarning)
            self.run_script(unreal)
        self.assertEqual([str(w.message) for w in seen], ['native deprecation'])

    def test_unresolved_class_never_calls_create(self):
        unreal, api = self.unreal()
        unreal.load_class.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'does not resolve'):
            self.run_script(unreal)
        api.assert_not_called()


class RemoteEvidenceTests(unittest.TestCase):
    def editor(self):
        e = Editor.__new__(Editor)
        e.project = 'ExpectedProject'
        e.calls = []
        return e

    def test_success_keeps_native_warnings_and_live_build_in_call_evidence(self):
        payload = {'success': True, 'node': {'engine_version': AUDITED_ENGINE_VERSIONS[0]},
                   'output': [{'type': 'Warning', 'output': 'DeprecationWarning: native API'},
                              {'type': 'Info', 'output': 'CODEX_SEQ {"bindingId":"value"}'}]}
        e = self.editor()
        with patch('sequencer_tools.editor.run_python', return_value=payload) as run:
            self.assertEqual(e.python('script', gap='known gap'), {'bindingId': 'value'})
        run.assert_called_once_with('script', project='ExpectedProject')
        self.assertEqual(e.calls[0]['warnings'], ['DeprecationWarning: native API'])
        self.assertEqual(e.calls[0]['engine_version'], AUDITED_ENGINE_VERSIONS[0])

    def test_print_before_failure_cannot_establish_success(self):
        payload = {'success': False, 'output': [{'type': 'Info', 'output': 'CODEX_SEQ {"ok":true}'},
                                               {'type': 'Error', 'output': 'failure after marker'}]}
        e = self.editor()
        with patch('sequencer_tools.editor.run_python', return_value=payload), self.assertRaisesRegex(RuntimeError, 'failure after marker'):
            e.python('script', gap='known gap')
        self.assertFalse(e.calls[0]['success'])
        self.assertEqual(e.calls[0]['errors'], ['failure after marker'])

    def test_missing_success_or_reported_error_is_not_a_pass(self):
        for payload in [{'output': [{'type': 'Info', 'output': 'CODEX_SEQ {}'}]},
                        {'success': True, 'output': [{'type': 'Error', 'output': 'native error'},
                                                   {'type': 'Info', 'output': 'CODEX_SEQ {}'}]}]:
            e = self.editor()
            with self.subTest(payload=payload), patch('sequencer_tools.editor.run_python', return_value=payload), self.assertRaises(RuntimeError):
                e.python('script', gap='known gap')

    def test_transport_failure_is_recorded_without_retry(self):
        e = self.editor()
        with patch('sequencer_tools.editor.run_python', side_effect=TimeoutError('unknown completion')) as run, self.assertRaises(TimeoutError):
            e.python('script', gap='known gap')
        run.assert_called_once()
        self.assertEqual(e.calls[0]['error'], 'unknown completion')

    def test_duplicate_markers_do_not_select_the_first_binding(self):
        payload = {'success': True, 'output': [{'type': 'Info', 'output': 'CODEX_SEQ {}\nCODEX_SEQ {}'}]}
        e = self.editor()
        with patch('sequencer_tools.editor.run_python', return_value=payload), self.assertRaises(RuntimeError):
            e.python('script', gap='known gap')
        self.assertIn('error', e.calls[0])
        self.assertNotIn('result', e.calls[0])


if __name__ == '__main__':
    unittest.main()
