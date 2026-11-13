"""Offline HTTP-boundary and decoded-media tests; no service quota is used."""

import base64
import contextlib
from email.parser import BytesParser
from email.policy import default
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cm_image_gen as cm  # noqa: E402
import cm_image_formats as formats
from test_cm_image_gen import FakeResponse


PROVIDER = cm.ImageApiProvider("offline", "https://offline.example/v1", "offline-key")
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024"><path d="M10 10H500V500Z" fill="blue"/></svg>'


def raster(fmt="PNG", size=(1024, 1024)):
    out = io.BytesIO()
    Image.new("RGB", size, "blue").save(out, format=fmt)
    return out.getvalue()


def animation(count=4, duration=200):
    images = []
    for index in range(count):
        frame = Image.new("RGB", (128, 128), "white")
        ImageDraw.Draw(frame).rectangle((index * 20, 10, index * 20 + 15, 80), fill="blue")
        images.append(frame)
    out = io.BytesIO()
    images[0].save(out, format="GIF", save_all=True, append_images=images[1:], duration=duration, loop=0)
    return out.getvalue()


class MediaRequestTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.source = self.root / "source.png"
        self.source.write_bytes(raster())
        self.stack.enter_context(mock.patch.object(cm, "configured_provider", return_value=(PROVIDER, "offline")))
        self.stack.enter_context(mock.patch.object(cm, "controller_defaults", return_value={}))
        self.catalog = self.stack.enter_context(mock.patch.object(cm, "model_catalog_check", return_value={"ok": True}))
        self.network = self.stack.enter_context(mock.patch.object(cm.urllib.request, "urlopen", side_effect=AssertionError("Unexpected network")))

    def call(self, operation, options, raw=None, *, sse=None):
        response = sse if sse is not None else json.dumps({"data": [{"b64_json": base64.b64encode(raw).decode()}]}).encode()
        self.network.side_effect = None
        self.network.return_value = FakeResponse([response], headers={"content-type": "text/event-stream" if sse else "application/json"})
        argv = ["cm_image_gen.py", operation, "--api", "images", "--prompt", "a blue mug", "--out-dir", str(self.root / "out"),
                "--max-attempts", "1", *options]
        if operation == "edit":
            argv += ["--image", str(self.source)]
        output = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
            code = cm.main()
        request = self.network.call_args.args[0]
        parts = []
        if operation == "edit":
            envelope = b"Content-Type: " + request.get_header("Content-type").encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + request.data
            parts = list(BytesParser(policy=default).parsebytes(envelope).iter_parts())
            fields = {p.get_param("name", header="content-disposition"): p.get_payload(decode=True).decode()
                      for p in parts if not p.get_filename()}
        else:
            fields = json.loads(request.data)
        return code, json.loads(output.getvalue()), fields, parts

    def test_square_landscape_and_portrait_are_preserved_at_wire_and_file(self):
        for width, height in ((1024, 1024), (1536, 1024), (1024, 1536)):
            size = f"{width}x{height}"
            with self.subTest(size=size):
                code, result, fields, _ = self.call("generate", ["--size", size, "--require-exact-size", "--output-format", "png"], raster(size=(width, height)))
                self.assertEqual(code, 0)
                self.assertEqual(fields["size"], size)
                self.assertEqual(result["output_dimensions"], [size])
                self.assertTrue(result["size_verified"])
                self.assertNotIn("response_format", fields)

    def test_gif_json_and_multipart_fields_and_animation(self):
        for operation in ("generate", "edit"):
            with self.subTest(operation=operation):
                code, result, fields, _ = self.call(operation, ["--size", "auto", "--output-format", "gif", "--frame-count", "4", "--frame-duration-ms", "200"], animation())
                self.assertEqual(code, 0)
                self.assertEqual(int(fields["frame_count"]), 4)
                self.assertEqual(int(fields["frame_duration_ms"]), 200)
                self.assertEqual(fields["quality"], "max")
                self.assertEqual(fields["complexity"], "high")
                self.assertTrue(result["paths"][0].endswith(".gif"))
                self.assertEqual(result["media_outputs"][0]["distinct_frames"], 4)
                self.assertEqual(result["media_outputs"][0]["total_duration_ms"], 800)

    def test_svg_author_model_is_separate_and_actual_extension_wins(self):
        code, result, fields, _ = self.call("generate", ["--output-format", "svg", "--svg-model", "gpt-6.1-sol",
            "--svg-reasoning", "max", "--filename", "logo.png", "--require-exact-size"], SVG)
        self.assertEqual(code, 0)
        self.assertEqual(fields["model"], "gpt-image-2.6-sunburst")
        self.assertEqual(fields["n"], 1)
        self.assertEqual(fields["svg"], {"model": "gpt-6.1-sol", "reasoning": {"effort": "max"}})
        self.assertTrue(result["paths"][0].endswith(".svg"))
        self.assertEqual(Path(result["paths"][0]).read_bytes(), SVG)

    def test_gateway_png_downgrade_is_failed_and_kept_as_png(self):
        for fmt in ("gif", "svg"):
            with self.subTest(fmt=fmt):
                code, result, _, _ = self.call("generate", ["--output-format", fmt, "--filename", f"result.{fmt}"], raster())
                self.assertEqual(code, 1)
                self.assertEqual(result["error_kind"], "image_media_mismatch")
                self.assertTrue(result["paths"][0].endswith(".png"))
                self.assertEqual(result["media_validation_warnings"][0]["warning"], "output_format_mismatch")

    def test_compression_and_stream_boolean_reach_edit_wire(self):
        code, _, fields, _ = self.call("edit", ["--output-format", "webp", "--output-compression", "80",
            "--stream", "--partial-images", "0", "--moderation", "auto", "--safety-identifier", "hashed-user"], raster("WEBP"))
        self.assertEqual(code, 0)
        self.assertEqual(fields["output_compression"], "80")
        self.assertEqual(fields["stream"], "true")
        self.assertEqual(fields["partial_images"], "0")
        self.assertEqual(fields["moderation"], "auto")
        self.assertEqual(fields["safety_identifier"], "hashed-user")

    def test_markup_upload_is_separate_and_unchanged(self):
        overlay = Image.new("RGBA", (1024, 1024))
        ImageDraw.Draw(overlay).ellipse((100, 100, 500, 500), outline="red", width=10)
        path = self.root / "markup.png"
        overlay.save(path)
        code, _, _, parts = self.call("edit", ["--markup", str(path)], raster())
        self.assertEqual(code, 0)
        uploads = {p.get_param("name", header="content-disposition"): p.get_payload(decode=True) for p in parts if p.get_filename()}
        self.assertEqual(uploads, {"image": self.source.read_bytes(), "markup": path.read_bytes()})

    def test_invalid_markup_dimensions_or_no_transparency_stops_before_network(self):
        for size, color in (((128, 128), (0, 0, 0, 0)), ((1024, 1024), (0, 0, 0, 255))):
            path = self.root / "bad-markup.png"
            Image.new("RGBA", size, color).save(path)
            argv = ["cm_image_gen.py", "edit", "--api", "images", "--prompt", "recolor", "--image", str(self.source), "--markup", str(path)]
            with mock.patch.object(sys, "argv", argv), self.assertRaises(SystemExit):
                cm.main()
        self.network.assert_not_called()
        self.catalog.assert_not_called()

    def test_incompatible_options_fail_before_catalog_and_post(self):
        cases = [
            ["--output-format", "gif", "--stream"], ["--output-format", "gif", "--frame-count", "17"],
            ["--output-format", "gif", "--frame-duration-ms", "10"], ["--frame-count", "4"],
            ["--output-format", "svg", "--n", "2"], ["--output-format", "svg", "--svg-reasoning", "max"],
            ["--output-format", "svg", "--output-compression", "100"], ["--output-format", "png", "--output-compression", "100"],
            ["--output-format", "jpeg", "--output-compression", "101"], ["--partial-images", "1"],
            ["--stream", "--partial-images", "4"], ["--api", "responses", "--output-format", "gif"],
            ["--n", "11"], ["--size", "1023x1024"], ["--size", "4096x1024"], ["--size", "auto", "--require-exact-size"],
        ]
        for options in cases:
            with self.subTest(options=options), mock.patch.object(sys, "argv", ["cm_image_gen.py", "generate", "--api", "images", "--prompt", "test", *options]):
                with self.assertRaises(SystemExit):
                    cm.main()
        self.network.assert_not_called()
        self.catalog.assert_not_called()

    def test_svg_edit_is_blocked_without_service_submission(self):
        argv = ["cm_image_gen.py", "edit", "--api", "images", "--prompt", "edit", "--image", str(self.source), "--output-format", "svg"]
        with mock.patch.object(sys, "argv", argv), self.assertRaisesRegex(SystemExit, "guide and edit schema disagree"):
            cm.main()
        self.network.assert_not_called()

    def test_stream_intermediate_is_excluded_from_saved_final(self):
        preview = base64.b64encode(raster(size=(64, 64))).decode()
        final = base64.b64encode(raster()).decode()
        sse = ("event: image_generation.partial_image\ndata: " + json.dumps({"b64_json": preview}) + "\n\n"
               "event: image_generation.completed\ndata: " + json.dumps({"b64_json": final}) + "\n\n").encode()
        code, result, fields, _ = self.call("generate", ["--stream", "--partial-images", "1", "--require-exact-size"], sse=sse)
        self.assertEqual(code, 0)
        self.assertTrue(fields["stream"])
        self.assertEqual(len(result["paths"]), 1)
        self.assertEqual(result["output_dimensions"], ["1024x1024"])

    def test_only_preview_is_not_a_completed_image_and_not_retryable(self):
        sse = 'event: image_generation.partial_image\ndata: {"b64_json":"ZmFrZQ=="}\n\n'
        with self.assertRaises(cm.ImageApiError) as error:
            cm.decode_json_or_sse_response(provider=PROVIDER, request_url=PROVIDER.base_url + "/images/generations", status=200,
                headers={"content-type": "text/event-stream"}, raw_bytes=sse.encode())
        self.assertFalse(cm.should_retry_primary_transport(error.exception))

    def test_doctor_has_svg_options_and_redacts_identifier(self):
        argv = ["cm_image_gen.py", "doctor", "--api", "images", "--operation", "generate", "--output-format", "svg",
                "--svg-model", "gpt-6.1-sol", "--svg-reasoning", "max", "--safety-identifier", "private-id", "--show-payload-shape"]
        out = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
            self.assertEqual(cm.main(), 0)
        self.assertNotIn("private-id", out.getvalue())
        fields = json.loads(out.getvalue())["payload_shapes"][0]["json_fields"]
        self.assertEqual(fields["svg"]["reasoning"]["effort"], "max")
        self.network.assert_not_called()


