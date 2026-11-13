"""Offline GIF workflow decisions from actual ledger-shaped evidence."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import contextlib
import io

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cm_gif_route as route


def failed(message="GIF output is not enabled for this request.", status=400):
    return {"state": "failed", "api": "images", "output_format": "gif", "attempts": [
        {"status": status, "error_kind": "http_error_response", "error": message, "pending_image_result": False}]}


class GifRouteTests(unittest.TestCase):
    def test_explicit_entitlement_failure_allows_composition(self):
        result = route.decide_native_job(failed())
        self.assertEqual(result["action"], "local_composition")
        self.assertTrue(result["fallback_allowed"])
        self.assertFalse(result["network_call_performed"])

    def test_native_success_is_kept(self):
        record = {"state": "completed", "ok": True, "api": "images", "output_format": "gif", "outputs": [{"path": "native.gif"}]}
        self.assertEqual(route.decide_native_job(record)["action"], "use_native_output")

    def test_native_only_prevents_fallback(self):
        self.assertFalse(route.decide_native_job(failed(), native_only=True)["fallback_allowed"])

    def test_generic_parameter_network_and_service_errors_do_not_fallback(self):
        cases = [
            ("GIF frame_count is not valid", 400), ("Unknown parameter frame_duration_ms", 400),
            ("GIF frame duration is not supported", 400), ("Bad image size", 422),
            ("Service unavailable", 503), ("GIF output is not enabled", 500), ("rate limit", 429),
            ("Invalid API key", 401), ("Forbidden", 403),
        ]
        for message, status in cases:
            with self.subTest(message=message, status=status):
                self.assertEqual(route.decide_native_job(failed(message, status))["action"], "stop")

    def test_policy_or_quota_evidence_wins_over_format_error(self):
        for message in ("GIF output is not supported; content_policy_violation", "GIF output is not enabled; insufficient_quota"):
            self.assertEqual(route.decide_native_job(failed(message))["action"], "stop")

    def test_running_and_uncertain_native_jobs_require_recovery(self):
        for state in route.ACTIVE_STATES:
            record = failed()
            record["state"] = state
            self.assertEqual(route.decide_native_job(record)["action"], "recover")

    def test_pending_and_read_error_require_recovery_even_when_marked_failed(self):
        for field, value in (("pending_image_result", True), ("error_kind", "images_read_error")):
            record = failed()
            record["attempts"][-1][field] = value
            self.assertEqual(route.decide_native_job(record)["action"], "recover")

    def test_wrong_format_result_requires_inspection(self):
        record = failed()
        record.update(state="completed", ok=False, error_kind="image_media_mismatch", outputs=[{"path": "still.png"}])
        self.assertEqual(route.decide_native_job(record)["action"], "stop")

    def test_old_attempt_or_prompt_cannot_trigger_fallback(self):
        record = failed()
        record["attempts"].append({"status": 503, "error": "Temporary failure"})
        record["prompt"] = "GIF output is not supported"
        self.assertEqual(route.decide_native_job(record)["action"], "stop")
        record["attempts"] = []
        self.assertEqual(route.decide_native_job(record)["action"], "stop")

    def test_only_native_images_jobs_are_classified(self):
        for key, value in (("api", "responses"), ("output_format", "png"), ("state", "unknown")):
            record = failed()
            record[key] = value
            self.assertEqual(route.decide_native_job(record)["action"], "stop")

    def test_cli_emits_offline_decision_without_raw_error_or_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "job.json"
            record = failed()
            record["base_url"] = "https://private-provider.example/v1"
            path.write_text(json.dumps(record), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = route.main(["--job-file", str(path)])
            self.assertEqual(code, 0)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["fallback_allowed"])
            self.assertNotIn("private-provider", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
