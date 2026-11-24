#!/usr/bin/env python3
"""Create a new UE 5.9 background camera sequence with a runtime binding tag.

Validates a plan without editor access by default. --execute requires an absolute
.uproject guard. Never opens a timeline, evaluates a world, or replaces an asset.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sequencer_tools.native_camera import NativeCameraBuilder, validate_plan, validate_project
from sequencer_tools.mcp import connect


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"))
    parser.add_argument("--url", default=os.environ.get("UNREAL_MCP_URL", "http://127.0.0.1:8001/mcp"))
    parser.add_argument("--state-dir", type=Path, default=os.environ.get("UE_MCP_CACHE_DIR"),
                        help="Isolated MCP state; defaults to a directory beside the output report")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"tool": "sequence_native_camera", "schema_version": "native_camera/1",
              "executed": False, "creation_attempted": False}
    client = builder = None
    exit_code = 0
    try:
        source = json.loads(args.plan.read_text(encoding="utf-8-sig"))
        report["validated_plan"] = validate_plan(source)
        if args.execute:
            validate_project(args.project)
            state_dir = (args.state_dir or args.out.parent / ".ue-mcp-native-camera").resolve()
            os.environ["UE_MCP_CACHE_DIR"] = str(state_dir)
            report["state_directory"] = str(state_dir)
            client = connect(url=args.url, project=args.project, timeout=60)
            client.refresh_schema = True
            client.reinitialize()  # Explicitly reject a stale engine/project identity.
            builder = NativeCameraBuilder(client)
            report["identity"] = client.initialize_result
            report["result"] = builder.build(source, save=args.save)
            report["executed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        if builder and builder.creation_attempted:
            report["outcome"] = ("inspect_partial_state_before_retry" if builder.created
                                 else "unknown_creation_completion")
        else:
            report["outcome"] = "refused_before_creation"
        exit_code = 1
    finally:
        if builder:
            report["creation_attempted"] = builder.creation_attempted
            report["created"] = builder.created
            report["calls"] = builder.records
        if client:
            client.close()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.out.resolve()), "executed": report["executed"],
                      "error": report.get("error")}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
