"""Lint coverage and target identity; no live UE connection."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
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
    def test_category_read_uses_selected_project_and_closes(self):
        client = Mock()
        client.call_resolved_tool.return_value = '界面|生命值'
        with patch('ue_mcp.skill_api.connect', return_value=client) as connect:
            self.assertEqual(lint.read_categories('/Game/T/WBP', ['Health'], 'ExpectedProject'), {'Health': '界面|生命值'})
        connect.assert_called_once_with(project='ExpectedProject')
        client.close.assert_called_once()

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


if __name__ == '__main__':
    unittest.main()
