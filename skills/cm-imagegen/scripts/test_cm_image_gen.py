import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import cm_image_gen as cm


PRIMARY = cm.ImageApiProvider("primary", "https://primary.example/v1", "primary-key")
FALLBACK = cm.ImageApiProvider("fallback", "https://fallback.example/v1", "fallback-key")


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
    def test_default_images_routes_for_generate_and_edit(self) -> None:
        calls = []

        def fake_request_provider(provider, command, endpoint, payload, timeout, multipart=None):
            calls.append((provider.name, command, endpoint, bool(multipart)))
            transport = "images_multipart" if multipart else "images_json"
            return cm.ProviderRequestResult({"data": [{"b64_json": "ZmFrZQ=="}]}, endpoint, transport, f"{provider.base_url}{endpoint}")

        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")):
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

    def test_retryable_primary_failure_stops_after_single_attempt_without_default_fallback(self) -> None:
        calls = []

        def fake_request_provider(provider, command, endpoint, payload, timeout, multipart=None):
            calls.append((provider.name, endpoint))
            raise cm.ImageApiError("temporary gateway failure", status=502, provider=provider.name)

        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")):
            with mock.patch.object(cm, "request_provider", side_effect=fake_request_provider):
                with self.assertRaises(SystemExit) as ctx:
                    cm.request_with_retry("generate", {"model": cm.DEFAULT_MODEL}, 1)

        self.assertIn("temporary gateway failure", str(ctx.exception))
        self.assertEqual(calls, [("primary", "/images/generations")])

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
            provider="fallback",
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

        with mock.patch.object(cm, "load_fallback_provider", return_value=FALLBACK):
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
            with mock.patch.object(cm, "load_fallback_provider", return_value=FALLBACK):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    rc = cm.doctor(args)
        self.assertEqual(rc, 0)
        data = json.loads(buffer.getvalue())
        self.assertFalse(data["network_call_performed"])
        self.assertEqual(data["configured_provider"]["routes"][0]["endpoint"], "/images/generations")
        self.assertEqual(data["configured_provider"]["routes"][1]["endpoint"], "/images/edits")
        self.assertTrue(data["fallback_provider"]["configured"])
        self.assertEqual(data["fallback_provider"]["base_url"], "https://fallback.example/v1")
        self.assertEqual(data["fallback_provider"]["routes"][0]["endpoint"], "/images/generations")
        self.assertEqual(data["fallback_provider"]["routes"][1]["endpoint"], "/images/edits")
        self.assertTrue(data["fallback_provider"]["temporarily_unavailable"])
        self.assertFalse(data["fallback_provider"]["used_for_default_route"])

    def test_doctor_reports_unconfigured_fallback_without_failing(self) -> None:
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
            show_payload_shape=False,
        )
        with mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")):
            with mock.patch.object(cm, "load_fallback_provider", side_effect=SystemExit("Fallback missing")):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    rc = cm.doctor(args)
        self.assertEqual(rc, 0)
        data = json.loads(buffer.getvalue())
        self.assertFalse(data["fallback_provider"]["configured"])
        self.assertFalse(data["fallback_provider"]["used_for_default_route"])
        self.assertTrue(data["fallback_provider"]["temporarily_unavailable"])
        self.assertIn("Fallback missing", data["fallback_provider"]["error"])

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
            with mock.patch.object(cm, "load_fallback_provider", return_value=FALLBACK):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    rc = cm.doctor(args)
        self.assertEqual(rc, 0)
        data = json.loads(buffer.getvalue())
        shape = data["payload_shapes"][0]
        self.assertEqual(shape["content_type"], "multipart/form-data")
        self.assertEqual(shape["form_fields"]["model"], cm.DEFAULT_MODEL)
        self.assertEqual(shape["image_file_parts"], "<redacted>")

    def test_edit_sends_default_model_in_multipart_fields(self) -> None:
        captured = {}

        def fake_request_with_retry(command, compat_payload, timeout, multipart=None):
            captured["command"] = command
            captured["payload"] = compat_payload
            captured["multipart"] = multipart
            return (
                {"data": [{"b64_json": "ZmFrZQ=="}]},
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
        self.assertEqual(captured["multipart"]["fields"]["prompt"], "change background")
        self.assertEqual(captured["multipart"]["fields"]["size"], cm.DEFAULT_SIZE)
        self.assertEqual(captured["multipart"]["fields"]["response_format"], cm.DEFAULT_RESPONSE_FORMAT)
        self.assertEqual(captured["multipart"]["files"][0]["field"], "image")


if __name__ == "__main__":
    unittest.main(verbosity=2)
