"""Single-provider behavior with no installed controller profile or image skill."""
import argparse
import base64
import contextlib
from email import policy
from email.parser import BytesParser
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cm_image_gen as cm  # noqa: E402


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

    def test_copying_only_skill_uses_images_without_profile(self):
        for command, extra in (('generate', ['--prompt', 'circle']),
                               ('edit', ['--prompt', 'circle', '--image', 'input.png']),
                               ('doctor', []), ('check-config', [])):
            function = 'doctor' if command == 'check-config' else command
            with self.subTest(command=command), mock.patch.object(cm, function, return_value=0) as execute:
                with mock.patch.object(sys, 'argv', ['cm_image_gen.py', command, *extra]):
                    self.assertEqual(cm.main(), 0)
                args = execute.call_args.args[0]
                self.assertEqual(args.api, 'images')
                self.assertEqual(cm.image_model_selection(args)['image_model'], cm.DEFAULT_MODEL)
                self.assertEqual(cm.image_quality(args, cm.DEFAULT_MODEL), 'max')
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
        self.assertEqual(data['configured_provider']['routes'][0]['endpoint'], '/images/generations')
        self.assertEqual(data['configured_provider']['routes'][1]['endpoint'], '/images/edits')
        self.assertEqual(data['payload_shapes'][0]['json_fields']['quality'], 'max')
        self.assertEqual(data['payload_shapes'][1]['form_fields']['quality'], 'max')
        self.assertEqual(data['requested_quality'], 'max')
        self.assertNotIn('responses_reasoning', data)
        self.assertNotIn(provider.api_key, output.getvalue())
        self.assertEqual([k for k in data if k.endswith('_provider')], ['configured_provider'])

    def test_images_profile_needs_no_controller_and_cli_can_explicitly_select_responses(self):
        profile = self.root / cm.LOCAL_CONFIG_DIR_NAME / 'controller.json'
        profile.parent.mkdir()
        profile.write_text('{"api":"images"}', encoding='utf-8')
        self.assertEqual(cm.controller_defaults(), {'api': 'images'})
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', ['cm_image_gen.py', 'doctor', '--api', 'responses',
                                            '--responses-reasoning', 'max', '--show-payload-shape']), \
             contextlib.redirect_stdout(output):
            self.assertEqual(cm.main(), 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data['default_api'], 'images')
        self.assertEqual(data['configured_provider']['routes'][0]['endpoint'], '/responses')
        self.assertEqual(data['payload_shapes'][0]['reasoning_effort'], 'max')

    def test_cli_sends_actual_images_json_and_multipart_with_max_quality(self):
        """Exercise parsing, route selection, serialization and saved outputs offline."""
        from PIL import Image

        source = self.root / 'reference.png'
        Image.new('RGB', (16, 16), 'blue').save(source)
        png = source.read_bytes()
        image_result = {'data': [{'b64_json': base64.b64encode(png).decode()}]}
        profile_path = self.root / cm.LOCAL_CONFIG_DIR_NAME / 'controller.json'
        profile_path.parent.mkdir()
        profiles = [None,
                    {'api': 'images', 'responses_model': 'stored-controller', 'responses_reasoning': 'max'},
                    {'api': 'responses', 'responses_model': 'old-controller', 'responses_reasoning': 'max'}]
        for profile in profiles:
            if profile is not None:
                profile_path.write_text(json.dumps(profile), encoding='utf-8')
            for command in ('generate', 'edit'):
                for quality_override in (None, 'low'):
                    expected_quality = quality_override or 'max'
                    endpoint = '/images/generations' if command == 'generate' else '/images/edits'
                    submitted = []

                    def fake_urlopen(request, timeout=None):
                        if request.get_method() == 'GET':
                            self.assertEqual(request.full_url, 'https://sub2api.example/v1/models')
                            data = {'data': [{'id': cm.DEFAULT_MODEL}]}
                        else:
                            self.assertEqual(request.get_method(), 'POST')
                            self.assertEqual(request.full_url, 'https://sub2api.example/v1' + endpoint)
                            content_type = request.get_header('Content-type')
                            if command == 'generate':
                                self.assertEqual(content_type, 'application/json')
                                fields = json.loads(request.data)
                            else:
                                self.assertTrue(content_type.startswith('multipart/form-data;'))
                                message = BytesParser(policy=policy.default).parsebytes(
                                    ('Content-Type: ' + content_type + '\r\n\r\n').encode() + request.data)
                                parts = {part.get_param('name', header='content-disposition'): part
                                         for part in message.iter_parts()}
                                self.assertEqual(parts['image'].get_payload(decode=True), png)
                                fields = {name: part.get_payload(decode=True).decode()
                                          for name, part in parts.items() if part.get_filename() is None}
                            self.assertEqual(fields['model'], cm.DEFAULT_MODEL)
                            self.assertEqual(fields['quality'], expected_quality)
                            self.assertEqual(fields['prompt'], 'Change the mug to blue')
                            for key in ('reasoning', 'reasoning_effort', 'tools', 'tool_choice'):
                                self.assertNotIn(key, fields)
                            submitted.append(request.full_url)
                            data = image_result
                        response = io.BytesIO(json.dumps(data).encode())
                        response.status = 200
                        response.headers = {'content-type': 'application/json'}
                        return response

                    argv = ['cm_image_gen.py', command, '--prompt', 'Change the mug to blue',
                            '--size', '16x16', '--out-dir', str(self.root / 'out')]
                    if command == 'edit':
                        argv += ['--image', str(source)]
                    if profile and profile['api'] == 'responses':
                        argv += ['--api', 'images']
                    if quality_override:
                        argv += ['--quality', quality_override]
                    output = io.StringIO()
                    with self.subTest(profile=profile, command=command, quality=expected_quality), \
                         mock.patch.object(cm.urllib.request, 'urlopen', side_effect=fake_urlopen), \
                         mock.patch.object(sys, 'argv', argv), contextlib.redirect_stdout(output):
                        self.assertEqual(cm.main(), 0)
                    result = json.loads(output.getvalue())
                    self.assertEqual(len(submitted), 1)
                    self.assertEqual(result['endpoint'], endpoint)
                    self.assertEqual(result['requested_quality'], expected_quality)
                    self.assertEqual(Path(result['paths'][0]).read_bytes(), png)

    def test_quality_defaults_respect_selected_model_and_explicit_override(self):
        for model, expected in ((cm.DEFAULT_MODEL, 'max'), ('image2.5-flare', 'max'),
                                ('gpt-image-2.5-sunburst-2026-09-08', 'max'),
                                ('gpt-image-2', None), ('custom-image-model', None)):
            for explicit in (None, 'low', 'auto'):
                args = argparse.Namespace(model=model, api='images', prompt='circle', size='1024x1024',
                    response_format='b64_json', n=None, quality=explicit, background=None, output_format=None)
                with self.subTest(model=model, explicit=explicit), \
                     mock.patch.object(cm, 'model_catalog_check', return_value={'ok': True}):
                    payload, selected = cm.image_payload(args)
                    tool = cm.image_tool_config(args, selected)[0]
                self.assertEqual(payload.get('quality'), explicit or expected)
                self.assertEqual(tool.get('quality'), explicit or expected)

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
