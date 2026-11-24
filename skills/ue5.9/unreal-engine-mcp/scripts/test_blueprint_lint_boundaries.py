"""Lint coverage and target identity; no live UE connection."""

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import blueprint_lint as lint


def snapshot():
    return {
        'blueprint': {'refPath': '/Game/T/WBP.WBP'},
        'variables': ['Health'],
        'graphs': [{
            'graph': {'refPath': '/Game/T/WBP.WBP:EventGraph'},
            'nodes': [{
                'node': {'refPath': '/Game/T/WBP.WBP:EventGraph.K2Node_Event_0'},
                'type_id': 'Event|Construct', 'position': {'x': 0, 'y': 0},
                'input_pins': [], 'output_pins': [],
            }],
        }],
    }


class AnnotationCoverageTests(unittest.TestCase):
    def test_empty_native_member_cache_reports_unknown_without_claiming_absence(self):
        findings = lint.lint_annotations(snapshot(), [{'graph': 'EventGraph', 'text': '[UI.Health] 生命值', 'members': []}], {})
        self.assertEqual([f['rule'] for f in findings], ['frame_membership_unavailable'])
        self.assertEqual(findings[0]['nodes'], ['K2Node_Event_0'])
        self.assertEqual(findings[0]['severity'], 'warning')

    def test_no_frame_remains_a_confirmed_missing_annotation(self):
        findings = lint.lint_annotations(snapshot(), [], {})
        self.assertEqual([f['rule'] for f in findings], ['entry_without_frame'])

    def test_explicit_native_membership_satisfies_entry_coverage(self):
        frames = [{'graph': 'EventGraph', 'text': '[UI.Health] 生命值', 'members': ['K2Node_Event_0']}]
        self.assertEqual(lint.lint_annotations(snapshot(), frames, {}), [])


