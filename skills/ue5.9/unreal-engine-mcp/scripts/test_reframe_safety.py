"""Comment replacement must preserve the original on ambiguity or candidate failure."""

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from blueprint_layout import REFRAME_SCRIPT


class Node:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class Frame(Node):
    def __init__(self, name, text, members):
        super().__init__(name)
        self.text, self.members = text, members
        self.props = {'node_details': '中文详细说明', 'font_size': 18, 'comment_color': 'blue'}
        self.fail_style = False

    def get_editor_property(self, name):
        return self.props[name]

    def set_editor_property(self, name, value):
        if self.fail_style:
            raise RuntimeError('style write failed')
        self.props[name] = value


class GraphEditor:
    def __init__(self, members=()):
        self.nodes = [Node('A'), Node('B')]
        self.original = Frame('Old', '[BP.A] 初始化 [BP.B]', [n for n in self.nodes if n.name in members])
        self.frames = [self.original]
        self.events = []
        self.fail_create = self.fail_style = self.bad_membership = False

    def list_all_nodes(self):
        return self.nodes

    def list_comment_nodes(self):
        return self.frames[:]

    def add_comment_to_nodes(self, text, nodes, padding):
        self.events.append('create')
        if self.fail_create:
            raise RuntimeError('create failed')
        candidate = Frame('New', text, [] if self.bad_membership else nodes)
        candidate.fail_style = self.fail_style
        self.frames.append(candidate)
        return candidate

    def remove_comment_node(self, frame):
        self.events.append('remove_' + frame.name)
        self.frames.remove(frame)


def run(editor, modules=None, frame_map=None):
    unreal = SimpleNamespace(
        BlueprintEditorLibrary=SimpleNamespace(find_graph=lambda *a: object(), get_comment_text=lambda f: f.text,
                                               get_nodes_in_comment=lambda f: f.members),
        BlueprintGraphEditor=SimpleNamespace(get_graph_editor=lambda g: editor),
        EdGraphNode_Comment=Frame, load_asset=lambda path: object(),
    )
    code = (REFRAME_SCRIPT.replace('__ASSET__', repr('/Game/T/BP')).replace('__GRAPH__', repr('EventGraph'))
            .replace('__MODULES__', repr(json.dumps(modules or [['EntryA', ['A']]])))
            .replace('__FRAMEMAP__', repr(json.dumps(frame_map or {}))))
    with patch.dict(sys.modules, unreal=unreal), redirect_stdout(io.StringIO()) as output:
        exec(code, {})
    return json.loads(output.getvalue().split('CODEX_REFRAME ', 1)[1])


class ReframeSafetyTests(unittest.TestCase):
    def test_failed_creation_keeps_the_original_frame(self):
        editor = GraphEditor(['A'])
        editor.fail_create = True
        with self.assertRaisesRegex(RuntimeError, 'create failed'):
            run(editor)
        self.assertEqual(editor.frames, [editor.original])
        self.assertNotIn('remove_Old', editor.events)

    def test_failed_style_removes_only_its_candidate(self):
        editor = GraphEditor(['A'])
        editor.fail_style = True
        with self.assertRaisesRegex(RuntimeError, 'style write failed'):
            run(editor)
        self.assertEqual(editor.frames, [editor.original])
        self.assertNotIn('remove_Old', editor.events)

    def test_unverified_candidate_membership_keeps_the_original(self):
        editor = GraphEditor(['A'])
        editor.bad_membership = True
        with self.assertRaises(RuntimeError):
            run(editor)
        self.assertEqual(editor.frames, [editor.original])

    def test_success_creates_and_verifies_before_removing_original(self):
        editor = GraphEditor(['A'])
        rows = run(editor)
        self.assertEqual(rows[0]['status'], 'reframed')
        self.assertEqual(editor.events, ['create', 'remove_Old'])
        self.assertEqual(len(editor.frames), 1)
        self.assertEqual(editor.frames[0].props, editor.original.props)
        self.assertEqual(editor.frames[0].text, editor.original.text)

    def test_ambiguous_explicit_mapping_never_picks_the_first_module(self):
        editor = GraphEditor()
        rows = run(editor, [['EntryA', ['A']], ['EntryB', ['B']]], {'EntryA': 'BP.A', 'EntryB': 'BP.B'})
        self.assertEqual(rows[0]['status'], 'unmapped')
        self.assertEqual(editor.events, [])

    def test_tied_native_membership_is_left_for_review(self):
        editor = GraphEditor(['A', 'B'])
        rows = run(editor, [['EntryA', ['A']], ['EntryB', ['B']]])
        self.assertEqual(rows[0]['status'], 'unmapped')
        self.assertEqual(editor.events, [])

    def test_missing_planned_member_never_deletes_the_old_frame(self):
        editor = GraphEditor(['A'])
        rows = run(editor, [['EntryA', ['A', 'Missing']]])
        self.assertEqual(rows[0]['status'], 'unmapped')
        self.assertEqual(editor.frames, [editor.original])
        self.assertEqual(editor.events, [])


if __name__ == '__main__':
    unittest.main()
