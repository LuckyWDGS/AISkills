"""One submission per named case; no outer retries or media conversions."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
CLI = Path(r"C:\Users\miaoyin\.codex\skills\cm-imagegen\scripts\cm_image_gen.py")
PROMPT = """Create a richly detailed editorial illustration of a small mountain observatory and botanical greenhouse at blue hour. Show a brass telescope, a red bicycle, a glass greenhouse containing ferns and orange trees, a narrow stone path crossing a stream, a wooden bench, a cat sleeping on the bench, a person carrying a lantern, distant snow-capped mountains, fine brass mechanisms, raindrops on the glass, warm interior lights, and carefully rendered leaves and stone textures. Balanced coherent architecture, accurate perspective, crisp small details, natural lighting. No text, no border, no collage. Compose the complete scene to fill the requested output canvas; keep every main subject inside the frame."""
CASES = [
    ("square", "1024x1024", "png", PROMPT, []),
    ("landscape", "1536x1024", "png", PROMPT, []),
    ("portrait", "1024x1536", "png", PROMPT, []),
    ("gif", "auto", "gif", "Generate an actual looping animated GIF, not a sprite sheet. A small blue paper sailboat gently rocks left and right on a calm golden pond. Fixed camera, clear flat illustration, no text, clean continuous loop, visible gentle motion between frames.", ["--frame-count", "4", "--frame-duration-ms", "200"]),
    ("svg", "1024x1024", "svg", "Create a clean static vector emblem of a mountain observatory with a brass telescope, a crescent moon, three stars and a curved footpath. Geometric shapes, elegant balanced composition, deep navy and golden yellow, no lettering, no bitmap textures. Return editable SVG paths and shapes.", ["--n", "1"]),
]

def main():
    results = []
    for name, size, fmt, prompt, extra in CASES:
        folder = ROOT / name
        folder.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "-X", "utf8", str(CLI), "generate", "--api", "images", "--model", "gpt-image-2.6-sunburst",
                   "--quality", "max", "--complexity", "high", "--size", size, "--output-format", fmt,
                   "--prompt", prompt, "--out-dir", str(folder), "--filename", name, "--max-attempts", "1", "--timeout", "600", *extra]
        if fmt == "png":
            command.append("--require-exact-size")
        (folder / "request.json").write_text(json.dumps({"case": name, "command": command, "size": size, "format": fmt, "prompt": prompt}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"event": "started", "case": name, "size": size, "format": fmt}), flush=True)
        started = time.monotonic()
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        (folder / "stdout.json").write_text(process.stdout, encoding="utf-8")
        (folder / "stderr.txt").write_text(process.stderr, encoding="utf-8")
        try:
            output = json.loads(process.stdout)
        except ValueError:
            output = {"ok": False, "error": process.stderr.strip()[:2000]}
        result = {"case": name, "requested_size": size, "requested_format": fmt,
                  "elapsed_seconds": round(time.monotonic()-started, 2), "exit_code": process.returncode, "result": output}
        results.append(result)
        (ROOT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"event": "finished", "case": name, "ok": output.get("ok"), "seconds": result["elapsed_seconds"],
                          "actual_sizes": output.get("output_dimensions"), "formats": [x.get("format") for x in output.get("media_outputs", [])],
                          "error_kind": output.get("error_kind"), "error": output.get("error", "")[:500]}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
