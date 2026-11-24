"""Execution boundaries and semantics regressions; fake MCP only, no editor writes."""

import copy
import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

import blueprint_geometry as geometry
import blueprint_layout as layout
import blueprint_normalize as normalize
from test_blueprint_layout import EX, THEN, Graph
from ue_mcp.skill_api import ensure_editor_idle


def client_for(handler):
    client = Mock()
    client.call_resolved_tool.side_effect = lambda toolset, tool, args: handler(toolset, tool, args)
    return client


class ExecutionTests(unittest.TestCase):
    def test_normalize_passes_project_to_connection(self):
        with patch('ue_mcp.skill_api.connect') as connect:
            normalize.Editor('/Game/T/BP.BP', 'ExpectedProject')
        connect.assert_called_once_with(project='ExpectedProject')

    def test_layout_passes_project_to_connection(self):
        client = client_for(lambda ts, name, args: [] if name == 'find_nodes' else {'refPath': 'G'})
        with patch('ue_mcp.skill_api.connect', return_value=client) as connect, redirect_stdout(io.StringIO()):
            self.assertEqual(layout.main(['/Game/T/BP', '--graph', 'Fn', '--project', 'ExpectedProject']), 0)
        connect.assert_called_once_with(project='ExpectedProject')
        client.close.assert_called_once()

    def test_missing_or_conflicting_graph_scope_fails_before_connect(self):
        for module in (normalize, layout):
            for extra in ([], ['--all', '--graph', 'Fn']):
                with self.subTest(module=module.__name__, extra=extra), patch('ue_mcp.skill_api.connect') as connect:
                    with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                        module.main(['/Game/T/BP', *extra])
                    self.assertEqual(exc.exception.code, 2)
                    connect.assert_not_called()

    def test_writes_require_project(self):
        for module in (normalize, layout):
            with patch.dict(os.environ, {}, clear=True), patch('ue_mcp.skill_api.connect') as connect:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    module.main(['/Game/T/BP', '--graph', 'Fn', '--write'])
                connect.assert_not_called()

    def test_pie_or_unknown_state_refuses_write(self):
        for state in (True, None, {}, 'false'):
            with self.subTest(state=state):
                client = client_for(lambda *args: state)
                with self.assertRaises(RuntimeError):
                    ensure_editor_idle(client)
        ensure_editor_idle(client_for(lambda *args: False))

    def test_layout_pie_refusal_closes_client_before_graph_writes(self):
        client = client_for(lambda *args: True)
        with patch('ue_mcp.skill_api.connect', return_value=client), self.assertRaises(RuntimeError):
            layout.main(['/Game/T/BP', '--all', '--write', '--project', 'ExpectedProject'])
        self.assertEqual([c.args[1] for c in client.call_resolved_tool.call_args_list], ['IsPIERunning'])
        client.close.assert_called_once()

    def test_external_inherited_or_local_getter_is_never_recreated_by_name(self):
        for type_id in ('OtherActor|GetHealth', 'BaseCharacter|GetHealth', 'Local|GetHealth'):
            g = Graph().add('K2Node_VariableGet_0', type_id, inputs=[('self', 'object', '')], outputs=[('Health', 'real')])
            editor = Mock()
            with self.assertRaises(RuntimeError):
                normalize.Editor.copy_node(editor, 'Fn', {}, g.infos()[0])
            editor.bt.assert_not_called()
            editor.getters.assert_not_called()

    def test_normalize_preserves_shared_external_target_and_set_output(self):
        g = Graph().add('K2Node_VariableGet_0', 'Other|GetHealth', inputs=[('self', 'object', '')], outputs=[('Health', 'real')])
        g.add('K2Node_VariableGet_1', 'Game|OtherActor', outputs=[('Actor', 'object')])
        g.link('K2Node_VariableGet_1', 'Actor', 'K2Node_VariableGet_0', 'self')
        g.add('K2Node_CallFunction_0', 'Game|A', inputs=[EX, ('Value', 'real', '0')], outputs=[THEN])
        g.add('K2Node_CallFunction_1', 'Game|B', inputs=[EX, ('Value', 'real', '0')], outputs=[THEN])
        g.link('K2Node_VariableGet_0', 'Health', 'K2Node_CallFunction_0', 'Value')
        g.link('K2Node_VariableGet_0', 'Health', 'K2Node_CallFunction_1', 'Value')
        before = copy.deepcopy(g.infos())
        editor = Mock(asset='/Game/T/BP.BP', client=client_for(lambda *args: False))
        editor.infos.return_value = g.infos()
        result = normalize.normalize_graph(editor, 'Fn', True)
        self.assertEqual(result['pure_copies'], 0)
        self.assertTrue(result['skipped'])
        editor.copy_node.assert_not_called()
        editor.rewire.assert_not_called()
        self.assertEqual(g.infos(), before)

    def test_failed_clone_input_readback_removes_only_the_new_node(self):
        original = Graph().add('K2Node_CallFunction_0', 'Game|Pure', inputs=[('Text', 'string', 'kept')], outputs=[('Result', 'string')]).infos()[0]
        clone = copy.deepcopy(original)
        clone['node'] = {'refPath': 'G.K2Node_CallFunction_1'}
        clone['input_pins'][0]['value'] = ''
        editor = Mock()
        editor.bt.side_effect = [clone['node'], [clone], None, [clone], True]
        with self.assertRaisesRegex(RuntimeError, 'default was not confirmed'):
            normalize.Editor.copy_node(editor, 'Fn', {}, original)
        self.assertEqual(editor.bt.call_args_list[-1].args[0], 'delete_node')
        self.assertEqual(editor.bt.call_args_list[-1].kwargs['node'], clone['node'])

    def test_rewire_false_success_is_read_back_and_original_restored(self):
        source, target, new = {'node': {'refPath': 'A'}}, {'node': {'refPath': 'B'}}, {'node': {'refPath': 'C'}}
        editor = Mock()
        empty = [{'input_pins': [{'pin_id': target, 'connected_pins': []}]}]
        editor.bt.side_effect = [True, False, empty, empty, True]
        with self.assertRaisesRegex(RuntimeError, 'not confirmed'):
            normalize.Editor.rewire(editor, source, target, new)
        self.assertEqual(editor.bt.call_args_list[-1].kwargs['output_pin'], source)

    def test_rewire_restores_original_only_after_readback_proves_it_missing(self):
        source, target, new = {'node': {'refPath': 'A'}}, {'node': {'refPath': 'B'}}, {'node': {'refPath': 'C'}}
        editor = Mock()
        editor.bt.side_effect = [None, TimeoutError('unknown completion'), [{'input_pins': [
            {'pin_id': target, 'connected_pins': []}]}], None]
        with self.assertRaises(TimeoutError):
            normalize.Editor.rewire(editor, source, target, new)
        self.assertEqual(editor.bt.call_args_list[-1].kwargs['output_pin'], source)

    def test_rewire_timeout_with_applied_connection_does_not_replay(self):
        source, target, new = {'node': {'refPath': 'A'}}, {'node': {'refPath': 'B'}}, {'node': {'refPath': 'C'}}
        editor = Mock()
        editor.bt.side_effect = [None, TimeoutError('unknown completion'), [{'input_pins': [
            {'pin_id': target, 'connected_pins': [new]}]}]]
        normalize.Editor.rewire(editor, source, target, new)
        self.assertEqual(editor.bt.call_count, 3)

    def test_layout_signature_ignores_positions_but_detects_default_and_wire_changes(self):
        original = Graph().add('K2Node_CallFunction_0', 'Game|Fn', inputs=[EX, ('Value', 'real', '0')], outputs=[THEN]).infos()
        changed = copy.deepcopy(original)
        changed[0]['position']['x'] = 900
        self.assertEqual(geometry.logic_signature(original), geometry.logic_signature(changed))
        changed[0]['input_pins'][1]['value'] = '1'
        self.assertNotEqual(geometry.logic_signature(original), geometry.logic_signature(changed))


if __name__ == '__main__':
    unittest.main()
