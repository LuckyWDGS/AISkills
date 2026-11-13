import argparse
import base64
import contextlib
import io
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cm_image_gen as cm  # noqa: E402


PRIMARY = cm.ImageApiProvider("primary", "https://primary.example/v1", "primary-key")


class FakeResponse:
    def __init__(self, chunks, *, headers=None, status=200, error_after_reads: int | None = None, error: Exception | None = None):
        self._chunks = list(chunks)
        self._index = 0
        self._reads = 0
        self._error_after_reads = error_after_reads
        self._error = error or OSError("simulated read failure")
        self.headers = headers or {}
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self):
        return self.status

    def read(self, _size=-1):
        if self._error_after_reads is not None and self._reads >= self._error_after_reads:
            raise self._error
        self._reads += 1
        if self._index >= len(self._chunks):
            return b""
        value = self._chunks[self._index]
        self._index += 1
        return value


class FakeRequestsResponse:
    def __init__(self, chunks, *, headers=None, status_code=200, error_after_chunks: int | None = None, error: Exception | None = None):
        self._chunks = list(chunks)
        self._index = 0
        self._error_after_chunks = error_after_chunks
        self._error = error or OSError("simulated requests stream failure")
        self.headers = headers or {}
        self.status_code = status_code

    def iter_content(self, chunk_size=None):
        while self._index < len(self._chunks):
            if self._error_after_chunks is not None and self._index >= self._error_after_chunks:
                raise self._error
            value = self._chunks[self._index]
            self._index += 1
            yield value
        if self._error_after_chunks is not None and self._index >= self._error_after_chunks:
            raise self._error

    def close(self):
        return None


class CmImageGenOfflineTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        (root / "config.toml").write_text('model_provider="offline"\n[model_providers.offline]\nbase_url="http://127.0.0.1:1/v1"\n', encoding="utf-8")
        self.stack.enter_context(mock.patch.object(cm, "codex_home", return_value=root))
        self.stack.enter_context(mock.patch.dict(cm.os.environ, {"CODEXMANAGER_IMAGE_API_KEY": "offline-test-only"}, clear=True))
        self.stack.enter_context(mock.patch.object(cm.urllib.request, "urlopen", side_effect=AssertionError("Unexpected network request in offline test")))

    def test_sol_ultra_controller_keeps_sunburst_tool(self):
        args = argparse.Namespace(responses_model="gpt-6.1-sol", responses_reasoning="ultra",
                                  prompt="draw a circle", size="1024x1024", quality="high",
                                  background=None, output_format=None, tools=None,
                                  instructions=None, responses_extra=None)
        payload, controller = cm.responses_payload(args, "gpt-image-2.5-sunburst")
        self.assertEqual(controller, "gpt-6.1-sol")
        self.assertEqual(payload["reasoning"]["effort"], "ultra")
        self.assertEqual(payload["tools"][0]["model"], "gpt-image-2.5-sunburst")
        self.assertEqual(payload["tools"][0]["action"], "generate")

    def test_ultra_profile_defaults_and_explicit_cli_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / cm.LOCAL_CONFIG_DIR_NAME / "controller.json"
            profile.parent.mkdir(parents=True)
            profile.write_text(json.dumps({"api": "responses", "responses_model": "gpt-6.1-sol",
                                           "responses_reasoning": "ultra"}), encoding="utf-8")
            with mock.patch.object(cm, "codex_home", return_value=Path(tmp)):
                for command, extra in (("generate", ["--prompt", "circle"]),
                                       ("edit", ["--prompt", "circle", "--image", "reference.png"]),
                                       ("doctor", []), ("check-config", [])):
                    function = "doctor" if command == "check-config" else command
                    with self.subTest(command=command), mock.patch.object(cm, function, return_value=0) as execute:
                        with mock.patch.object(sys, "argv", ["cm_image_gen.py", command, *extra]):
                            self.assertEqual(cm.main(), 0)
                        args = execute.call_args.args[0]
                        self.assertEqual((args.api, args.responses_model, args.responses_reasoning),
                                         ("responses", "gpt-6.1-sol", "ultra"))
                        with mock.patch.object(sys, "argv", ["cm_image_gen.py", command, *extra,
                                               "--responses-model", "gpt-5.6-luna", "--responses-reasoning", "max"]):
                            self.assertEqual(cm.main(), 0)
                        args = execute.call_args.args[0]
                        self.assertEqual((args.responses_model, args.responses_reasoning), ("gpt-5.6-luna", "max"))

    def test_luna_max_controller_keeps_image2_tool(self):
        args = argparse.Namespace(responses_model="gpt-5.6-luna", responses_reasoning="max",
                                  prompt="draw a circle", size="1024x1024", quality="low",
                                  background=None, output_format=None, tools=None,
                                  instructions=None, responses_extra=None)
        payload, controller = cm.responses_payload(args, "gpt-image-2")
        self.assertEqual(controller, "gpt-5.6-luna")
        self.assertEqual(payload["reasoning"]["effort"], "max")
        self.assertEqual(payload["tools"][0]["model"], "gpt-image-2")
        self.assertEqual(payload["tool_choice"], {"type": "image_generation"})
        self.assertEqual(payload["tools"][0]["action"], "generate")

    def test_image_model_is_independent_of_conversation_model(self):
        with mock.patch.dict(cm.os.environ, {}, clear=True):
            with mock.patch.object(cm, "load_codex_config", return_value={"model": "gpt-5.4-mini"}):
                self.assertEqual(cm.image_model_selection(argparse.Namespace(model=None))["image_model"], "gpt-image-2.6-sunburst")

    def test_explicit_image_model_and_shorthand_precedence(self):
        with mock.patch.dict(cm.os.environ, {"CODEXMANAGER_IMAGE_MODEL": "gpt-image-1"}):
            for name in ("Image2", "image-2", "gpt2", "gpt-image-2"):
                selected = cm.image_model_selection(argparse.Namespace(model=name))
                self.assertEqual(selected["image_model"], "gpt-image-2")
                self.assertEqual(selected["image_model_source"], "cli")
            selected = cm.image_model_selection(argparse.Namespace(model="image2.5"))
            self.assertEqual(selected["image_model"], "gpt-image-2.5-sunburst")
            self.assertTrue(selected["model_alias_applied"])
            flare = cm.image_model_selection(argparse.Namespace(model="image2.5-flare"))
            self.assertEqual(flare["image_model"], "gpt-image-2.5-flare")
            selected26 = cm.image_model_selection(argparse.Namespace(model="image2.6"))
            self.assertEqual(selected26["image_model"], "gpt-image-2.6-sunburst")
            flare26 = cm.image_model_selection(argparse.Namespace(model="image2.6-flare"))
            self.assertEqual(flare26["image_model"], "gpt-image-2.6-flare")
            snapshot = cm.image_model_selection(argparse.Namespace(model="gpt-image-2.5-sunburst-2026-09-08"))
            self.assertEqual(snapshot["image_model"], "gpt-image-2.5-sunburst-2026-09-08")
            self.assertFalse(snapshot["model_alias_applied"])
            self.assertEqual(cm.image_model_selection(argparse.Namespace(model="vendor-custom-image"))["image_model"], "vendor-custom-image")

    def test_model_catalog_does_not_claim_unlisted_model_is_supported(self):
        response = FakeResponse([json.dumps({"data": [{"id": "gpt-image-2"}]}).encode()])
        with mock.patch.object(cm.urllib.request, "urlopen", return_value=response) as request:
            result = cm.model_catalog_check(PRIMARY, "gpt-image-2.5-sunburst")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "not_listed")
        self.assertEqual(request.call_args.args[0].get_method(), "GET")
        self.assertEqual(request.call_args.args[0].full_url, "https://primary.example/v1/models")

    def test_unknown_version_alias_stops_before_image_submission(self):
        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")), \
             mock.patch.object(cm, "model_catalog_check", return_value={"ok": False, "error": "not listed"}), \
             mock.patch.object(cm, "request_with_retry") as send:
            with self.assertRaisesRegex(SystemExit, "not listed"):
                cm.generate(argparse.Namespace(model="gpt2.5"))
            send.assert_not_called()

    def write_local_image_models(self, models, base_url=PRIMARY.base_url):
        path = cm.codex_home() / cm.LOCAL_CONFIG_DIR_NAME / "models.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"base_url": base_url, "image_models": models}), encoding="utf-8")
        return path

    def test_local_image_models_preserve_exact_json_and_multipart_ids(self):
        models = ["gpt-image-2.6-flare", "gpt-image-2.6-sunburst"]
        self.write_local_image_models(models)
        def catalog_response(*args, **kwargs):
            return FakeResponse([json.dumps({"data": [{"id": "text-model"}]}).encode()])
        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")), \
             mock.patch.object(cm.urllib.request, "urlopen", side_effect=catalog_response):
            for model in models:
                with self.subTest(model=model):
                    check = cm.model_catalog_check(PRIMARY, model)
                    self.assertTrue(check["ok"])
                    self.assertEqual(check["status"], "locally_registered")
                    self.assertFalse(check["remote_listed"])
                    self.assertTrue(check["local_registered"])
                    self.assertFalse(check["generation_verified"])
                    self.assertNotIn(model, check["listed_models"])
                    args = argparse.Namespace(model=model, api="images", check_model=True,
                        prompt="test", size="1024x1024", response_format="b64_json", n=None,
                        quality=None, background=None, output_format=None)
                    payload, selected = cm.image_payload(args)
                    self.assertEqual((selected, json.loads(json.dumps(payload))["model"]), (model, model))
                    self.assertEqual(payload["quality"], "max")
                    self.assertEqual(payload["complexity"], "high")
                    body, _ = cm.multipart_body(payload, [])
                    self.assertIn(f'name="model"\r\n\r\n{model}\r\n'.encode(), body)

    def test_local_image_models_do_not_apply_to_another_provider(self):
        model = "gpt-image-2.6-flare"
        self.write_local_image_models([model])
        other = cm.ImageApiProvider("other", "https://other.example/v1", "other-key")
        response = FakeResponse([b'{"data": []}'])
        with mock.patch.object(cm.urllib.request, "urlopen", return_value=response):
            check = cm.model_catalog_check(other, model)
        self.assertFalse(check["ok"])
        self.assertFalse(check["local_registered"])

    def test_local_registration_does_not_mask_catalog_auth_failure(self):
        model = "gpt-image-2.6-flare"
        self.write_local_image_models([model])
        error = cm.urllib.error.HTTPError(PRIMARY.base_url + "/models", 401, "Unauthorized", {}, None)
        with mock.patch.object(cm.urllib.request, "urlopen", side_effect=error):
            check = cm.model_catalog_check(PRIMARY, model)
        self.assertFalse(check["ok"])
        self.assertEqual(check["status"], "catalog_unavailable")

    def test_responses_doctor_does_not_accept_a_local_image_as_controller(self):
        model = "gpt-image-2.6-flare"
        self.write_local_image_models([model])
        args = argparse.Namespace(api="responses", operation="all", model=model,
            responses_model=model, responses_reasoning=None, check_model=True)
        output = io.StringIO()
        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")), \
             mock.patch.object(cm.urllib.request, "urlopen", return_value=FakeResponse([b'{"data": []}'])), \
             contextlib.redirect_stdout(output):
            self.assertEqual(cm.doctor(args), 1)
        check = json.loads(output.getvalue())["model_catalog_check"]
        self.assertFalse(check["local_registered"])
        self.assertEqual(check["status"], "not_listed")

    def test_offline_doctor_shows_local_registration_without_network(self):
        model = "gpt-image-2.6-sunburst"
        self.write_local_image_models([model])
        output = io.StringIO()
        args = argparse.Namespace(api="images", operation="all", model=model)
        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")), \
             contextlib.redirect_stdout(output):
            self.assertEqual(cm.doctor(args), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result["network_call_performed"])
        self.assertTrue(result["image_model_registered_locally"])
        self.assertEqual(result["local_image_models"], [model])

    def test_invalid_local_catalog_stops_before_network(self):
        self.write_local_image_models(["gpt-image-2.6-*"])
        with mock.patch.object(cm.urllib.request, "urlopen") as request:
            with self.assertRaisesRegex(SystemExit, "Invalid local image catalog"):
                cm.model_catalog_check(PRIMARY, "gpt-image-2.6-flare")
        request.assert_not_called()

    def test_explicit_model_roundtrips_json_multipart_and_responses_tool(self):
        args = argparse.Namespace(model="gpt-image-2.5-sunburst", prompt="test", size="1024x1024",
                                  response_format="b64_json", n=None, quality=None,
                                  background=None, output_format=None, tools=None)
        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")), \
             mock.patch.object(cm, "model_catalog_check", return_value={"ok": True}):
            payload, model = cm.image_payload(args)
        self.assertEqual(payload["model"], "gpt-image-2.5-sunburst")
        body, _ = cm.multipart_body(payload, [])
        self.assertIn(b'name="model"\r\n\r\ngpt-image-2.5-sunburst\r\n', body)
        self.assertEqual(cm.image_tool_config(args, model)[0]["model"], "gpt-image-2.5-sunburst")

    def test_default_images_routes_for_generate_and_edit(self) -> None:
        calls = []

        def fake_request_provider(provider, command, endpoint, payload, timeout, multipart=None):
            calls.append((provider.name, command, endpoint, bool(multipart)))
            transport = "images_multipart" if multipart else "images_json"
            return cm.ProviderRequestResult({"data": [{"b64_json": "ZmFrZQ=="}]}, endpoint, transport, f"{provider.base_url}{endpoint}")

        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")), mock.patch.object(cm, "model_catalog_check", return_value={"ok": True}):
            with mock.patch.object(cm, "request_provider", side_effect=fake_request_provider):
                _data, provider, endpoint, transport, request_url, errors = cm.request_with_retry(
                    "generate", {"model": cm.DEFAULT_MODEL}, 1
                )
                self.assertEqual(provider.name, "primary")
                self.assertEqual(endpoint, "/images/generations")
                self.assertEqual(transport, "images_json")
                self.assertEqual(request_url, "https://primary.example/v1/images/generations")
                self.assertEqual(errors, [])

                _data, provider, endpoint, transport, request_url, errors = cm.request_with_retry(
                    "edit", {"model": cm.DEFAULT_MODEL}, 1, {"fields": {}, "files": []}
                )
                self.assertEqual(provider.name, "primary")
                self.assertEqual(endpoint, "/images/edits")
                self.assertEqual(transport, "images_multipart")
                self.assertEqual(request_url, "https://primary.example/v1/images/edits")
                self.assertEqual(errors, [])

        self.assertEqual(calls[0], ("primary", "generate", "/images/generations", False))
        self.assertEqual(calls[1], ("primary", "edit", "/images/edits", True))

    def test_retryable_primary_failure_stops_after_three_attempts_without_switching_provider(self) -> None:
        calls = []

        def fake_request_provider(provider, command, endpoint, payload, timeout, multipart=None):
            calls.append((provider.name, endpoint))
            raise cm.ImageApiError("temporary gateway failure", status=502, provider=provider.name)

        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")):
            with mock.patch.object(cm, "request_provider", side_effect=fake_request_provider), mock.patch.object(cm.time, "sleep") as sleep:
                with self.assertRaises(SystemExit) as ctx:
                    cm.request_with_retry("generate", {"model": cm.DEFAULT_MODEL}, 1)

        self.assertIn("temporary gateway failure", str(ctx.exception))
        self.assertEqual(calls, [("primary", "/images/generations")] * 3)
        self.assertEqual(sleep.call_args_list, [mock.call(5), mock.call(15)])

    def test_sse_stream_with_image_result_is_recovered(self) -> None:
        sse = (
            "event: response.output_item.done\n"
            'data: {"type":"image_generation_call","result":"ZmFrZQ=="}\n'
            "\n"
            "event: response.completed\n"
            'data: {"type":"response.completed"}\n'
            "\n"
        )
        data = cm.decode_json_or_sse_response(
            provider=PRIMARY,
            request_url="https://primary.example/v1/images/generations",
            status=200,
            headers={},
            raw_bytes=sse.encode("utf-8"),
        )
        self.assertTrue(data["_cm_sse_parsed"])
        self.assertEqual(data["data"][0]["b64_json"], "ZmFrZQ==")
        self.assertEqual(data["_cm_sse_diagnostics"]["sse_image_item_count"], 1)

    def test_partial_json_response_is_salvaged(self) -> None:
        raw = b'{"data":[{"b64_json":"ZmFrZQ=="}],"created":123'
        data = cm.decode_json_or_sse_response(
            provider=PRIMARY,
            request_url="https://primary.example/v1/images/generations",
            status=200,
            headers={"content-type": "application/json"},
            raw_bytes=raw,
            partial_diagnostics={"error_kind": "images_partial_read_error", "partial_response_salvage_attempted": True},
        )
        self.assertTrue(data["_cm_partial_response_salvaged"])
        self.assertEqual(data["data"][0]["b64_json"], "ZmFrZQ==")
        self.assertEqual(data["_cm_partial_response_diagnostics"]["partial_recovery_item_count"], 1)

    def test_request_json_salvages_partial_sse_after_read_error(self) -> None:
        sse = (
            "event: response.output_item.done\n"
            'data: {"type":"image_generation_call","result":"ZmFrZQ=="}\n'
            "\n"
            "event: response.completed\n"
        ).encode("utf-8")
        response = FakeResponse([sse[:45], sse[45:]], headers={"content-type": "text/event-stream"}, error_after_reads=2)

        with mock.patch.object(cm.urllib.request, "urlopen", return_value=response):
            data = cm.request_json(PRIMARY, "/images/generations", {"model": cm.DEFAULT_MODEL}, 1)

        self.assertTrue(data["_cm_partial_response_salvaged"])
        self.assertTrue(data["_cm_sse_parsed"])
        self.assertEqual(data["data"][0]["b64_json"], "ZmFrZQ==")

    def test_request_json_polls_async_result_until_image_available(self) -> None:
        initial = FakeResponse(
            [b'{"id":"job_123","status":"processing","poll_url":"https://primary.example/v1/tasks/job_123"}'],
            headers={"content-type": "application/json"},
        )
        polled = FakeResponse(
            [b'{"status":"succeeded","data":[{"b64_json":"ZmFrZQ=="}]}'],
            headers={"content-type": "application/json"},
        )

        def fake_urlopen(req, timeout=0):
            if req.full_url.endswith("/images/generations"):
                return initial
            if req.full_url.endswith("/tasks/job_123"):
                return polled
            raise AssertionError(f"Unexpected URL: {req.full_url}")

        with mock.patch.object(cm.urllib.request, "urlopen", side_effect=fake_urlopen):
            with mock.patch.object(cm.time, "sleep", return_value=None):
                data = cm.request_json(PRIMARY, "/images/generations", {"model": cm.DEFAULT_MODEL}, 1)

        self.assertTrue(data["_cm_async_poll_used"])
        self.assertTrue(data["_cm_async_poll_diagnostics"]["completed"])
        self.assertEqual(data["data"][0]["b64_json"], "ZmFrZQ==")

    def test_request_json_requests_stream_polls_async_result_until_image_available(self) -> None:
        initial = FakeRequestsResponse(
            [b'{"id":"job_456","status":"processing","poll_url":"https://primary.example/v1/tasks/job_456"}'],
            headers={"content-type": "application/json"},
        )
        polled = FakeRequestsResponse(
            [b'{"status":"succeeded","data":[{"b64_json":"ZmFrZQ=="}]}'],
            headers={"content-type": "application/json"},
        )

        class FakeRequestsModule:
            def post(self, url, **kwargs):
                if url.endswith("/images/generations"):
                    return initial
                raise AssertionError(f"Unexpected POST URL: {url}")

            def get(self, url, **kwargs):
                if url.endswith("/tasks/job_456"):
                    return polled
                raise AssertionError(f"Unexpected GET URL: {url}")

        with mock.patch.object(cm, "load_requests_module", return_value=FakeRequestsModule()):
            with mock.patch.object(cm.time, "sleep", return_value=None):
                data = cm.request_json_requests_stream(PRIMARY, "/images/generations", {"model": cm.DEFAULT_MODEL}, 1)

        self.assertTrue(data["_cm_async_poll_used"])
        self.assertEqual(data["_cm_async_poll_diagnostics"]["poll_client"], "request_poll_url_requests_stream")
        self.assertEqual(data["data"][0]["b64_json"], "ZmFrZQ==")

    def test_transport_probe_reports_mixed_client_results(self) -> None:
        args = argparse.Namespace(
            operation="generate",
            client="both",
            prompt="test prompt",
            image=None,
            mask=None,
            model=None,
            size=cm.DEFAULT_SIZE,
            response_format=cm.DEFAULT_RESPONSE_FORMAT,
            out_dir=None,
            filename=None,
            n=None,
            quality=None,
            background=None,
            output_format=None,
            timeout=1,
            save_images=False,
        )

        def fake_request_provider(provider, command, endpoint, payload, timeout, multipart=None):
            raise cm.ImageApiError("urllib failed", status=525, provider=provider.name, diagnostics={"transport_client": "urllib"})

        def fake_request_provider_requests_stream(provider, command, endpoint, payload, timeout, multipart=None):
            return cm.ProviderRequestResult(
                {"data": [{"b64_json": "ZmFrZQ=="}], "_cm_async_poll_used": True, "_cm_async_poll_diagnostics": {"completed": True}},
                endpoint,
                "images_json_requests_stream",
                f"{provider.base_url}{endpoint}",
            )

        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")), mock.patch.object(cm, "model_catalog_check", return_value={"ok": True}):
            with mock.patch.object(cm, "request_provider", side_effect=fake_request_provider):
                with mock.patch.object(cm, "request_provider_requests_stream", side_effect=fake_request_provider_requests_stream):
                    buffer = io.StringIO()
                    with contextlib.redirect_stdout(buffer):
                        rc = cm.transport_probe(args)

        self.assertEqual(rc, 0)
        data = json.loads(buffer.getvalue())
        self.assertEqual(data["operation"], "transport-probe")
        self.assertEqual(len(data["clients"]), 2)
        self.assertFalse(data["clients"][0]["ok"])
        self.assertTrue(data["clients"][1]["ok"])
        self.assertEqual(data["clients"][1]["transport"], "images_json_requests_stream")

    def test_no_image_json_diagnostics_identify_async_shape(self) -> None:
        message = cm.no_image_items_error(
            provider=PRIMARY,
            endpoint="/images/generations",
            transport="images_json",
            request_url="https://primary.example/v1/images/generations",
            data={"id": "job_123", "status": "processing"},
        )
        self.assertIn("likely_async_or_polling_response", message)
        self.assertIn("processing", message)

    def test_doctor_reports_routes_without_network_call(self) -> None:
        args = argparse.Namespace(
            api="images",
            operation="all",
            model=None,
            responses_model=None,
            size=cm.DEFAULT_SIZE,
            response_format=cm.DEFAULT_RESPONSE_FORMAT,
            n=None,
            quality=None,
            background=None,
            output_format=None,
            show_payload_shape=False,
        )
        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")):
            with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    rc = cm.doctor(args)
        self.assertEqual(rc, 0)
        data = json.loads(buffer.getvalue())
        self.assertFalse(data["network_call_performed"])
        self.assertEqual(data["configured_provider"]["routes"][0]["endpoint"], "/images/generations")
        self.assertEqual(data["configured_provider"]["routes"][1]["endpoint"], "/images/edits")


    def test_doctor_payload_shape_reports_safe_multipart_model_field(self) -> None:
        args = argparse.Namespace(
            api="images",
            operation="edit",
            model=None,
            responses_model=None,
            size=cm.DEFAULT_SIZE,
            response_format=cm.DEFAULT_RESPONSE_FORMAT,
            n=None,
            quality=None,
            background=None,
            output_format=None,
            show_payload_shape=True,
        )
        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")):
            with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    rc = cm.doctor(args)
        self.assertEqual(rc, 0)
        data = json.loads(buffer.getvalue())
        shape = data["payload_shapes"][0]
        self.assertEqual(shape["content_type"], "multipart/form-data")
        self.assertEqual(shape["form_fields"]["model"], cm.DEFAULT_MODEL)
        self.assertEqual(shape["form_fields"]["quality"], "max")
        self.assertEqual(shape["form_fields"]["complexity"], "high")
        self.assertEqual(shape["image_file_parts"], "<redacted>")

    def test_edit_sends_default_model_in_multipart_fields(self) -> None:
        captured = {}
        from PIL import Image
        valid_png = io.BytesIO()
        Image.new("RGB", (1024, 1024), "blue").save(valid_png, format="PNG")

        def fake_request_with_retry(command, compat_payload, timeout, multipart=None, *, max_attempts=3):
            captured["command"] = command
            captured["payload"] = compat_payload
            captured["multipart"] = multipart
            return (
                {"data": [{"b64_json": base64.b64encode(valid_png.getvalue()).decode()}]},
                PRIMARY,
                "/images/edits",
                "images_multipart",
                "https://primary.example/v1/images/edits",
                [],
            )

        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "input.png"
            image_path.write_bytes(b"fake-png")
            out_dir = Path(tmp) / "out"
            args = argparse.Namespace(
                prompt="change background",
                image=[str(image_path)],
                mask=None,
                api="images",
                model=None,
                responses_model=None,
                tools=None,
                instructions=None,
                responses_extra=None,
                size=cm.DEFAULT_SIZE,
                response_format=cm.DEFAULT_RESPONSE_FORMAT,
                out_dir=str(out_dir),
                filename="result.png",
                n=None,
                quality=None,
                background=None,
                output_format=None,
                timeout=1,
            )
            with mock.patch.object(cm, "request_with_retry", side_effect=fake_request_with_retry):
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = cm.edit(args)

        self.assertEqual(rc, 0)
        self.assertEqual(captured["command"], "edit")
        self.assertEqual(captured["multipart"]["fields"]["model"], cm.DEFAULT_MODEL)
        self.assertEqual(captured["multipart"]["fields"]["quality"], "max")
        self.assertEqual(captured["multipart"]["fields"]["complexity"], "high")
        self.assertEqual(captured["multipart"]["fields"]["prompt"], "change background")
        self.assertEqual(captured["multipart"]["fields"]["size"], cm.DEFAULT_SIZE)
        self.assertNotIn("response_format", captured["multipart"]["fields"])
        self.assertEqual(captured["multipart"]["files"][0]["field"], "image")


    def test_cli_quality_and_complexity_reach_json_and_multipart_wire(self):
        from email.parser import BytesParser
        from email.policy import default
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "reference.png"
            Image.new("RGB", (16, 16), "blue").save(source)
            reply = json.dumps({"data": [{"b64_json": base64.b64encode(source.read_bytes()).decode()}]}).encode()
            settings = [([], "gpt-image-2.6-sunburst", "max", "high"),
                        (["--model", "gpt-image-2.6-flare", "--quality", "high", "--complexity", "low"],
                         "gpt-image-2.6-flare", "high", "low"),
                        (["--model", "gpt-image-2.5-sunburst"], "gpt-image-2.5-sunburst", "max", None)]
            for operation in ("generate", "edit"):
                for flags, model, quality, complexity in settings:
                    with self.subTest(operation=operation, model=model, complexity=complexity):
                        captured = []
                        def send(request, **kwargs):
                            captured.append(request)
                            return FakeResponse([reply])
                        argv = ["cm_image_gen.py", operation, "--api", "images", "--prompt", "one blue mug",
                                "--size", "16x16", "--require-exact-size", "--max-attempts", "1",
                                "--out-dir", tmp, *flags]
                        if operation == "edit":
                            argv += ["--image", str(source)]
                        output = io.StringIO()
                        with mock.patch.object(cm.urllib.request, "urlopen", side_effect=send), \
                             mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
                            self.assertEqual(cm.main(), 0)
                        self.assertEqual(len(captured), 1)
                        request = captured[0]
                        self.assertEqual(request.get_method(), "POST")
                        self.assertTrue(request.full_url.endswith("/images/edits" if operation == "edit" else "/images/generations"))
                        if operation == "generate":
                            fields = json.loads(request.data)
                        else:
                            content_type = request.get_header("Content-type")
                            envelope = b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + request.data
                            message = BytesParser(policy=default).parsebytes(envelope)
                            fields = {part.get_param("name", header="content-disposition"): part.get_payload(decode=True).decode()
                                      for part in message.iter_parts() if not part.get_filename()}
                        self.assertEqual(fields["model"], model)
                        self.assertEqual(fields["quality"], quality)
                        if complexity is None:
                            self.assertNotIn("complexity", fields)
                        else:
                            self.assertEqual(fields["complexity"], complexity)
                        self.assertNotIn("reasoning", fields)
                        result = json.loads(output.getvalue())
                        self.assertEqual(result["requested_complexity"], complexity)

    def test_responses_cannot_silently_drop_explicit_image_complexity(self):
        argv = ["cm_image_gen.py", "generate", "--api", "responses", "--prompt", "one blue mug", "--complexity", "high"]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(cm, "request_responses_with_retry") as send:
            with self.assertRaisesRegex(SystemExit, "only with --api images"):
                cm.main()
            send.assert_not_called()


