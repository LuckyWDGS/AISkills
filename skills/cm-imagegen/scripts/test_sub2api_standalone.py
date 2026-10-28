"""Single-provider behavior with no installed controller profile or image skill."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import cm_image_gen as cm


class StandaloneSub2ApiTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(mock.patch.object(cm, 'codex_home', return_value=self.root))
        self.stack.enter_context(mock.patch.dict(os.environ, {}, clear=True))
        self.stack.enter_context(mock.patch.object(cm.urllib.request, 'urlopen', side_effect=AssertionError('Network forbidden')))
        (self.root / 'config.toml').write_text(
            'model_provider = "sub2api"\nmodel = "available-controller"\n'
            '[model_providers.sub2api]\nbase_url = "https://sub2api.example/v1"\n'
            'env_key = "SUB2API_TEST_KEY"\n', encoding='utf-8')
        os.environ['SUB2API_TEST_KEY'] = 'test-only-not-a-real-key'

    def test_copying_only_skill_uses_responses_without_profile(self):
        for command, extra in (('generate', ['--prompt', 'circle']),
                               ('edit', ['--prompt', 'circle', '--image', 'input.png']),
                               ('doctor', []), ('check-config', [])):
            function = 'doctor' if command == 'check-config' else command
            with self.subTest(command=command), mock.patch.object(cm, function, return_value=0) as execute:
                with mock.patch.object(sys, 'argv', ['cm_image_gen.py', command, *extra]):
                    self.assertEqual(cm.main(), 0)
                args = execute.call_args.args[0]
                self.assertEqual(args.api, 'responses')
                self.assertEqual(cm.configured_responses_model(args), 'available-controller')

    def test_doctor_reads_only_primary_connection_and_hides_key(self):
        provider, name = cm.configured_provider()
        self.assertEqual(name, 'sub2api')
        self.assertEqual(provider.base_url, 'https://sub2api.example/v1')
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', ['cm_image_gen.py', 'doctor', '--show-payload-shape']), contextlib.redirect_stdout(output):
            self.assertEqual(cm.main(), 0)
        data = json.loads(output.getvalue())
        self.assertFalse(data['network_call_performed'])
        self.assertEqual(data['configured_provider']['routes'][0]['endpoint'], '/responses')
        self.assertEqual(data['payload_shapes'][0]['tool_choice'], {'type': 'image_generation'})
        self.assertNotIn(provider.api_key, output.getvalue())
        self.assertEqual([k for k in data if k.endswith('_provider')], ['configured_provider'])

    def test_normal_image_request_forces_tool_but_explicit_extra_wins(self):
        args = argparse.Namespace(responses_model=None, responses_reasoning=None,
            prompt='a circle', size='1024x1024', quality='low', background=None,
            output_format='png', tools=None, instructions=None, responses_extra=None)
        payload, model = cm.responses_payload(args, cm.DEFAULT_MODEL)
        self.assertEqual(model, 'available-controller')
        self.assertEqual(payload['tool_choice'], {'type': 'image_generation'})
        args.responses_extra = '{"tool_choice":"auto"}'
        payload, _ = cm.responses_payload(args, cm.DEFAULT_MODEL)
        self.assertEqual(payload['tool_choice'], 'auto')

    def test_custom_tools_do_not_force_an_unavailable_image_tool(self):
        args = argparse.Namespace(responses_model=None, responses_reasoning=None,
            prompt='a circle', size='1024x1024', quality=None, background=None,
            output_format=None, tools='[]', instructions=None, responses_extra=None)
        payload, _ = cm.responses_payload(args, cm.DEFAULT_MODEL)
        self.assertEqual(payload['tools'], [])
        self.assertNotIn('tool_choice', payload)

    def test_transport_probe_cannot_select_a_second_provider(self):
        with mock.patch.object(sys, 'argv', ['cm_image_gen.py', 'transport-probe',
            '--operation', 'generate', '--prompt', 'circle', '--provider', 'secondary']), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                cm.main()
        self.assertEqual(raised.exception.code, 2)

    def test_sse_repeated_image_events_save_one_item_without_raw_previews(self):
        item = {'type': 'image_generation_call', 'id': 'ig-1', 'result': 'ZmFrZQ==', 'status': 'completed'}
        events = [
            {'type': 'response.output_item.done', 'item': item},
            {'type': 'response.completed', 'response': {'status': 'completed', 'instructions': 'private-echo-marker', 'output': [item]}},
        ]
        stream = ''.join('data: ' + json.dumps(event) + '\n\n' for event in events)
        provider, _ = cm.configured_provider()
        data = cm.decode_json_or_sse_response(provider=provider, request_url=provider.base_url + '/responses',
            status=200, headers={'content-type': 'text/event-stream'}, raw_bytes=stream.encode())
        self.assertEqual(len(cm.response_image_items(data)), 1)
        diagnostics = data['_cm_sse_diagnostics']
        self.assertEqual(diagnostics['sse_image_item_count'], 1)
        self.assertNotIn('private-echo-marker', json.dumps(diagnostics))
        self.assertNotIn('ZmFrZQ==', json.dumps(diagnostics))


if __name__ == '__main__':
    unittest.main()
