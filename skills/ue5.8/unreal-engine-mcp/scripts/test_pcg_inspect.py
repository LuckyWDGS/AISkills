"""PCG topology and read-only boundary regressions; no Unreal editor needed."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from pcg_inspect import READ_CALLS, ReadOnlyPCG, analyze_snapshot, capture, graph_paths, snapshot_fingerprint


GRAPH = '/Game/Test/PCG_Test.PCG_Test'


def ref(path):
    return {'refPath':path}


def fixture():
    nodes = []
    for name, kind, pins in [('A','Sampler',[('Out','output')]),
                             ('B','Spawner',[('In','input'),('PointsPerSquaredMeter','input')]),
                             ('DefaultInputNode','Input',[('In','output')])]:
        path = GRAPH + ':' + name
        nodes.append({'node':ref(path), 'name':name, 'pins':[
            {'pin':ref(path+'.Pin_'+str(i)), 'direction':direction, 'node':ref(path),
             'properties':{'label':label,'pinStatus':'OverrideOrUserParam' if label=='PointsPerSquaredMeter' else 'Normal'},
             'edges':[]} for i,(label,direction) in enumerate(pins)]})
    data = {'graph':ref(GRAPH), 'structure':{'name':'PCG_Test','description':'中文说明',
            'nodes':[{'path':n['node']['refPath'],'name':n['name'],'nodeType':kind,
                      'paramOverrides':{'ordered':['first','second']}} for n,kind in zip(nodes,['Sampler','Spawner','Input'])],
            'edges':[]}, 'nodes':nodes, 'edge_objects':{},
            'schema':{'graphParamsSchema':'{"density":{"type":"number"}}'},
            'parameter_values':{'userParameters':{'density':.18}}, 'parameter_values_covered':True}
    add_edge(data,nodes[0]['pins'][0],nodes[1]['pins'][0])
    add_edge(data,nodes[0]['pins'][0],nodes[1]['pins'][1])
    return data


def add_edge(data, source, target):
    name = GRAPH + ':Edge_' + str(len(data['edge_objects']))
    source['edges'].append(ref(name))
    target['edges'].append(ref(name))
    data['edge_objects'][name] = {'inputPin':source['pin'], 'outputPin':target['pin']}
    lookup = {n['path']:n['name'] for n in data['structure']['nodes']}
    data['structure']['edges'].append({'srcNode':lookup[source['node']['refPath']], 'srcPin':source['properties']['label'],
                                      'destNode':lookup[target['node']['refPath']], 'destPin':target['properties']['label']})


class TopologyTests(unittest.TestCase):
    def test_dynamic_override_pin_and_fanout_use_real_pins(self):
        data = fixture()
        original = copy.deepcopy(data)
        result = analyze_snapshot(data)
        self.assertTrue(result['valid_returned_topology'])
        self.assertEqual(result['counts'],{'nodes':3,'pins':4,'edges':2})
        self.assertEqual(result['edges'][1]['endpoints'][3],'PointsPerSquaredMeter')
        self.assertEqual(data,original)

    def test_upstream_input_pin_naming_is_not_graph_input_direction(self):
        data = fixture()
        edge = next(iter(data['edge_objects'].values()))
        edge['inputPin'],edge['outputPin'] = edge['outputPin'],edge['inputPin']
        codes = {i['code'] for i in analyze_snapshot(data)['diagnostics']}
        self.assertIn('edge_direction_mismatch',codes)
        self.assertIn('structure_edge_set_mismatch',codes)

    def test_missing_membership_and_endpoint_are_reported(self):
        data = fixture()
        data['nodes'][1]['pins'][0]['edges'].clear()
        data['nodes'][1]['pins'].pop()
        codes = {i['code'] for i in analyze_snapshot(data)['diagnostics']}
        self.assertIn('edge_membership_mismatch',codes)
        self.assertIn('missing_pin_endpoint',codes)
        self.assertIn('structure_edge_set_mismatch',codes)

    def test_owner_mismatch_duplicate_node_pin_and_membership(self):
        data = fixture()
        data['structure']['nodes'].append(copy.deepcopy(data['structure']['nodes'][0]))
        pin = data['nodes'][0]['pins'][0]
        pin['node'] = ref(GRAPH+':B')
        pin['edges'].append(copy.deepcopy(pin['edges'][0]))
        data['nodes'][0]['pins'].append(copy.deepcopy(pin))
        codes = {i['code'] for i in analyze_snapshot(data)['diagnostics']}
        self.assertTrue({'duplicate_node','duplicate_pin','duplicate_pin_label','pin_owner_mismatch','duplicate_edge_membership'} <= codes)

    def test_unread_node_and_extra_advertised_edge_fail(self):
        data = fixture()
        data['nodes'].pop()
        data['structure']['edges'].append({'srcNode':'missing','srcPin':'Out','destNode':'B','destPin':'In'})
        codes = {i['code'] for i in analyze_snapshot(data)['diagnostics']}
        self.assertIn('node_readback_mismatch',codes)
        self.assertIn('structure_missing_node',codes)

    def test_fingerprint_ignores_node_pin_order_but_preserves_setting_array_order(self):
        data = fixture()
        other = copy.deepcopy(data)
        other['structure']['nodes'].reverse()
        other['structure']['edges'].reverse()
        other['nodes'].reverse()
        for node in other['nodes']:
            node['pins'].reverse()
            for pin in node['pins']:
                pin['edges'].reverse()
        self.assertEqual(snapshot_fingerprint(data),snapshot_fingerprint(other))
        other['structure']['nodes'][0]['paramOverrides']['ordered'].reverse()
        self.assertNotEqual(snapshot_fingerprint(data),snapshot_fingerprint(other))


class FakeClient:
    def __init__(self, *, dirty=True, change=False, flip_dirty=False, fail=False):
        self.data = fixture()
        self.calls = []
        self.dirty, self.change, self.flip_dirty, self.fail = dirty, change, flip_dirty, fail
        self.structure_reads, self.dirty_reads = 0, 0
        self.closed = False

    def open(self):
        return self

    def close(self):
        self.closed = True

    def describe_toolset(self, group):
        return {'name':group,'tools':[]}

    def call_resolved_tool(self, group, tool, args):
        self.calls.append((group,tool,args))
        if (group,tool) not in READ_CALLS:
            raise AssertionError('Unexpected editor call')
        if tool == 'is_dirty':
            self.dirty_reads += 1
            return not self.dirty if self.flip_dirty and self.dirty_reads > 1 else self.dirty
        if tool == 'GetGraphStructure':
            self.structure_reads += 1
            value = copy.deepcopy(self.data['structure'])
            if self.change and self.structure_reads > 1:
                value['nodes'][0]['paramOverrides']['density'] = .5
            return value
        if tool == 'GetGraphSchema':
            return copy.deepcopy(self.data['schema'])
        if tool == 'ListNativeNodes':
            return ['Sampler','Spawner']
        if tool == 'GetNativeNodeSchema':
            if self.fail:
                raise RuntimeError('Native schema failed after pins were read')
            # Basic schema intentionally omits the live override pin.
            return {'inputPins':[{'name':'In'}], 'outputPins':[{'name':'Out'}]}
        target = args['instance']['refPath']
        if target == GRAPH:
            values = self.data['parameter_values']
        elif target in self.data['edge_objects']:
            values = self.data['edge_objects'][target]
        else:
            values = None
            for node in self.data['nodes']:
                if target == node['node']['refPath']:
                    values = {field:[p['pin'] for p in node['pins'] if p['direction']==direction]
                              for field,direction in [('inputPins','input'),('outputPins','output')]}
                for pin in node['pins']:
                    if target == pin['pin']['refPath']:
                        values = {k:pin[k] for k in ['node','properties','edges']}
            if values is None:
                raise AssertionError('Unknown object '+target)
        value = {k:{} for k in values} if tool == 'list_properties' else {k:copy.deepcopy(values[k]) for k in args['properties']}
        # Mimic the JSON string layer used by official ObjectTools.
        return json.dumps(value)


class CaptureTests(unittest.TestCase):
    def test_capture_is_read_only_and_keeps_existing_dirty_state(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/'new'
            self.assertEqual(capture(client,GRAPH,out,verify_snapshot=True),0)
            result = json.loads((out/'result.json').read_text(encoding='utf-8'))
            self.assertTrue(result['dirty_before'] and result['dirty_after'] and result['snapshot_unchanged'])
            snapshot = json.loads((out/'snapshot.json').read_text(encoding='utf-8'))
            self.assertEqual(snapshot['native_schema_unavailable'][0]['type'],'Input')
            self.assertEqual(len(snapshot['native_schemas']),2)
            self.assertTrue(client.closed)
            self.assertTrue(all((g,t) in READ_CALLS for g,t,a in client.calls))
            self.assertFalse({'GetNodeDataView','ExecuteGraphInstance','RunPCGInstantGraph','save_assets','set_properties'} & {t for g,t,a in client.calls})

    def test_concurrent_change_or_dirty_change_does_not_pass(self):
        for kwargs in [{'change':True},{'flip_dirty':True}]:
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as folder:
                client = FakeClient(**kwargs)
                self.assertEqual(capture(client,GRAPH,Path(folder)/'out',verify_snapshot=True),1)
                self.assertTrue(client.closed)

    def test_graph_without_parameters_accepts_native_empty_schema_string(self):
        client = FakeClient()
        client.data['schema']['graphParamsSchema'] = ''
        client.data['parameter_values'] = {'userParameters':{}}
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(capture(client,GRAPH,Path(folder)/'out',verify_snapshot=True),0)

    def test_late_error_keeps_partial_snapshot_and_call_error(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/'out'
            client = FakeClient(fail=True)
            self.assertEqual(capture(client,GRAPH,out),1)
            partial = json.loads((out/'snapshot-partial.json').read_text(encoding='utf-8'))
            self.assertEqual(len(partial['edge_objects']),2)
            calls = [json.loads(s) for s in (out/'calls.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertIn('error',calls[-1])
            self.assertTrue(client.closed)

    def test_unknown_dirty_state_is_a_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(capture(FakeClient(dirty=None),GRAPH,Path(folder)/'out'),1)

    def test_nonempty_output_is_preserved_before_contacting_editor(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out/'evidence.txt').write_text('keep',encoding='utf-8')
            client = FakeClient()
            with self.assertRaisesRegex(ValueError,'previous evidence'):
                capture(client,GRAPH,out)
            self.assertEqual(client.calls,[])
            self.assertEqual((out/'evidence.txt').read_text(),'keep')

    def test_read_allowlist_refuses_execution_even_when_tool_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            client = FakeClient()
            reader = ReadOnlyPCG(client,Path(folder))
            for tool in ['GetNodeDataView','ExecuteGraphInstance','DrawSpline']:
                with self.assertRaisesRegex(ValueError,'Not a permitted'):
                    reader.call('PCGToolset',tool)
            self.assertEqual(client.calls,[])

    def test_paths_accept_graph_assets_and_reject_subobjects(self):
        self.assertEqual(graph_paths('/Game/Test/PCG_Test'),('/Game/Test/PCG_Test',GRAPH))
        self.assertEqual(graph_paths(GRAPH),('/Game/Test/PCG_Test',GRAPH))
        for value in ['relative','/Game//PCG_Test','/Game/../PCG_Test',GRAPH+':Node','/Game/PCG_Test.','/']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                graph_paths(value)


if __name__ == '__main__':
    unittest.main()
