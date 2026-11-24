#!/usr/bin/env python3
"""Render frames of a Level Sequence to PNG to answer a named visual question (framing, readability).

    python scripts/sequence_render.py /Game/Cinematics/LS_Intro --allow-editor-ui --project MyGame --frames 0,90,180 --out <dir> --question "主角是否在画面三分线上"

Each frame is rendered with the engine's built-in Level Sequence capture (SequencerTools.render_movie,
deprecated in 5.8 but working without the Movie Render Queue plugin) at the sequence's own frame
rate, after --preroll frames (default 8) so motion blur and temporal AA match playback; only the
requested frames are kept. --range START END renders a contiguous range instead. Completion comes
from the capture's callback plus validated files in a unique run directory. Files alone never
prove completion. This legacy capture may open a render viewport: --allow-editor-ui is required.
This is preview evidence: final-quality output goes through Movie Render Queue when the project
has the MovieRenderPipeline plugin enabled. Look at every image and report the answer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

SCHEMA_VERSION = "sequence_render/2"
RENDER_SCRIPT = r'''
import json, unreal
def _codex_render():
    capture = unreal.AutomatedLevelSequenceCapture()
    capture.level_sequence_asset = unreal.SoftObjectPath(__SEQ__)
    settings = capture.settings
    settings.output_directory = unreal.DirectoryPath(__OUT__)
    settings.output_format = "{sequence}.{frame}"
    settings.resolution = unreal.CaptureResolution(__W__, __H__)
    settings.use_relative_frame_numbers = False
    settings.overwrite_existing = True
    # The capture defaults to 24 fps; frame numbers would then map to the wrong sequence time.
    rate = unreal.load_asset(__SEQ__.split(".")[0]).get_display_rate()
    settings.use_custom_frame_rate = True
    settings.custom_frame_rate = unreal.FrameRate(rate.numerator, rate.denominator)
    capture.set_image_capture_protocol_type(unreal.load_class(None, "/Script/MovieSceneCapture.ImageSequenceProtocol_PNG"))
    capture.use_custom_start_frame = True
    capture.custom_start_frame = unreal.FrameNumber(__START__)
    capture.use_custom_end_frame = True
    capture.custom_end_frame = unreal.FrameNumber(__END__)
    def done(success):
        unreal.log("__TOKEN__ " + str(success))
    callback = unreal.OnRenderMovieStopped()
    callback.bind_callable(done)
    # Keep the delegate alive after this remote script returns, or it is collected and never fires.
    unreal._codex_render_callbacks = getattr(unreal, "_codex_render_callbacks", [])[-8:] + [(done, callback, capture)]
    print("CODEX_SEQ " + json.dumps({"started": unreal.SequencerTools.render_movie(capture, callback),
                                     "mrq": hasattr(unreal, "MoviePipelineQueueSubsystem")}))
_codex_render()
'''


def valid_pngs(paths: list[Path], size: tuple[int, int]) -> bool:
    from PIL import Image
    try:
        for path in paths:
            with Image.open(path) as image:
                if image.format != "PNG" or image.size != size:
                    return False
                image.load()
        return bool(paths)
    except (OSError, ValueError):
        return False


def render_range(editor, sequence: str, out: Path, start: int, end: int, size: tuple[int, int], timeout: float,
                 *, allow_editor_ui: bool = False) -> dict:
    if not allow_editor_ui:
        raise RuntimeError("Legacy capture may open a viewport; explicit --allow-editor-ui is required. No render started.")
    if start >= end or min(size) <= 0 or timeout <= 0:
        raise ValueError("render needs start < end, positive dimensions and timeout")
    token = "CODEX_RENDER_" + uuid.uuid4().hex[:10]
    run_out = out / token
    run_out.mkdir(parents=True, exist_ok=False)
    path = sequence.split(".")[0]
    script = (RENDER_SCRIPT.replace("__SEQ__", json.dumps(f"{path}.{path.rsplit('/', 1)[-1]}"))
              .replace("__OUT__", json.dumps(run_out.as_posix())).replace("__W__", str(size[0])).replace("__H__", str(size[1]))
              .replace("__START__", str(start)).replace("__END__", str(end)).replace("__TOKEN__", token))
    started = editor.python(script, gap="No MCP render tool in the inspected UE 5.8.4 Sequencer toolsets; legacy preview capture only.")
    base = {"start": start, "end": end, "run_directory": str(run_out), "token": token, "images": []}
    if not started.get("started"):
        return {**base, "ok": False, "status": "not_started", "error": "render_movie did not start (PIE running?)"}
    name = path.rsplit("/", 1)[-1]
    expected = [run_out / f"{name}.{frame:04d}.png" for frame in range(start, end)]
    deadline = time.monotonic() + timeout
    completed = False
    while time.monotonic() < deadline:
        rows = editor.call("LogsToolset", "GetLogEntries", category="LogPython", pattern=token, maxEntries=5) or []
        matches = re.findall(re.escape(token) + r"\s+(True|False)\b", str(rows))
        if matches and matches[-1] == "False":
            return {**base, "ok": False, "status": "failed", "error": "capture callback reported failure"}
        completed |= bool(matches and matches[-1] == "True")
        if completed and valid_pngs(expected, size):
            return {**base, "ok": True, "status": "complete", "mrq_available": started.get("mrq"),
                    "images": [str(p) for p in expected], "detected": "callback_and_files"}
        time.sleep(2)
    return {**base, "ok": False, "status": "incomplete" if completed else "unknown",
            "error": f"no verified completion within {timeout:.0f}s; inspect this capture before starting another"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sequence")
    parser.add_argument("--frames", default="", help="Comma-separated display-rate frames, one image each")
    parser.add_argument("--range", nargs=2, type=int, metavar=("START", "END"), help="Render START..END-1")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--question", default="", help="The visual question these frames answer (recorded)")
    parser.add_argument("--size", nargs=2, type=int, default=(960, 540), metavar=("W", "H"))
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--preroll", type=int, default=8, help="Frames rendered and discarded before each --frames frame")
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"))
    parser.add_argument("--allow-editor-ui", action="store_true", help="Explicitly permit legacy capture's render viewport")
    args = parser.parse_args(argv)
    if not args.frames and not args.range:
        parser.error("give --frames or --range")
    if not args.allow_editor_ui:
        parser.error("legacy capture can open a viewport; use --allow-editor-ui only for an explicitly requested UI workflow")
    if not args.project:
        parser.error("--project or UE_MCP_PROJECT is required")
    if not args.question:
        print("note: name the visual question with --question; renders do not prove behaviour", file=sys.stderr)

    from sequencer_tools.editor import Editor

    wanted = [int(f) for f in args.frames.split(",") if f.strip()]
    ranges = [tuple(args.range)] if args.range else [(max(0, f - args.preroll), f + 1) for f in wanted]
    args.out.mkdir(parents=True, exist_ok=True)
    editor = Editor(args.project)
    try:
        if editor.call("EditorAppToolset", "IsPIERunning") is not False:
            raise SystemExit("stop PIE before rendering")
        results = []
        for s, e in ranges:
            results.append(render_range(editor, args.sequence, args.out.resolve(), s, e, tuple(args.size), args.timeout,
                                        allow_editor_ui=args.allow_editor_ui))
            if not results[-1]["ok"]:
                break  # a timed-out capture may still be running; never schedule a second one blindly
    finally:
        editor.close()
    if not args.range:
        name = args.sequence.split(".")[0].rsplit("/", 1)[-1]
        keep = {f"{name}.{f:04d}.png" for f in wanted}
        for result in results:
            for path in result["images"]:
                image = Path(path)
                if image.name not in keep:
                    image.unlink()  # only enumerated images produced in this unique run
            result["images"] = [p for p in result["images"] if Path(p).name in keep]
    images = sorted(p for result in results for p in result["images"])
    report = {"tool": "sequence_render", "schema_version": SCHEMA_VERSION, "sequence": args.sequence,
              "question": args.question, "renders": results, "images": images,
              "passed": all(r["ok"] for r in results) and bool(images)}
    (args.out / "render.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
