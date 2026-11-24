"""False success, mismatched evidence and annotation coverage regressions."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import blueprint_layout as layout
import blueprint_lint as lint
from blueprint_comment_geometry import GEOMETRY_SOURCE
from test_blueprint_lint_boundaries import snapshot


class RemoteReadTests(unittest.TestCase):
    def process(self, marker, value, *, success=True, code=0, extra=()):
        payload = {'success': success, 'output': [
            {'type': 'Info', 'output': marker + json.dumps(value)}, *extra]}
        return Mock(returncode=code, stdout=json.dumps(payload), stderr='')

    def test_comment_marker_does_not_override_a_failed_command(self):
        for success, code, extra in [(False, 1, []), (None, 0, []), (True, 1, []),
                                     (True, 0, [{'type': 'Error', 'output': 'failure after marker'}])]:
            with self.subTest(success=success, code=code, extra=extra), \
                 patch.object(lint.subprocess, 'run', return_value=self.process('CODEX_COMMENTS ', [], success=success, code=code, extra=extra)), \
                 self.assertRaises(RuntimeError):
                lint.read_comments('/Game/T/WBP', 'ExpectedProject')

    def test_reframe_marker_does_not_override_a_failed_write(self):
        with patch.object(layout.subprocess, 'run', return_value=self.process('CODEX_REFRAME ', [], success=False, code=1)), \
             self.assertRaises(RuntimeError):
            layout.reframe('/Game/T/WBP', 'EventGraph', {}, 'ExpectedProject')

    def test_null_or_malformed_annotations_cannot_disable_the_check(self):
        for value in [None, {}, [{'graph': 'EventGraph', 'text': '中文', 'members': None}]]:
            with self.subTest(value=value), patch.object(lint.subprocess, 'run', return_value=self.process('CODEX_COMMENTS ', value)), \
                 self.assertRaises(RuntimeError):
                lint.read_comments('/Game/T/WBP', 'ExpectedProject')

    def test_valid_empty_annotation_result_is_still_accepted(self):
        with patch.object(lint.subprocess, 'run', return_value=self.process('CODEX_COMMENTS ', [])):
            self.assertEqual(lint.read_comments('/Game/T/WBP', 'ExpectedProject'), [])


class ReusedCaptureTests(unittest.TestCase):
    def run_cli(self, folder, target='/Game/T/WBP', *, passed=True, data=None, with_result=True):
        capture = Path(folder) / 'capture'
        capture.mkdir()
        (capture / 'snapshot.json').write_text(json.dumps(data or snapshot()), encoding='utf-8')
        if with_result:
            (capture / 'result.json').write_text(json.dumps({'blueprint': '/Game/T/WBP.WBP', 'passed': passed,
                                                             'error': 'incomplete capture' if not passed else None}), encoding='utf-8')
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return lint.main([target, '--inspect-dir', str(capture), '--out', str(Path(folder) / 'out'), '--no-comments', '--strict'])

    def test_another_assets_snapshot_is_refused_before_live_reads(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(lint, 'read_comments') as read:
            self.assertEqual(self.run_cli(folder, '/Game/T/Other'), 2)
        read.assert_not_called()

    def test_failed_or_unproven_capture_is_not_reused_as_a_pass(self):
        for options in [{'passed': False}, {'with_result': False}]:
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                self.assertEqual(self.run_cli(folder, **options), 2)

    def test_matching_successful_capture_can_be_reviewed_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.run_cli(folder), 0)

    def test_missing_queried_node_cannot_produce_a_clean_lint(self):
        data = snapshot()
        graph = data['graphs'][0]
        graph['node_refs'] = [graph['nodes'][0]['node'], {'refPath': '/Game/T/WBP.WBP:EventGraph.K2Node_Event_1'}]
        report = lint.lint(data)
        self.assertFalse(report['passed'])
        self.assertTrue(any(item.get('diagnostics') for item in report['findings']))


class FunctionCoverageTests(unittest.TestCase):
    def data(self):
        data = copy.deepcopy(snapshot())
        graph = data['graphs'][0]
        graph['graph']['refPath'] = '/Game/T/WBP.WBP:Initialize'
        graph['nodes'][0]['node']['refPath'] = '/Game/T/WBP.WBP:Initialize.K2Node_FunctionEntry_0'
        return data

    def frame(self, *, members, source='native_cache'):
        return {'graph': 'Initialize', 'text': '[UI.Initialize] 初始化界面', 'members': members,
                'membership_source': source,
                'bounds': {'x': 1000, 'y': 1000, 'width': 100, 'height': 100},
                'node_bounds': {'K2Node_FunctionEntry_0': {'x': 0, 'y': 0, 'width': 100, 'height': 50}}}

    def test_function_empty_native_cache_still_requires_coverage_evidence(self):
        findings = lint.lint_annotations(self.data(), [self.frame(members=[])], {})
        self.assertTrue(any(item['rule'] == 'frame_membership_unavailable' for item in findings))

    def test_unrelated_chinese_frame_does_not_cover_the_function_entry(self):
        findings = lint.lint_annotations(self.data(), [self.frame(members=[], source=GEOMETRY_SOURCE)], {})
        self.assertTrue(any(item['rule'] == 'function_without_description' for item in findings))

    def test_enclosed_function_entry_passes(self):
        self.assertEqual(lint.lint_annotations(self.data(), [self.frame(members=['K2Node_FunctionEntry_0'])], {}), [])


if __name__ == '__main__':
    unittest.main()
