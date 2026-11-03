#!/usr/bin/env python3
"""Render frames of a Level Sequence to PNG to answer a named visual question (framing, readability).

    python scripts/sequence_render.py /Game/Cinematics/LS_Intro --frames 0,90,180 --out <dir> --question "主角是否在画面三分线上"

Each frame is rendered with the engine's built-in Level Sequence capture (SequencerTools.render_movie,
deprecated in 5.8 but working without the Movie Render Queue plugin) at the sequence's own frame
rate, after --preroll frames (default 8) so motion blur and temporal AA match playback; only the
requested frames are kept. --range START END renders a contiguous range instead. Completion comes
from the capture's callback, or from the expected files when the callback is not seen.
This is preview evidence: final-quality output goes through Movie Render Queue when the project
has the MovieRenderPipeline plugin enabled. Look at every image and report the answer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

SCHEMA_VERSION = "sequence_render/1"
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


def render_range(editor, sequence: str, out: Path, start: int, end: int, size: tuple[int, int], timeout: float) -> dict:
    token = "CODEX_RENDER_" + uuid.uuid4().hex[:10]
    path = sequence.split(".")[0]
    script = (RENDER_SCRIPT.replace("__SEQ__", json.dumps(f"{path}.{path.rsplit('/', 1)[-1]}"))
              .replace("__OUT__", json.dumps(out.as_posix())).replace("__W__", str(size[0])).replace("__H__", str(size[1]))
              .replace("__START__", str(start)).replace("__END__", str(end)).replace("__TOKEN__", token))
    started = editor.python(script)
    if not started.get("started"):
        return {"start": start, "end": end, "ok": False, "error": "render_movie did not start (PIE running?)"}
    name = path.rsplit("/", 1)[-1]
    expected = [out / f"{name}.{frame:04d}.png" for frame in range(start, end)]
    deadline = time.time() + timeout
    sizes: list[int] = []
    while time.time() < deadline:
        rows = editor.call("LogsToolset", "GetLogEntries", category="LogPython", pattern=token, maxEntries=5) or []
        if rows:
            return {"start": start, "end": end, "ok": "True" in str(rows[-1]), "mrq_available": started.get("mrq")}
        if all(p.is_file() for p in expected):
            now = [p.stat().st_size for p in expected]
            if now == sizes and all(now):
                return {"start": start, "end": end, "ok": True, "mrq_available": started.get("mrq"), "detected": "files"}
            sizes = now
        time.sleep(2)
    return {"start": start, "end": end, "ok": False, "error": f"no completion within {timeout:.0f}s"}


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
    args = parser.parse_args(argv)
    if not args.frames and not args.range:
        parser.error("give --frames or --range")
    if not args.question:
        print("note: name the visual question with --question; renders do not prove behaviour", file=sys.stderr)

    from sequencer_tools.editor import Editor

    wanted = [int(f) for f in args.frames.split(",") if f.strip()]
    ranges = [tuple(args.range)] if args.range else [(max(0, f - args.preroll), f + 1) for f in wanted]
    args.out.mkdir(parents=True, exist_ok=True)
    editor = Editor(args.project)
    try:
        if editor.call("EditorAppToolset", "IsPIERunning"):
            raise SystemExit("stop PIE before rendering")
        results = [render_range(editor, args.sequence, args.out.resolve(), s, e, tuple(args.size), args.timeout) for s, e in ranges]
    finally:
        editor.close()
    if not args.range:
        name = args.sequence.split(".")[0].rsplit("/", 1)[-1]
        keep = {f"{name}.{f:04d}.png" for f in wanted}
        for start, end in ranges:
            for frame in range(start, end):
                image = args.out / f"{name}.{frame:04d}.png"
                if image.name not in keep and image.is_file():
                    image.unlink()  # pre-roll frame written by this run
    images = sorted(p.name for p in args.out.glob("*.png"))
    report = {"tool": "sequence_render", "schema_version": SCHEMA_VERSION, "sequence": args.sequence,
              "question": args.question, "renders": results, "images": images,
              "passed": all(r["ok"] for r in results) and bool(images)}
    (args.out / "render.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
