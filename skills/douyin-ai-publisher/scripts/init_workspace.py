#!/usr/bin/env python3
"""Create missing local Douyin operating records without replacing existing data.

--account <ID>  (recommended) <DOUYIN_PUBLISHER_HOME or ~/.douyin-publisher>/<ID>/
--root <dir>    (legacy)      <dir>/.codex/session/douyin-publisher/
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys

ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def publisher_home() -> Path:
    return Path(os.environ.get("DOUYIN_PUBLISHER_HOME") or Path.home() / ".douyin-publisher").expanduser()


RECORD_NAMES = (
    "operations.json",
    "content_queue.csv",
    "metrics_snapshots.csv",
    "experiments.csv",
    "audience_requests.csv",
)


def is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def initialize(root_argument: str | None, dry_run: bool = False, account: str | None = None) -> list[tuple[str, Path]]:
    if account is not None:
        if not ACCOUNT_RE.match(account):
            raise ValueError("--account may only contain letters, digits, '.', '_' and '-'")
        home = publisher_home()
        if not dry_run:
            home.mkdir(parents=True, exist_ok=True)
        root_path = home.resolve()
    else:
        root_path = Path(root_argument or "").expanduser()
        if not root_path.is_absolute():
            raise ValueError("--root must be an absolute workspace directory")
        root_path = root_path.resolve(strict=True)
        if not root_path.is_dir():
            raise ValueError("--root must be an existing directory")

    skill_directory = Path(__file__).resolve().parent.parent
    if is_within(root_path, skill_directory):
        raise ValueError("runtime records must not be created inside the Skill directory")
    template_directory = (skill_directory / "assets" / "templates").resolve(strict=True)
    if not template_directory.is_dir():
        raise ValueError("template directory is missing or is not a directory")

    if account is not None:
        output_directory = root_path / account
    else:
        output_directory = root_path / ".codex" / "session" / "douyin-publisher"
    resolved_output = output_directory.resolve()
    if not is_within(resolved_output, root_path):
        raise ValueError("output directory resolves outside the requested workspace")
    if output_directory.exists() and not output_directory.is_dir():
        raise ValueError("output directory conflicts with an existing non-directory")

    # Validate and load every source before creating any destination files.
    records: list[tuple[Path, bytes]] = []
    for name in RECORD_NAMES:
        source = template_directory / name
        resolved_source = source.resolve(strict=True)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"template must be a regular file: {name}")
        if not is_within(resolved_source, template_directory):
            raise ValueError(f"template resolves outside the template directory: {name}")
        destination = output_directory / name
        if not is_within(destination.resolve(), resolved_output):
            raise ValueError(f"destination resolves outside the output directory: {name}")
        if destination.is_symlink() or (destination.exists() and not destination.is_file()):
            raise ValueError(f"destination is not a regular record file: {name}")
        records.append((destination, source.read_bytes()))

    if not dry_run:
        output_directory.mkdir(parents=True, exist_ok=True)
        (output_directory / "releases").mkdir(exist_ok=True)

    results = []
    for destination, content in records:
        if destination.exists():
            results.append(("existing", destination))
        elif dry_run:
            results.append(("planned", destination))
        else:
            try:
                with destination.open("xb") as record_file:
                    record_file.write(content)
            except FileExistsError:
                # Another initializer or user may have created it after preflight.
                if destination.is_symlink() or not destination.is_file():
                    raise ValueError(f"destination is not a regular record file: {destination.name}")
                results.append(("existing", destination))
            else:
                results.append(("created", destination))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--account", help="account ID; records go to the per-account directory (recommended)")
    target.add_argument("--root", help="legacy: absolute existing workspace directory")
    parser.add_argument("--dry-run", action="store_true", help="show missing records without writing")
    arguments = parser.parse_args()
    try:
        results = initialize(arguments.root, arguments.dry_run, arguments.account)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    for status, destination in results:
        print(f"{status}: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