class ProjectIdentityTests(unittest.TestCase):
    def test_cli_endpoint_precedence_explicit_then_environment_then_inspector_default(self):
        for env_url, explicit, expected in (
                (None, None, None),
                ('http://127.0.0.1:8001/mcp', None, 'http://127.0.0.1:8001/mcp'),
                ('http://127.0.0.1:8001/mcp', 'http://127.0.0.1:8002/mcp', 'http://127.0.0.1:8002/mcp')):
            with self.subTest(env_url=env_url, explicit=explicit), tempfile.TemporaryDirectory() as folder:
                environment = {'UNREAL_MCP_URL': env_url} if env_url else {}
                out = Path(folder)
                inspect = out/'inspect'
                inspect.mkdir()
                (inspect/'snapshot.json').write_text(json.dumps(snapshot()), encoding='utf-8')
                command = ['/Game/T/WBP', '--out', str(out)]
                if explicit:
                    command += ['--url', explicit]
                with patch.dict(os.environ, environment, clear=True), \
                     patch.object(lint.subprocess, 'run', return_value=Mock(returncode=0)) as run, \
                     patch.object(lint, 'read_comments', return_value=[]), \
                     patch.object(lint, 'read_categories', return_value={}) as categories, \
                     redirect_stdout(io.StringIO()):
                    self.assertEqual(lint.main(command), 0)
                child = run.call_args.args[0]
                if expected is None:
                    self.assertNotIn('--url', child)  # inspector's CLI defaults to port 8000 without env.
                    self.assertNotIn('url', categories.call_args.kwargs)
                else:
                    self.assertEqual(child[child.index('--url')+1], expected)
                    self.assertEqual(categories.call_args.kwargs['url'], expected)

    def test_category_read_uses_selected_project_and_closes(self):
        client = Mock()
        client.call_resolved_tool.return_value = '界面|生命值'
        with patch('ue_mcp.skill_api.connect', return_value=client) as connect:
            self.assertEqual(lint.read_categories('/Game/T/WBP', ['Health'], 'ExpectedProject'), {'Health': '界面|生命值'})
        connect.assert_called_once_with(project='ExpectedProject')
        client.close.assert_called_once()

    def test_category_read_propagates_explicit_endpoint(self):
        client = Mock()
        client.call_resolved_tool.return_value = '界面|生命值'
        with patch('ue_mcp.skill_api.connect', return_value=client) as connect:
            lint.read_categories('/Game/T/WBP', ['Health'], 'ExpectedProject', url='http://127.0.0.1:8001/mcp')
        connect.assert_called_once_with(project='ExpectedProject', url='http://127.0.0.1:8001/mcp')

    def test_cli_propagates_project_to_all_three_read_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            inspect = out/'inspect'
            inspect.mkdir()
            (inspect/'snapshot.json').write_text(json.dumps(snapshot()), encoding='utf-8')
            with patch.object(lint.subprocess, 'run', return_value=Mock(returncode=0)) as run, \
                 patch.object(lint, 'read_comments', return_value=[]) as comments, \
                 patch.object(lint, 'read_categories', return_value={}) as categories, \
                 patch.object(lint, 'lint', return_value={'passed': True, 'summary': {'warning': 0, 'info': 0}, 'findings': [], 'checked': {}, 'blueprint': 'WBP'}), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(lint.main(['/Game/T/WBP', '--out', str(out), '--project', 'ExpectedProject']), 0)
            command = run.call_args.args[0]
            self.assertEqual(command[command.index('--expect-project')+1], 'ExpectedProject')
            comments.assert_called_once_with('/Game/T/WBP', 'ExpectedProject')
            categories.assert_called_once_with('/Game/T/WBP', ['Health'], 'ExpectedProject')

    def test_cli_propagates_explicit_endpoint_to_inspection_and_categories(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            inspect = out/'inspect'
            inspect.mkdir()
            (inspect/'snapshot.json').write_text(json.dumps(snapshot()), encoding='utf-8')
            with patch.object(lint.subprocess, 'run', return_value=Mock(returncode=0)) as run, \
                 patch.object(lint, 'read_comments', return_value=[]), \
                 patch.object(lint, 'read_categories', return_value={}) as categories, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(lint.main(['/Game/T/WBP', '--out', str(out), '--project', 'ExpectedProject',
                                            '--url', 'http://127.0.0.1:8001/mcp']), 0)
            command = run.call_args.args[0]
            self.assertEqual(command[command.index('--url')+1], 'http://127.0.0.1:8001/mcp')
            categories.assert_called_once_with('/Game/T/WBP', ['Health'], 'ExpectedProject', url='http://127.0.0.1:8001/mcp')


class NativeSnapshotTests(unittest.TestCase):
    def native_snapshot(self):
        data = snapshot()
        data.update(source_contract={'blueprint_toolset': 'BlueprintToolset'},
                    annotations=[{'graph': 'EventGraph', 'text': 'UI.Health｜生命值入口',
                                  'members': ['K2Node_Event_0'], 'membership_source': 'native_cache'}],
                    categories={'Health': '界面|生命值'})
        return data

    def test_native_inspection_evidence_is_consumed_without_remote_or_fresh_reads(self):
        data = self.native_snapshot()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            inspect = out/'inspect'
            inspect.mkdir()
            (inspect/'snapshot.json').write_text(json.dumps(data), encoding='utf-8')
            (inspect/'result.json').write_text(json.dumps({'passed': True, 'blueprint': '/Game/T/WBP.WBP'}), encoding='utf-8')
            with patch.object(lint.subprocess, 'run') as run, \
                 patch.object(lint, 'read_comments') as comments, \
                 patch.object(lint, 'read_categories') as categories, redirect_stdout(io.StringIO()):
                self.assertEqual(lint.main(['/Game/T/WBP', '--out', str(out), '--inspect-dir', str(inspect), '--strict']), 0)
            run.assert_not_called()
            comments.assert_not_called()
            categories.assert_not_called()
            report = json.loads((out/'lint.json').read_text(encoding='utf-8'))
            self.assertTrue(report['checked']['annotations'])
            self.assertTrue(report['passed'])
            self.assertEqual(json.loads((out/'annotations.json').read_text(encoding='utf-8')), data['annotations'])

    def test_missing_native_category_evidence_fails_without_fallback(self):
        data = self.native_snapshot()
        data['categories'] = {}
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            inspect = out/'inspect'
            inspect.mkdir()
            (inspect/'snapshot.json').write_text(json.dumps(data), encoding='utf-8')
            (inspect/'result.json').write_text(json.dumps({'passed': True, 'blueprint': '/Game/T/WBP.WBP'}), encoding='utf-8')
            errors = io.StringIO()
            with patch.object(lint, 'read_comments') as comments, \
                 patch.object(lint, 'read_categories') as categories, redirect_stderr(errors):
                self.assertEqual(lint.main(['/Game/T/WBP', '--out', str(out), '--inspect-dir', str(inspect)]), 2)
            self.assertIn('complete variable category evidence', errors.getvalue())
            comments.assert_not_called()
            categories.assert_not_called()

    def test_native_empty_comment_membership_retains_warning(self):
        data = self.native_snapshot()
        data['annotations'][0]['members'] = []
        data['annotations'][0]['membership_source'] = 'unavailable'
        original = copy.deepcopy(data)
        comments, categories = lint.captured_annotations(data)
        report = lint.lint(data, comments=comments, categories=categories)
        self.assertEqual(data, original)
        self.assertIn('frame_membership_unavailable', [item['rule'] for item in report['findings']])
        self.assertFalse(report['passed'])


if __name__ == '__main__':
    unittest.main()
