#!/usr/bin/env python3
"""Copy the MCPBlueprintMetadata editor plugin into a UE project and compile it.

Stock UE has no write route for Blueprint function/variable descriptions (hover tooltips);
this small editor plugin adds one for editor Python (see blueprint_tooltips.py). It works for
Blueprint-only projects: UnrealBuildTool builds just the plugin module against an installed engine.

    python scripts/install_blueprint_metadata_plugin.py --uproject E:/Proj/MyGame.uproject --engine-root E:/UE_5.8

Install and build only with the user's agreement. The editor must be restarted to load a newly
installed plugin, so ask the user to save their work and restart it; never restart it yourself.
If the build reports that Live Coding is active, the editor has to be closed for the build.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = "MCPBlueprintMetadata"
SOURCE = Path(__file__).resolve().parents[1] / "assets" / "plugins" / PLUGIN


def sync(source: Path, target: Path) -> list[str]:
    """Copy plugin source files into target; return the relative paths that changed."""
    changed = []
    for path in sorted(source.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(source)
        dest = target / rel
        if dest.exists() and filecmp.cmp(path, dest, shallow=False):
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        changed.append(rel.as_posix())
    return changed


def build(engine_root: Path, uproject: Path) -> int:
    script = engine_root / "Engine" / "Build" / "BatchFiles" / ("Build.bat" if os.name == "nt" else "Build.sh")
    if not script.is_file():
        raise SystemExit(f"Build script not found under the engine root: {script}")
    command = [str(script), "UnrealEditor", "Win64" if os.name == "nt" else "Linux", "Development",
               f"-Project={uproject}", "-WaitMutex", "-NoHotReloadFromIDE"]
    print("Building:", " ".join(command), flush=True)
    return subprocess.call(command)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uproject", type=Path, required=True)
    parser.add_argument("--engine-root", type=Path, default=os.environ.get("UE_ENGINE_ROOT"),
                        help="Folder that contains Engine/ (default: $UE_ENGINE_ROOT)")
    parser.add_argument("--no-build", action="store_true", help="Only copy the source")
    args = parser.parse_args(argv)
    uproject = args.uproject.resolve()
    if uproject.suffix != ".uproject" or not uproject.is_file():
        raise SystemExit(f"Not a .uproject file: {uproject}")
    target = uproject.parent / "Plugins" / PLUGIN
    changed = sync(SOURCE, target)
    result = {"plugin": str(target), "copied": changed, "built": False}
    if not args.no_build:
        if not args.engine_root:
            raise SystemExit("Pass --engine-root or set UE_ENGINE_ROOT")
        code = build(Path(args.engine_root), uproject)
        result["built"] = code == 0
        if code:
            print(json.dumps(result, indent=2))
            return code
        result["binary"] = next((str(p) for p in (target / "Binaries").rglob(f"*{PLUGIN}*.dll")), None)
    result["next"] = "Restart the editor (after the user saves) so it loads the plugin, then run blueprint_tooltips.py."
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
