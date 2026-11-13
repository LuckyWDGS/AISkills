"""Job ledger, provenance sidecars, --prompt-file and `recover` (offline)."""
import base64
import contextlib
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
import cm_job_ledger as jobs  # noqa: E402

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is optional for the CLI
    Image = None


def png_bytes(size=(32, 32)) -> bytes:
    if Image is None:
        raise unittest.SkipTest("Pillow required")
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


class JobLedgerTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.out = self.root / "out"
        self.stack.enter_context(mock.patch.object(cm, "codex_home", return_value=self.root))
        self.stack.enter_context(mock.patch.dict(os.environ, {}, clear=True))
        self.stack.enter_context(
            mock.patch.object(cm.urllib.request, "urlopen", side_effect=AssertionError("Network forbidden"))
        )
        self.stack.enter_context(mock.patch.object(cm, "retry_delay", lambda attempt: None))
        self.stack.enter_context(mock.patch.object(cm, "model_catalog_check", return_value={"ok": True}))
        (self.root / "config.toml").write_text(
            'model_provider = "sub2api"\n[model_providers.sub2api]\nbase_url = "https://sub2api.example/v1"\n'
            'env_key = "SUB2API_TEST_KEY"\n',
            encoding="utf-8",
        )
        os.environ["SUB2API_TEST_KEY"] = "test-only-not-a-real-key"

    def run_cli(self, *argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["cm_image_gen.py", *argv]), contextlib.redirect_stdout(
            stdout
        ), contextlib.redirect_stderr(stderr):
            try:
                code = cm.main()
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def only_ledger(self) -> dict:
        files = list((self.out / jobs.JOB_DIR_NAME).glob("*.json"))
        self.assertEqual(len(files), 1)
        return json.loads(files[0].read_text(encoding="utf-8")) | {"_path": str(files[0])}

    def image_result(self):
        data = {"created": 1, "data": [{"b64_json": base64.b64encode(png_bytes()).decode("ascii")}]}
        return cm.ProviderRequestResult(data, "/images/generations", "images_json",
                                        "https://sub2api.example/v1/images/generations")

    def test_success_writes_ledger_sidecar_and_prompt_file(self):
        prompt_file = self.root / "p01.txt"
        prompt_file.write_text("﻿第一页：女孩在雨夜便利店门口\n", encoding="utf-8")
        with mock.patch.object(cm, "request_provider", return_value=self.image_result()):
            code, stdout, stderr = self.run_cli(
                "generate", "--prompt-file", str(prompt_file), "--out-dir", str(self.out), "--filename", "p01"
            )
        self.assertEqual(code, 0, stdout + stderr)
        result = json.loads(stdout)
        self.assertIn("cm-imagegen job ledger:", stderr)
        ledger = self.only_ledger()
        self.assertEqual(ledger["state"], "completed")
        self.assertEqual(ledger["prompt"], "第一页：女孩在雨夜便利店门口")
        self.assertEqual(ledger["submissions"], 1)
        image = Path(result["paths"][0])
        self.assertEqual(image.name, "p01.png")
        sidecar = json.loads((image.parent / "p01.png.cm.json").read_text(encoding="utf-8"))
        self.assertEqual(sidecar["output"]["sha256"], jobs.sha256_file(image))
        self.assertEqual(sidecar["prompt"], ledger["prompt"])
        for private in ("base_url", "request_url", "poll_candidates", "pid"):
            self.assertNotIn(private, sidecar)
        self.assertNotIn("test-only-not-a-real-key", json.dumps(sidecar) + json.dumps(ledger))
        self.assertEqual(result["sidecars"], [str((image.parent / "p01.png.cm.json").resolve())])

        code, stdout, _ = self.run_cli("recover", "--job-file", ledger["_path"])
        report = json.loads(stdout)
        self.assertEqual((code, report["recovery_status"]), (0, "already_completed"))

    def test_prompt_and_prompt_file_are_exclusive(self):
        code, _, stderr = self.run_cli("generate", "--prompt", "a", "--prompt-file", "b.txt")
        self.assertEqual(code, 2)
        self.assertIn("not allowed with argument", stderr)

    def test_killed_process_leaves_in_flight_ledger(self):
        with mock.patch.object(cm, "request_provider", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                with mock.patch.object(sys, "argv", ["cm_image_gen.py", "generate", "--prompt", "x",
                                                     "--out-dir", str(self.out)]), \
                        contextlib.redirect_stderr(io.StringIO()):
                    cm.main()
        self.assertIsNone(jobs.active())
        ledger = self.only_ledger()
        self.assertEqual(ledger["state"], "submitting")
        code, stdout, _ = self.run_cli("recover", "--job-file", ledger["_path"])
        report = json.loads(stdout)
        self.assertEqual((code, report["recovery_status"]), (1, "in_flight"))
        self.assertIn("Do not resubmit", report["resubmit_advice"])

        code, stdout, _ = self.run_cli("recover", "--out-dir", str(self.out))
        listing = json.loads(stdout)
        self.assertEqual(code, 0)
        self.assertEqual(len(listing["unfinished"]), 1)

    def test_final_timeout_is_uncertain_and_400_is_failed(self):
        cases = (
            (cm.ImageApiError("The read operation timed out", provider="sub2api"), "uncertain"),
            (cm.ImageApiError("HTTP 400 bad size", status=400, provider="sub2api"), "failed"),
        )
        for error, expected in cases:
            with self.subTest(expected=expected):
                out = self.root / f"out-{expected}"
                with mock.patch.object(cm, "request_provider", side_effect=error):
                    code, _, stderr = self.run_cli(
                        "generate", "--prompt", "x", "--out-dir", str(out), "--max-attempts", "2"
                    )
                self.assertNotEqual(code, 0)
                ledger_file = next((out / jobs.JOB_DIR_NAME).glob("*.json"))
                ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
                self.assertEqual(ledger["state"], expected)
                self.assertIn(f"cm-imagegen job state: {expected}", stderr)
                expected_submissions = 2 if expected == "uncertain" else 1
                self.assertEqual(ledger["submissions"], expected_submissions)
                code, stdout, _ = self.run_cli("recover", "--job-file", str(ledger_file))
                self.assertEqual(json.loads(stdout)["recovery_status"], expected)

    def make_pending_ledger(self, base_url="https://sub2api.example/v1") -> Path:
        ledger = jobs.JobLedger.start(
            self.out, command="generate", filename="p02", size="1024x1024", prompt="x", started_epoch=0
        )
        ledger.update(
            state="pending",
            endpoint="/images/generations",
            request_url="https://sub2api.example/v1/images/generations",
            poll_candidates=["https://sub2api.example/v1/images/generations/job_1"],
            base_url=base_url,
        )
        return ledger.path

    def test_recover_polls_pending_job_and_saves_outputs(self):
        path = self.make_pending_ledger()
        polled = {"data": [{"b64_json": base64.b64encode(png_bytes()).decode("ascii")}]}
        with mock.patch.object(cm, "request_poll_url", return_value=polled) as poll:
            code, stdout, _ = self.run_cli("recover", "--job-file", str(path))
        report = json.loads(stdout)
        self.assertEqual(report["recovery_status"], "recovered", stdout)
        self.assertEqual(poll.call_args.args[1], "https://sub2api.example/v1/images/generations/job_1")
        self.assertTrue(Path(report["paths"][0]).name.startswith("p02"))
        self.assertTrue(Path(report["sidecars"][0]).is_file())
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["state"], "completed")
        self.assertIn(code, (0, 1))  # size warning only; 32px test image vs 1024 request is non-strict

    def test_recover_refuses_other_provider_and_no_poll_skips_network(self):
        path = self.make_pending_ledger(base_url="https://other.example/v1")
        with mock.patch.object(cm, "request_poll_url", side_effect=AssertionError("must not poll")):
            code, stdout, _ = self.run_cli("recover", "--job-file", str(path))
        self.assertEqual((code, json.loads(stdout)["recovery_status"]), (1, "provider_mismatch"))

        path = self.make_pending_ledger()
        with mock.patch.object(cm, "request_poll_url", side_effect=AssertionError("must not poll")):
            code, stdout, _ = self.run_cli("recover", "--job-file", str(path), "--no-poll")
        self.assertEqual((code, json.loads(stdout)["recovery_status"]), (1, "pending"))

    def test_no_job_record_disables_ledger(self):
        with mock.patch.object(cm, "request_provider", return_value=self.image_result()):
            code, stdout, _ = self.run_cli("generate", "--prompt", "x", "--out-dir", str(self.out), "--no-job-record")
        self.assertEqual(code, 0)
        self.assertFalse((self.out / jobs.JOB_DIR_NAME).exists())
        self.assertNotIn("sidecars", json.loads(stdout))


if __name__ == "__main__":
    unittest.main()