class DecodedMediaTests(unittest.TestCase):
    def test_valid_svg_and_viewbox_without_pixels(self):
        self.assertTrue(formats.inspect_media(SVG)["readable"])
        viewbox = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><path d="M0 0H100"/></svg>'
        self.assertIsNone(cm.parse_image_dimensions(viewbox))
        self.assertEqual(formats.inspect_media(viewbox)["view_box"], [0, 0, 100, 50])

    def test_nonvector_svg_content_is_not_treated_as_success(self):
        for child in ('<script>alert(1)</script>', '<image href="data:image/png;base64,xxx"/>', '<use href="https://example.com/a.svg"/>'):
            with self.subTest(child=child):
                self.assertFalse(formats.inspect_media(('<svg xmlns="http://www.w3.org/2000/svg">' + child + '</svg>').encode())["readable"])

    def test_gif_decoding_timing_and_still_gif_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "motion.gif"
            path.write_bytes(animation())
            args = type("Args", (), {"output_format": "gif", "frame_count": 4, "frame_duration_ms": 200})()
            self.assertFalse(formats.validate_media_outputs([path], args)["media_validation_failed"])
            path.write_bytes(raster("GIF", (128, 128)))
            self.assertTrue(formats.validate_media_outputs([path], args)["media_validation_failed"])

    def test_direct_binary_gif_and_svg_are_decoded(self):
        for raw in (animation(), SVG):
            result = cm.decode_json_or_sse_response(provider=PROVIDER, request_url=PROVIDER.base_url, status=200, headers={}, raw_bytes=raw)
            self.assertEqual(base64.b64decode(result["data"][0]["b64_json"]), raw)


if __name__ == "__main__":
    unittest.main()