class OutputSizeValidationTests(unittest.TestCase):
    def make_png(self, path, dimensions):
        from PIL import Image
        Image.new("RGB", dimensions, "white").save(path)
        return path

    def test_4k_default_is_strict_and_lower_resolution_is_opt_in(self):
        self.assertTrue(cm.exact_size_is_required("3840x2160"))
        self.assertTrue(cm.exact_size_is_required("2160x3840"))
        self.assertFalse(cm.exact_size_is_required("1024x1536"))
        self.assertTrue(cm.exact_size_is_required("1024x1536", True))

    def test_actual_png_mismatch_keeps_file_and_reports_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=self.make_png(Path(tmp)/"returned.png", (1672,941))
            before=path.read_bytes()
            result=cm.validate_output_sizes([path], "3840x2160", require_exact=True)
            self.assertTrue(result["size_validation_failed"])
            self.assertEqual(result["output_dimensions"], ["1672x941"])
            self.assertFalse(result["size_verified"])
            self.assertEqual(path.read_bytes(), before)

    def test_exact_png_passes_and_auto_does_not_claim_size_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=self.make_png(Path(tmp)/"exact.png", (3840,2160))
            self.assertTrue(cm.validate_output_sizes([path], "3840x2160", require_exact=True)["size_verified"])
            self.assertIsNone(cm.validate_output_sizes([path], "auto")["size_verified"])
            self.assertTrue(cm.validate_output_sizes([path], "auto", require_exact=True)["size_validation_failed"])

    def test_unreadable_image_fails_only_when_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.png";path.write_bytes(b"not an image")
            self.assertTrue(cm.validate_output_sizes([path], "3840x2160", require_exact=True)["size_validation_failed"])
            self.assertFalse(cm.validate_output_sizes([path], "1024x1024")["size_validation_failed"])
            self.assertIsNone(cm.parse_image_dimensions(b"\x89PNG\r\n\x1a\n"))

    def test_jpeg_and_webp_real_dimensions(self):
        from PIL import Image
        for fmt in ("JPEG", "WEBP"):
            stream=io.BytesIO();Image.new("RGB",(320,240)).save(stream,format=fmt)
            self.assertEqual(cm.parse_image_dimensions(stream.getvalue()), (320,240))

    def test_generate_and_edit_return_failure_for_mismatched_4k(self):
        import base64
        from PIL import Image
        stream=io.BytesIO();Image.new("RGB",(1672,941)).save(stream,format="PNG")
        response={"data":[{"b64_json":base64.b64encode(stream.getvalue()).decode()}]}
        provider=cm.ImageApiProvider("primary", "https://primary.example/v1", "dummy")
        for operation in ("generate", "edit"):
            with tempfile.TemporaryDirectory() as tmp:
                source=self.make_png(Path(tmp)/"source.png", (64,64))
                args=argparse.Namespace(api="responses", model=cm.DEFAULT_MODEL, prompt="test",size="3840x2160",quality="high",background=None,output_format=None,response_format="b64_json",n=1,timeout=1,tools=None,instructions=None,responses_extra=None,responses_reasoning="max",responses_model="gpt-5.6-luna",out_dir=tmp,filename="result.png",image=[str(source)],mask=None,require_exact_size=False)
                fake=(response, provider, "/responses", "responses_stream", "https://primary.example/v1/responses", [])
                stdout=io.StringIO()
                with mock.patch.object(cm,"request_responses_with_retry",return_value=fake), contextlib.redirect_stdout(stdout):
                    code=getattr(cm,operation)(args)
                result=json.loads(stdout.getvalue())
                self.assertEqual(code,1)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error_kind"],"image_size_mismatch")
                self.assertEqual(result["output_dimensions"],["1672x941"])
                self.assertTrue(Path(result["paths"][0]).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
