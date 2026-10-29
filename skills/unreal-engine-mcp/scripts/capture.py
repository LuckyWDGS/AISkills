#!/usr/bin/env python3
"""Capture editor images through Epic's MCP without touching the user's viewport camera or windows.

    python scripts/capture.py asset /Game/M/M_Fire --out-dir <session>/captures
    python scripts/capture.py viewport --pose 0,-600,200,-10,90,0 --frames 3 --interval 0.5 --out-dir <session>/captures

Writes PNGs plus an ``mcp_capture/1`` JSON report and prints the report path.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ue_mcp.capture import capture_report, parse_pose  # noqa: E402
from ue_mcp.skill_api import DEFAULT_MCP_URL, connect  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=DEFAULT_MCP_URL)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--project", help="Refuse an endpoint served by another project (env UE_MCP_PROJECT)")
    sub = parser.add_subparsers(dest="mode", required=True)
    asset = sub.add_parser("asset", help="Thumbnail render of one asset (EditorAppToolset.CaptureAssetImage)")
    asset.add_argument("asset_path")
    viewport = sub.add_parser("viewport", help="Level viewport frame(s) (EditorAppToolset.CaptureViewport)")
    viewport.add_argument("--pose", help="x,y,z,pitch,yaw,roll in cm/degrees; default: the current viewport camera")
    viewport.add_argument("--frames", type=int, default=1, help="Time-separated frames for motion review")
    viewport.add_argument("--interval", type=float, default=0.5, help="Seconds between frames")
    for item in (asset, viewport):
        item.add_argument("--out-dir", required=True)
        item.add_argument("--name", help="File stem; default derived from the asset path or 'viewport'")
    args = parser.parse_args(argv)

    asset_path = getattr(args, "asset_path", "")
    stem = args.name or re.sub(r"[^A-Za-z0-9_-]+", "-", asset_path.rsplit("/", 1)[-1].split(".")[0] or "viewport")
    out_dir = Path(args.out_dir)
    client = connect(url=args.url, timeout=args.timeout, project=args.project)
    try:
        report = capture_report(client, args.mode, out_dir, stem, asset_path=asset_path,
                                pose=parse_pose(args.pose) if getattr(args, "pose", None) else None,
                                frames=getattr(args, "frames", 1), interval=getattr(args, "interval", 0.0))
    finally:
        client.close()
    out = out_dir / f"{stem}-capture.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
