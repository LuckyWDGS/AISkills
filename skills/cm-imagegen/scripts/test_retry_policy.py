"""Offline tests of bounded same-route retries; no image or network requests."""

import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

import cm_image_gen as cm


PRIMARY = cm.ImageApiProvider("primary", "https://offline.example/v1", "offline-test-key")
IMAGE_DATA = {"data": [{"b64_json": "ZmFrZQ=="}]}
REFERENCE = cm.InputImage(Path("offline-reference.png"), "offline-reference.png", "image/png", b"fixed-reference-bytes")
ROUTES = ("generate", "edit", "responses")


def transient(status=503):
    return cm.ImageApiError("temporary service failure", status=status, provider=PRIMARY.name)


def failed_response(status="completed", *, refusal=None, text=None):
    output = [{"type": "image_generation_call", "id": "offline-image-1", "status": "failed", "result": None}]
    if refusal is not None:
        output.append({"type": "message", "role": "assistant", "content": [{"type": "refusal", "refusal": refusal}]})
    elif text is not None:
        output.append({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]})
    return {"id": "offline-response-1", "status": status, "output": output}


def sse_no_image_error(*, status="completed", http_status=200, refusal=None,
                       text="The image tool returned no result.", prefix="", partial=False):
    """Use the real decoder, not fabricated retry classification diagnostics."""
    if status is None:
        stream = prefix + 'event: response.image_generation_call.in_progress\ndata: {"type":"response.image_generation_call.in_progress","item_id":"offline-image-1"}\n\n'
    else:
        payload = {"type": "response." + status, "response": failed_response(status, refusal=refusal, text=text)}
        stream = prefix + "event: response." + status + "\ndata: " + json.dumps(payload) + "\n\n"
    partial_diagnostics = ({"error_kind": "responses_partial_read_error", "read_exception_type": "ConnectionResetError",
                            "partial_response_salvage_attempted": True} if partial else None)
    try:
        cm.decode_json_or_sse_response(provider=PRIMARY, request_url=PRIMARY.base_url + "/responses",
                                      status=http_status, headers={"content-type": "text/event-stream"},
                                      raw_bytes=stream.encode("utf-8"), partial_diagnostics=partial_diagnostics)
    except cm.ImageApiError as exc:
        return exc
    raise AssertionError("No-image SSE unexpectedly decoded successfully")


class RetryPolicyOfflineTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(cm.urllib.request, "urlopen", side_effect=AssertionError("Network forbidden in offline retry tests")))
        self.stack.enter_context(mock.patch.object(cm, "load_requests_module", side_effect=AssertionError("Network clients forbidden in offline retry tests")))
        self.stack.enter_context(mock.patch.object(cm, "configured_provider", return_value=(PRIMARY, "primary")))
        self.sleep = self.stack.enter_context(mock.patch.object(cm.time, "sleep", return_value=None))

    def exercise(self, route, outcomes, *, expected_attempts, expected_sleeps, fails=False, max_attempts=None):
        """Count actual low-level submissions and snapshot all visual inputs."""
        payload = {"model": "offline-image-model", "prompt": "adult covered fashion portrait", "size": "1024x1024"}
        multipart = None
        if route == "edit":
            multipart = {"fields": copy.deepcopy(payload), "files": [{"field": "image", "image": REFERENCE}]}
        elif route == "responses":
            payload = {"model": "offline-controller", "reasoning": {"effort": "ultra"}, "stream": True,
                       "input": [{"role": "user", "content": [{"type": "input_text", "text": "adult covered fashion portrait"},
                                                                 {"type": "input_image", "image_url": REFERENCE.data_url()}]}],
                       "tools": [{"type": "image_generation", "model": "offline-image-model"}]}
        original_payload = copy.deepcopy(payload)
        original_multipart = copy.deepcopy(multipart)
        submissions = []

        def fake_compat(provider, command, endpoint, submitted, timeout, multipart=None):
            self.assertEqual(command, route)
            return submit(provider, submitted, multipart, endpoint, "images_multipart" if multipart else "images_json")

        def fake_responses(provider, submitted, timeout):
            return submit(provider, submitted, None, "/responses", "responses_stream")

        def submit(provider, submitted, submitted_multipart, endpoint, transport):
            self.assertEqual(provider, PRIMARY)
            submissions.append((copy.deepcopy(submitted), copy.deepcopy(submitted_multipart), endpoint, transport))
            index = len(submissions) - 1
            outcome = outcomes[min(index, len(outcomes) - 1)]
            if isinstance(outcome, BaseException):
                raise outcome
            return cm.ProviderRequestResult(copy.deepcopy(outcome), endpoint, transport, provider.base_url + endpoint)

        function = cm.request_responses_with_retry if route == "responses" else cm.request_with_retry
        args = (payload, 1) if route == "responses" else (route, payload, 1, multipart)
        kwargs = {} if max_attempts is None else {"max_attempts": max_attempts}
        self.sleep.reset_mock()
        target = "request_responses_provider" if route == "responses" else "request_provider"
        low_level = fake_responses if route == "responses" else fake_compat
        with mock.patch.object(cm, target, side_effect=low_level), \
             mock.patch.object(cm, "format_provider_failures", wraps=cm.format_provider_failures) as format_failures:
            if fails:
                with self.assertRaises(SystemExit):
                    function(*args, **kwargs)
                self.assertTrue(format_failures.called)
                errors = format_failures.call_args.args[0]
            else:
                result = function(*args, **kwargs)
                self.assertEqual(result[0], IMAGE_DATA)
                self.assertEqual(result[1], PRIMARY)
                errors = result[-1]
                self.assertFalse(format_failures.called)
        self.assertEqual(len(submissions), expected_attempts, submissions)
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], expected_sleeps)
        for submitted, submitted_multipart, endpoint, transport in submissions:
            self.assertEqual(submitted, original_payload)
            self.assertEqual(submitted_multipart, original_multipart)
            self.assertEqual(endpoint, "/responses" if route == "responses" else "/images/edits" if route == "edit" else "/images/generations")
            self.assertEqual(transport, "responses_stream" if route == "responses" else "images_multipart" if route == "edit" else "images_json")
            if route == "edit":
                self.assertEqual(submitted_multipart["files"][0]["image"].data, REFERENCE.data)
        self.assertEqual(payload, original_payload)
        self.assertEqual(multipart, original_multipart)
        self.assertEqual([error["attempt"] for error in errors], list(range(1, expected_attempts + (1 if fails else 0))))
        return errors

    def test_transient_failure_exhausts_three_actual_submissions_and_retains_all_attempts(self):
        for route in ROUTES:
            for status in (408, 429, 500, 502, 503, 504):
                with self.subTest(route=route, status=status):
                    self.exercise(route, [transient(status)], expected_attempts=3, expected_sleeps=[5, 15], fails=True)

    def test_second_and_third_attempt_success_preserve_payload_and_references(self):
        for route in ROUTES:
            for success_at in (2, 3):
                with self.subTest(route=route, success_at=success_at):
                    self.exercise(route, [transient()] * (success_at - 1) + [IMAGE_DATA], expected_attempts=success_at,
                                  expected_sleeps=[5, 15][:success_at - 1])

    def test_connection_failure_retries_boundedly(self):
        error = cm.ImageApiError("connection reset before response", diagnostics={"error_kind": "responses_url_error", "exception_type": "ConnectionResetError"})
        for route in ROUTES:
            with self.subTest(route=route):
                self.exercise(route, [error, IMAGE_DATA], expected_attempts=2, expected_sleeps=[5])

    def test_actual_terminal_sse_image_failure_retries_without_claiming_a_cause(self):
        for status in ("completed", "failed", "cancelled"):
            error = sse_no_image_error(status=status)
            evidence = error.diagnostics["sse_terminal_evidence"]
            self.assertEqual(evidence["response_status"], status)
            self.assertEqual(evidence["image_tool_status_counts"].get("failed"), 1)
            self.assertEqual(evidence["image_tool_result_present_count"], 0)
            self.assertEqual(evidence["rejection_state"], "unknown")
            for route in ROUTES:
                with self.subTest(route=route, status=status):
                    self.exercise(route, [error, IMAGE_DATA], expected_attempts=2, expected_sleeps=[5])

    def test_terminal_unknown_sse_failure_exhausts_the_bound(self):
        error = sse_no_image_error()
        for route in ROUTES:
            with self.subTest(route=route):
                self.exercise(route, [error], expected_attempts=3, expected_sleeps=[5, 15], fails=True)

    def test_explicit_refusal_stops_first_or_after_one_transient(self):
        error = sse_no_image_error(refusal="This request is refused.")
        for route in ROUTES:
            for preceding in ([], [transient()]):
                with self.subTest(route=route, preceding=bool(preceding)):
                    count = len(preceding) + 1
                    self.exercise(route, preceding + [error], expected_attempts=count,
                                  expected_sleeps=[5] if preceding else [], fails=True)

    def test_refusal_evidence_takes_precedence_over_5xx(self):
        errors = [sse_no_image_error(http_status=503, refusal="This request is refused."),
                  cm.ImageApiError("blocked", status=503, raw='{"error":{"code":"content_policy_violation"}}')]
        for route in ROUTES:
            for index, error in enumerate(errors):
                with self.subTest(route=route, error=index):
                    self.exercise(route, [error], expected_attempts=1, expected_sleeps=[], fails=True)

    def test_possible_text_rejection_is_not_retried_as_unknown(self):
        error = sse_no_image_error(text="I can't generate this image.")
        self.assertEqual(error.diagnostics["sse_terminal_evidence"]["rejection_state"], "possible_text_rejection")
        for route in ROUTES:
            with self.subTest(route=route):
                self.exercise(route, [error], expected_attempts=1, expected_sleeps=[], fails=True)

    def test_refusal_event_name_without_json_type_stops(self):
        prefix = 'event: response.refusal.done\ndata: {"refusal":"Request refused."}\n\n'
        error = sse_no_image_error(prefix=prefix)
        for route in ROUTES:
            with self.subTest(route=route):
                self.exercise(route, [error], expected_attempts=1, expected_sleeps=[], fails=True)

    def test_top_level_sse_error_code_stops(self):
        prefix = 'event: error\ndata: {"code":"content_policy_violation"}\n\n'
        error = sse_no_image_error(prefix=prefix)
        for route in ROUTES:
            with self.subTest(route=route):
                self.exercise(route, [error], expected_attempts=1, expected_sleeps=[], fails=True)

    def test_nonterminal_sse_and_partial_reads_never_resubmit(self):
        for partial in (False, True):
            error = sse_no_image_error(status=None, partial=partial)
            for route in ROUTES:
                with self.subTest(route=route, partial=partial):
                    self.exercise(route, [error], expected_attempts=1, expected_sleeps=[], fails=True)

    def test_json_terminal_failed_zero_image_is_classified_inside_retry_loop(self):
        data = failed_response("failed")
        for route in ROUTES:
            with self.subTest(route=route):
                self.exercise(route, [data, IMAGE_DATA], expected_attempts=2, expected_sleeps=[5])

    def test_json_explicit_refusal_stops_before_another_submission(self):
        data = failed_response("completed", refusal="Request refused.")
        for route in ROUTES:
            with self.subTest(route=route):
                self.exercise(route, [data], expected_attempts=1, expected_sleeps=[], fails=True)

    def test_parameter_auth_and_other_nontransient_4xx_stop(self):
        for route in ROUTES:
            for status in (400, 401, 403, 404, 409, 422):
                with self.subTest(route=route, status=status):
                    self.exercise(route, [cm.ImageApiError("invalid request or authentication", status=status)],
                                  expected_attempts=1, expected_sleeps=[], fails=True)

    def test_success_does_not_retry_or_sleep(self):
        for route in ROUTES:
            with self.subTest(route=route):
                self.exercise(route, [IMAGE_DATA], expected_attempts=1, expected_sleeps=[])

    def test_explicit_one_attempt_cap_disables_resubmission(self):
        for route in ROUTES:
            with self.subTest(route=route):
                self.exercise(route, [transient()], expected_attempts=1, expected_sleeps=[], fails=True, max_attempts=1)

    def test_cli_rejects_attempt_limits_outside_one_to_five(self):
        for command in ("generate", "edit"):
            for value in ("0", "6", "-1"):
                argv = ["cm_image_gen.py", command, "--prompt", "offline", "--max-attempts", value]
                if command == "edit":
                    argv += ["--image", str(REFERENCE.path)]
                with self.subTest(command=command, value=value), \
                     mock.patch.object(sys, "argv", argv), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as exit_info:
                        cm.main()
                    self.assertEqual(exit_info.exception.code, 2)

    def test_cli_passes_valid_limits_and_default_to_operation(self):
        for command in ("generate", "edit"):
            for value in (None, "1", "2", "3", "4", "5"):
                argv = ["cm_image_gen.py", command, "--prompt", "offline"]
                if command == "edit":
                    argv += ["--image", str(REFERENCE.path)]
                if value is not None:
                    argv += ["--max-attempts", value]
                with self.subTest(command=command, value=value), \
                     mock.patch.object(sys, "argv", argv), \
                     mock.patch.object(cm, command, return_value=0) as operation:
                    self.assertEqual(cm.main(), 0)
                    self.assertEqual(operation.call_args.args[0].max_attempts, 3 if value is None else int(value))


if __name__ == "__main__":
    unittest.main()
