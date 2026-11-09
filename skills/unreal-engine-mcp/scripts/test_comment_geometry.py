"""Saved comment bounds must work after reload and never turn missing evidence into a pass."""

import copy
import unittest

import blueprint_lint
from blueprint_comment_geometry import GEOMETRY_SOURCE, contained_nodes, decode_object_export, parse_comment_bounds
from test_blueprint_lint_boundaries import snapshot


PATH = '/Game/T/WBP.WBP:EventGraph.EdGraphNode_Comment_0'
HEADER = f'Begin Object Class=/Script/UnrealEd.EdGraphNode_Comment Name="EdGraphNode_Comment_0" ExportPath="/Script/UnrealEd.EdGraphNode_Comment\'{PATH}\'"'


def exported(*properties):
    return '\n'.join([HEADER, *('   ' + item for item in properties), 'End Object', ''])


class CommentBoundsTests(unittest.TestCase):
    def test_windows_unicode_and_utf8_exports_are_decoded(self):
        text = exported('NodeComment="中文说明"')
        for encoding in ['utf-16', 'utf-8-sig', 'utf-8']:
            with self.subTest(encoding=encoding):
                self.assertEqual(decode_object_export(text.encode(encoding)), text)

    def test_negative_coordinates_and_nondefault_size(self):
        text = exported('NodePosX=-60', 'NodePosY=-120', 'NodeWidth=320', 'NodeHeight=872')
        self.assertEqual(parse_comment_bounds(text, PATH, [320, 872]),
                         {'x': -60, 'y': -120, 'width': 320, 'height': 872})

    def test_native_default_properties_may_be_omitted(self):
        self.assertEqual(parse_comment_bounds(exported(), PATH, [400, 100]),
                         {'x': 0, 'y': 0, 'width': 400, 'height': 100})

    def test_export_identity_must_match(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            parse_comment_bounds(exported(), PATH + '_Other', [400, 100])

    def test_incomplete_nested_and_non_native_exports_are_rejected(self):
        for text in [exported().replace('End Object', ''), exported(HEADER, 'End Object'),
                     exported().replace('/Script/UnrealEd.EdGraphNode_Comment ', '/Script/Other.Comment '), '']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_comment_bounds(text, PATH, [400, 100])

    def test_duplicate_or_malformed_position_never_uses_a_default(self):
        for props in [('NodePosX=abc',), ('NodePosX=1', 'NodePosX=2')]:
            with self.subTest(props=props), self.assertRaises(ValueError):
                parse_comment_bounds(exported(*props), PATH, [400, 100])

    def test_stale_or_invalid_size_is_rejected(self):
        for size in [[400, 99], [0, 100], [float('nan'), 100]]:
            with self.subTest(size=size), self.assertRaises(ValueError):
                parse_comment_bounds(exported('NodeWidth=400', 'NodeHeight=100'), PATH, size)

    def test_full_containment_partial_intersection_and_outside_are_distinct(self):
        enclosed, partial = contained_nodes({'x': -10, 'y': -10, 'width': 110, 'height': 110}, {
            'inside': {'x': 0, 'y': 0, 'width': 40, 'height': 40},
            'on_boundary': {'x': -10, 'y': -10, 'width': 110, 'height': 110},
            'partial': {'x': 90, 'y': 90, 'width': 40, 'height': 40},
            'outside': {'x': 100, 'y': 100, 'width': 40, 'height': 40},
        })
        self.assertEqual(enclosed, ['inside', 'on_boundary'])
        self.assertEqual(partial, ['partial'])

    def test_zero_or_nonfinite_node_size_is_unknown(self):
        with self.assertRaises(ValueError):
            contained_nodes({'x': 0, 'y': 0, 'width': 100, 'height': 100},
                            {'entry': {'x': 0, 'y': 0, 'width': 0, 'height': 10}})


class PersistedCoverageTests(unittest.TestCase):
    def frame(self, *, members=None, partial=None):
        return {'graph': 'EventGraph', 'text': '[UI.Health] 生命值', 'membership_source': GEOMETRY_SOURCE,
                'members': ['K2Node_Event_0'] if members is None else members,
                'partial_members': partial or [], 'bounds': {'x': -10, 'y': -10, 'width': 100, 'height': 100},
                'node_bounds': {'K2Node_Event_0': {'x': 0, 'y': 0, 'width': 20, 'height': 20}}}

    def test_empty_native_cache_can_use_verified_persisted_geometry(self):
        self.assertEqual(blueprint_lint.lint_annotations(snapshot(), [self.frame()], {}), [])

    def test_known_empty_geometry_still_reports_unframed_entry(self):
        findings = blueprint_lint.lint_annotations(snapshot(), [self.frame(members=[])], {})
        self.assertEqual([f['rule'] for f in findings], ['entry_without_frame'])

    def test_partially_intersecting_entry_is_not_claimed_as_enclosed(self):
        findings = blueprint_lint.lint_annotations(snapshot(), [self.frame(members=[], partial=['K2Node_Event_0'])], {})
        self.assertEqual([f['rule'] for f in findings], ['frame_membership_unavailable'])

    def test_changed_graph_or_node_position_refuses_old_coverage(self):
        for changed in ['position', 'new_node']:
            data = copy.deepcopy(snapshot())
            if changed == 'position':
                data['graphs'][0]['nodes'][0]['position']['x'] = 1000
            else:
                new_node = copy.deepcopy(data['graphs'][0]['nodes'][0])
                new_node['node']['refPath'] = new_node['node']['refPath'].replace('_0', '_1')
                data['graphs'][0]['nodes'].append(new_node)
            findings = blueprint_lint.lint_annotations(data, [self.frame()], {})
            self.assertEqual([f['rule'] for f in findings], ['frame_membership_unavailable'])


if __name__ == '__main__':
    unittest.main()
