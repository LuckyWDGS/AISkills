#!/usr/bin/env python3
"""Inspect PCG graph settings, real pins and reciprocal edges through Epic MCP.

This never executes a graph, enables inspection, spawns content, edits or saves.
Output describes returned topology, not evaluated points or generated instances.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from ue_mcp import DEFAULT_PROTOCOL, UnrealMcpClient, default_cache_dir, default_session_dir, unwrap_result
from ue_mcp.skill_api import DEFAULT_MCP_URL


READ_CALLS = {
    ('AssetTools', 'is_dirty'),
    ('PCGToolset', 'GetGraphStructure'),
    ('PCGToolset', 'GetGraphSchema'),
    ('PCGToolset', 'ListNativeNodes'),
    ('PCGToolset', 'GetNativeNodeSchema'),
    ('ObjectTools', 'list_properties'),
    ('ObjectTools', 'get_properties'),
}
COVERAGE = (
    'Settings and returned logical topology only. Actual UPCGPin/UPCGEdge objects '
    'are checked against GetGraphStructure, including override pins. Native '
    'schemas may omit dynamic pins. No point evaluation, instance counts, '
    'annotation frames, UI wire curves or runtime acceptance is performed. '
    'Multiple reads are not an atomic snapshot.'
)


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def graph_paths(value: str) -> tuple[str, str]:
    if not value.startswith('/') or any(c in value for c in (':', '\\', "'", '"')):
        raise ValueError('Use an absolute PCG graph package or object path')
    package, sep, name = value.partition('.')
    if any(p in ('', '.', '..') for p in package.split('/')[1:]):
        raise ValueError('Invalid graph package path')
    if sep and (not name or '/' in name or '.' in name):
        raise ValueError('Invalid graph object path')
    return package, package + '.' + (name if sep else package.rsplit('/', 1)[-1])


def ref_path(value: Any) -> str:
    if not isinstance(value, dict) or not isinstance(value.get('refPath'), str) or not value['refPath']:
        raise ValueError(f'Invalid UObject reference: {value!r}')
    return value['refPath']


class ReadOnlyPCG:
    def __init__(self, client: Any, out: Path):
        self.client, self.out = client, out
        self.partial: dict = {}

    def call(self, group: str, tool: str, **args: Any) -> Any:
        if (group, tool) not in READ_CALLS:
            raise ValueError(f'Not a permitted PCG read: {group}.{tool}')
        row = {'toolset': group, 'tool': tool, 'arguments': args}
        try:
            value = unwrap_result(self.client.call_resolved_tool(group, tool, args))
            row['result'] = value
            return value
        except Exception as exc:
            row['error'] = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            with (self.out / 'calls.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')

    def properties(self, target: dict, names: list[str]) -> dict:
        value = self.call('ObjectTools', 'get_properties', instance=target, properties=names)
        if not isinstance(value, dict) or any(k not in value for k in names):
            raise ValueError(f'Incomplete property response for {ref_path(target)}: {names}')
        return value

    def snapshot(self, graph: dict, *, native_schemas: bool = True) -> dict:
        data: dict = {'graph': graph, 'nodes': [], 'edge_objects': {}}
        self.partial = data
        structure = self.call('PCGToolset', 'GetGraphStructure', graph=graph)
        if not isinstance(structure, dict) or not all(isinstance(structure.get(k), list) for k in ('nodes', 'edges')):
            raise ValueError('PCG graph structure schema changed')
        data['structure'] = structure
        data['schema'] = self.call('PCGToolset', 'GetGraphSchema', graph=graph)
        if not isinstance(data['schema'], dict):
            raise ValueError('PCG graph parameter schema changed')
        fields = self.call('ObjectTools', 'list_properties', instance=graph)
        data['parameter_values'] = self.properties(graph, ['userParameters']) if 'userParameters' in fields else None
        data['parameter_values_covered'] = 'userParameters' in fields
        for node in structure['nodes']:
            target = {'refPath': node['path']}
            node_fields = self.call('ObjectTools', 'list_properties', instance=target)
            if not all(p in node_fields for p in ('inputPins', 'outputPins')):
                raise ValueError(f'Real PCG pins unavailable on {node["path"]}')
            pins = self.properties(target, ['inputPins', 'outputPins'])
            row: dict = {'node': target, 'name': node['name'], 'pins': []}
            data['nodes'].append(row)
            for field, direction in [('inputPins', 'input'), ('outputPins', 'output')]:
                if not isinstance(pins[field], list):
                    raise ValueError(f'{field} is not a list on {node["path"]}')
                for pin in pins[field]:
                    values = self.properties(pin, ['node', 'properties', 'edges'])
                    if not isinstance(values['properties'].get('label'), str) or not isinstance(values['edges'], list):
                        raise ValueError(f'PCG pin schema changed on {ref_path(pin)}')
                    row['pins'].append({'pin': pin, 'direction': direction, **values})
                    for edge in values['edges']:
                        path = ref_path(edge)
                        if path not in data['edge_objects']:
                            # UPCGEdge.InputPin is upstream (an output pin),
                            # OutputPin is downstream (an input pin).
                            edge_fields = self.call('ObjectTools', 'list_properties', instance=edge)
                            if not all(k in edge_fields for k in ('inputPin', 'outputPin')):
                                raise ValueError(f'PCG edge schema changed on {path}')
                            data['edge_objects'][path] = self.properties(edge, ['inputPin', 'outputPin'])
        if native_schemas:
            names = self.call('PCGToolset', 'ListNativeNodes', bCommonOnly=False)
            if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                raise ValueError('PCG native-node catalog schema changed')
            data['native_schemas'], data['native_schema_unavailable'] = {}, []
            for kind in sorted({n['nodeType'] for n in structure['nodes']}):
                if kind in names:
                    data['native_schemas'][kind] = self.call('PCGToolset', 'GetNativeNodeSchema', nodeName=kind)
                else:
                    data['native_schema_unavailable'].append({'type': kind, 'reason': 'Not in live native-node catalog; real pins were read'})
        return data


def analyze_snapshot(data: dict) -> dict:
    """Check endpoints, direction, reciprocal membership and the two edge sets."""
    diagnostics: list[dict] = []

    def issue(code: str, **detail: Any) -> None:
        diagnostics.append({'code': code, **detail})

    by_path, by_name = {}, {}
    for node in data['structure']['nodes']:
        if node['path'] in by_path or node['name'] in by_name:
            issue('duplicate_node', node=node['path'], name=node['name'])
        by_path[node['path']], by_name[node['name']] = node, node
    pins, observed = {}, {}
    read_nodes = [ref_path(n['node']) for n in data['nodes']]
    if len(read_nodes) != len(set(read_nodes)) or set(read_nodes) != set(by_path):
        issue('node_readback_mismatch', returned=sorted(by_path), read=sorted(read_nodes))
    labels = set()
    for node in data['nodes']:
        owner = ref_path(node['node'])
        for pin in node['pins']:
            path = ref_path(pin['pin'])
            if path in pins:
                issue('duplicate_pin', pin=path)
            pins[path] = {**pin, 'owner': owner}
            if ref_path(pin['node']) != owner:
                issue('pin_owner_mismatch', pin=path, expected=owner, actual=ref_path(pin['node']))
            key = (owner, pin['direction'], pin['properties']['label'])
            if key in labels:
                issue('duplicate_pin_label', pin=path, key=key)
            labels.add(key)
            seen = set()
            for edge in pin['edges']:
                edge_path = ref_path(edge)
                if edge_path in seen:
                    issue('duplicate_edge_membership', edge=edge_path, pin=path)
                seen.add(edge_path)
                observed.setdefault(edge_path, set()).add(path)

    actual, rows = set(), []
    for path in sorted(set(data['edge_objects']) | set(observed)):
        edge = data['edge_objects'].get(path)
        if edge is None:
            issue('missing_edge_object', edge=path)
            continue
        source, target = ref_path(edge['inputPin']), ref_path(edge['outputPin'])
        if observed.get(path, set()) != {source, target}:
            issue('edge_membership_mismatch', edge=path, expected=[source, target], observed=sorted(observed.get(path, set())))
        if source not in pins or target not in pins:
            issue('missing_pin_endpoint', edge=path, source=source, target=target)
            continue
        a, b = pins[source], pins[target]
        if a['direction'] != 'output' or b['direction'] != 'input':
            issue('edge_direction_mismatch', edge=path, source=source, target=target)
        if a['owner'] not in by_path or b['owner'] not in by_path:
            issue('missing_node_endpoint', edge=path)
            continue
        key = (by_path[a['owner']]['name'], a['properties']['label'], by_path[b['owner']]['name'], b['properties']['label'])
        if key in actual:
            issue('duplicate_logical_edge', edge=path, endpoints=key)
        actual.add(key)
        rows.append({'edge': path, 'source_pin': source, 'target_pin': target, 'endpoints': key})
    advertised = []
    for edge in data['structure']['edges']:
        key = tuple(edge[k] for k in ('srcNode', 'srcPin', 'destNode', 'destPin'))
        advertised.append(key)
        if key[0] not in by_name or key[2] not in by_name:
            issue('structure_missing_node', endpoints=key)
    if len(advertised) != len(set(advertised)):
        issue('duplicate_structure_edge')
    if set(advertised) != actual:
        issue('structure_edge_set_mismatch', only_structure=sorted(set(advertised)-actual), only_pin_objects=sorted(actual-set(advertised)))
    return {'valid_returned_topology': not diagnostics, 'diagnostics': diagnostics, 'edges': rows,
            'counts': {'nodes':len(by_path), 'pins':len(pins), 'edges':len(rows)}}


def snapshot_fingerprint(data: dict) -> str:
    # Graph node order is incidental; ordered setting arrays remain ordered.
    structure = dict(data['structure'])
    structure['nodes'] = sorted(structure['nodes'], key=lambda n:n['path'])
    structure['edges'] = sorted(structure['edges'], key=lambda e:json.dumps(e, sort_keys=True))
    nodes = []
    for node in data['nodes']:
        pins = [{**p, 'edges':sorted(p['edges'], key=ref_path)} for p in node['pins']]
        nodes.append({**node, 'pins':sorted(pins, key=lambda p:ref_path(p['pin']))})
    nodes.sort(key=lambda n:ref_path(n['node']))
    schema = dict(data['schema'])
    if isinstance(schema.get('graphParamsSchema'), str):
        # GetGraphSchema leaves this string empty when there is no parameter bag.
        schema['graphParamsSchema'] = json.loads(schema['graphParamsSchema']) if schema['graphParamsSchema'].strip() else {}
    return json.dumps({'structure':structure, 'nodes':nodes, 'schema':schema,
                       'parameters':data['parameter_values'], 'edges':data['edge_objects']}, sort_keys=True, ensure_ascii=False)


def capture(client: Any, graph: str, out: Path, *, verify_snapshot: bool = False) -> int:
    package, obj = graph_paths(graph)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError('Output directory must be new or empty; previous evidence is preserved')
    out.mkdir(parents=True, exist_ok=True)
    reader, analysis = ReadOnlyPCG(client, out), None
    report: dict = {'graph':obj, 'passed':False, 'coverage':COVERAGE,
                    'started_at_utc':datetime.now(timezone.utc).isoformat()}
    try:
        client.open()
        schemas = {g:client.describe_toolset(g) for g in ('PCGToolset','ObjectTools','AssetTools')}
        save_json(out/'tool-schemas.json', schemas)
        report['dirty_before'] = reader.call('AssetTools','is_dirty',asset_path=package)
        if type(report['dirty_before']) is not bool:
            raise ValueError('Unknown graph dirty state')
        snapshot = reader.snapshot({'refPath':obj})
        save_json(out/'snapshot.json', snapshot)
        analysis = analyze_snapshot(snapshot)
        save_json(out/'connections.json', analysis)
        if verify_snapshot:
            again = reader.snapshot({'refPath':obj}, native_schemas=False)
            save_json(out/'snapshot-verification.json', again)
            report['snapshot_unchanged'] = snapshot_fingerprint(snapshot) == snapshot_fingerprint(again)
        report['dirty_after'] = reader.call('AssetTools','is_dirty',asset_path=package)
        if type(report['dirty_after']) is not bool:
            raise ValueError('Unknown graph dirty state after capture')
        failures = []
        if not analysis['valid_returned_topology']:
            failures.append('Returned topology has diagnostics; inspect connections.json')
        if report.get('snapshot_unchanged') is False:
            failures.append('Graph changed between snapshots; no edits were made')
        if report['dirty_before'] != report['dirty_after']:
            failures.append('Graph dirty flag changed; it was not saved or cleared')
        report['passed'] = not failures
        if failures:
            report['error'] = '; '.join(failures)
    except Exception as exc:
        save_json(out/'snapshot-partial.json', reader.partial)
        report['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        client.close()
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        if analysis:
            report['counts'] = analysis['counts']
        save_json(out/'result.json', report)
        lines = ['# PCG 官方 MCP 只读检查', '', f'图：`{obj}`', '', f'结构检查通过：**{report["passed"]}**', '', COVERAGE, '',
                 f'检查前后 dirty：{report.get("dirty_before")} / {report.get("dirty_after")}', '',
                 f'数量：`{json.dumps(report.get("counts", {}))}`', '',
                 'snapshot.json 包含图参数、节点设置、真实引脚和原生 schema；connections.json 包含双端边校验。', '',
                 '本报告不代表 PCG 输出或游戏运行时验收。', '']
        if report.get('error'):
            lines += [f'失败：{report["error"]}', '']
        (out/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    return 0 if report['passed'] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', help='Absolute PCGGraph package or object path')
    parser.add_argument('--out', type=Path, required=True, help='New or empty local output directory')
    parser.add_argument('--project', default=os.environ.get('UE_MCP_PROJECT'), help='Expected editor .uproject or name')
    parser.add_argument('--url', default=DEFAULT_MCP_URL)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--verify-snapshot', action='store_true', help='Reread pins, links, settings and parameters to detect changes')
    args = parser.parse_args()
    try:
        graph_paths(args.graph)
    except ValueError as exc:
        parser.error(str(exc))
    if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
        parser.error('Output directory must be new or empty')
    client = UnrealMcpClient(args.url, DEFAULT_PROTOCOL, args.timeout, expected_project=args.project,
                             cache_dir=default_cache_dir(), session_dir=default_session_dir())
    code = capture(client, args.graph, args.out, verify_snapshot=args.verify_snapshot)
    print(json.dumps({'exit_code':code, 'report':str(args.out.resolve()/'report.md')}, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
