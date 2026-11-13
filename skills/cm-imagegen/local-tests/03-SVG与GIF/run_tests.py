"""Four independently requested format tests; one submission per case."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
CLI = Path(r"C:\Users\miaoyin\.codex\skills\cm-imagegen\scripts\cm_image_gen.py")
CASES = [
    {"id": "svg_01_greenhouse", "label": "SVG 1：机械温室", "format": "svg", "size": "1024x1024", "prompt": "Generate an editable static SVG vector illustration. Square 1:1 composition. An intricate isometric botanical greenhouse and astronomical observatory: a glass dome, a brass telescope, six planters with distinct fern leaves and citrus trees, small irrigation pipes, three visible gears, a tiled stone path, a curved footbridge, a red bicycle, and a crescent moon. Precise clean vector paths, geometric layering, consistent isometric perspective, six harmonious navy, teal, cream, coral and gold colors. Clear silhouettes and fine details, no lettering, no raster textures, no embedded bitmap images, no external resources. Return genuine SVG paths and shapes through SVG output."},
    {"id": "svg_02_canal", "label": "SVG 2：运河小镇", "format": "svg", "size": "1024x1024", "prompt": "Generate an editable static SVG vector illustration. Square 1:1 composition. A detailed miniature canal-town map: a winding blue canal, two distinct stone bridges, six small colorful houses with individual windows, a red tram, a lighthouse, a windmill, twelve trees, moored boats, a market square with striped awnings and a tiny compass rose. Elegant geometric paths and shapes, accurate road and bridge connections, thin consistent outlines, cream background, deep teal, coral, ochre and navy accents. No text labels, no raster textures, no embedded bitmap images, no external resources. Return genuine SVG vector content through SVG output."},
    {"id": "gif_01_greenhouse", "label": "GIF 1：温室夜景", "format": "gif", "size": "auto", "prompt": "Generate an actual animated GIF with 9 distinct frames at 200 milliseconds per frame, a clean seamless 1.8 second loop. A richly detailed miniature glass greenhouse and brass observatory at night: visible ferns, orange trees, small irrigation pipes, stone path, footbridge, telescope and a red bicycle. The brass gear makes a slow gentle oscillation, fern leaves sway slightly, and warm lantern light softly flickers. Fixed camera and stable architecture, legible detailed shapes, cozy navy and gold illustrated palette. The first and final poses connect smoothly. No text, no contact sheet, no sprite sheet: the output is one playable looping GIF animation."},
    {"id": "gif_02_canal", "label": "GIF 2：雨夜运河", "format": "gif", "size": "auto", "prompt": "Generate an actual animated GIF with 9 distinct frames at 200 milliseconds per frame, a clean seamless 1.8 second loop. A detailed cozy canal town in light evening rain: colorful houses, a small stone bridge, a stationary red tram, market awnings, trees, and a cat resting under a warm lamp. A moored blue boat gently bobs on the water, hanging lanterns sway slightly, and soft circular rain ripples animate on the canal. Fixed camera, stable buildings, warm reflected lights, careful small details, elegant illustrated style. Smooth repeating motion with matching loop endpoints. No text, no contact sheet, no sprite sheet: one playable animated GIF file."},
]


def main():
    results = []
    for case in CASES:
        folder = ROOT / case["id"]
        folder.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "-X", "utf8", str(CLI), "generate", "--api", "images", "--model", "gpt-image-2.6-sunburst",
                   "--quality", "max", "--complexity", "high", "--n", "1", "--size", case["size"], "--output-format", case["format"],
                   "--prompt", case["prompt"], "--out-dir", str(folder), "--filename", case["id"], "--max-attempts", "1", "--timeout", "600"]
        if case["format"] == "gif":
            command += ["--frame-count", "9", "--frame-duration-ms", "200"]
        (folder / "request.json").write_text(json.dumps({**case, "command": command}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"event": "started", "case": case["id"], "format": case["format"]}), flush=True)
        start = time.monotonic()
        process = subprocess.run(command, capture_output=True, encoding="utf-8", text=True)
        (folder / "stdout.json").write_text(process.stdout, encoding="utf-8")
        (folder / "stderr.txt").write_text(process.stderr, encoding="utf-8")
        try:
            output = json.loads(process.stdout)
        except ValueError:
            output = {"ok": False, "error": process.stderr.strip()[:3000]}
        result = {**case, "elapsed_seconds": round(time.monotonic()-start, 2), "exit_code": process.returncode,
                  "result": output, "original_files": [{"path": name, "sha256": hashlib.sha256(Path(name).read_bytes()).hexdigest()}
                                                      for name in output.get("paths", [])]}
        results.append(result)
        (ROOT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"event": "finished", "case": case["id"], "ok": output.get("ok"), "seconds": result["elapsed_seconds"],
                          "dimensions": output.get("output_dimensions"), "actual_formats": [x.get("format") for x in output.get("media_outputs", [])],
                          "error_kind": output.get("error_kind"), "error": output.get("error", "")[:700]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
