#!/usr/bin/env python3
"""Initialize and maintain compact Codex session continuity files."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
from pathlib import Path


PROJECT_MARKERS = [
    "AGENTS.md",
    "settings.gradle.kts",
    "build.gradle.kts",
    "package.json",
    "Cargo.toml",
    "pyproject.toml",
    "go.mod",
    "README.md",
]


def now() -> str:
    return dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")


def find_auto_root(start: Path) -> Path:
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    parents = [current, *current.parents]

    # Existing project memory is the strongest signal. It lets work from deep
    # subdirectories keep writing to the same project-local memory root.
    for parent in parents:
        if (parent / ".codex" / "session" / "HANDOFF.md").exists():
            return parent

    # Prefer real project markers over a parent Git root. This avoids placing
    # memory in a broad monorepo or workspace folder when the task is scoped to
    # a nested project.
    for parent in parents:
        if any((parent / marker).exists() for marker in PROJECT_MARKERS):
            return parent

    # Only use a Git root when the current directory itself is that root. If the
    # nearest .git is above the current directory, choose the current directory
    # instead so memory stays local to the task scope.
    if (current / ".git").exists():
        return current

    return current


def resolve_root(value: str) -> Path:
    if value.lower() == "auto":
        root = find_auto_root(Path.cwd())
    else:
        root = Path(value).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Root does not exist: {root}")
    return root


def git_value(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"


def session_dir(root: Path) -> Path:
    return root / ".codex" / "session"


def project_template(root: Path) -> str:
    branch = git_value(root, "branch", "--show-current")
    return f"""# Project Memory

Updated: {now()}
Root: {root}
Git branch: {branch}

## Purpose

- Describe what this project does and what the user is trying to achieve.

## Architecture

- Note the main app/framework, important directories, and runtime entry points.

## Commands

- Add build, test, lint, run, and debug commands that are known to work.

## Conventions

- Capture project-specific coding, UX, language, or workflow preferences.

## Constraints

- Record durable constraints, external services, platform limits, and things to avoid.
"""


def handoff_template(root: Path, archived: str | None = None) -> str:
    branch = git_value(root, "branch", "--show-current")
    archive_line = f"\nPrevious handoff archived at: {archived}\n" if archived else ""
    return f"""# Active Handoff

Updated: {now()}
Root: {root}
Git branch: {branch}{archive_line}

## Current Objective

- State the active task in one or two sentences.

## Current State

- Summarize what is already done and what is still pending.

## Important Files

- Add the smallest set of files a fresh Codex session should inspect first.

## Commands And Verification

- List commands/tests run and their exact outcomes.

## Risks And Assumptions

- Mark uncertain items with "Needs verification".

## Next Steps

1. Replace this with the first concrete next action.
"""


def decisions_template(root: Path) -> str:
    return f"""# Decision Log

Updated: {now()}
Root: {root}

## Decisions

- YYYY-MM-DD: Decision. Rationale. Consequence.
"""


def assets_template(root: Path) -> str:
    return f"""# Asset Index

Updated: {now()}
Root: {root}

## Active Assets

- Add only user-provided assets that the task actually depends on: design/UI references, bug screenshots, PDFs, mockups, reference files, generated assets, or other external artifacts that future Codex sessions may need.

## Recording Format

- Path or source: Where the file lives, or "description only" when the original attachment cannot be saved.
- Asset type: `design-ui-reference`, `bug-screenshot`, `content-asset`, `reference-doc`, or another short label.
- Role: Why this asset matters for the current task.
- Notes: Key visual/semantic details, explicit user intent, and any uncertainty.
"""


def debug_screenshots_template(root: Path) -> str:
    return f"""# Debug Screenshot Index

Updated: {now()}
Root: {root}

## Active Debug Screenshots

- Add only runtime/test/debug screenshots that still help reproduce, diagnose, or verify current issues.

## Recording Format

- Path or source: Where the file lives, or "description only" when the original capture cannot be saved.
- Screenshot type: `bug-screenshot`, `runtime-verification`, `tv-photo`, `visual-regression`, or another short label.
- Status: `active-bug`, `active-verification`, `fixed-awaiting-cleanup`, `stale-delete-soon`, or another short lifecycle label.
- Role: Why this screenshot matters for the current code/debugging task.
- Notes: What the image shows, the related bug or verification goal, and when it should be deleted or refreshed.

## Cleanup Rules

- Keep only active blockers, useful reproductions, and the latest relevant verification captures.
- Delete or remove stale entries after the issue is fixed or the screenshot is no longer needed.
- Do not use this file for design/UI references; keep those in `ASSETS.md`.
- `active-bug`: keep until the issue is fixed and a newer verification capture proves the fix.
- `active-verification`: keep only the latest one or two useful screenshots for the current area/state.
- `fixed-awaiting-cleanup`: remove by the end of the current related task or the next related session.
- `stale-delete-soon`: remove as soon as practical.
"""


def agents_template(root: Path) -> str:
    return f"""# Codex Project Instructions

## Session Memory

- Use `$codex-session-continuity` for this project.
- Read rules from `C:/Users/QY/.codex/skills/codex-session-continuity/SKILL.md`.
- Use helper script `C:/Users/QY/.codex/skills/codex-session-continuity/scripts/session_continuity.py`.
- Project memory lives only in `{root}\\.codex\\session\\`.

## Startup

- First read `.codex/session/HANDOFF.md`.
- Then read `.codex/session/PROJECT.md`.
- Read `.codex/session/ASSETS.md` only if the task depends on screenshots, design images, PDFs, mockups, or external reference files.
- Read `.codex/session/DEBUG_SCREENSHOTS.md` only if the task depends on runtime screenshots, bug/error captures, or visual verification/debugging images.
- Read `.codex/session/DECISIONS.md` when the handoff references decisions or when architecture/context choices matter.
- Verify memory against current files before editing.

## Checkpoint

- Before every final response that completes or pauses project work, update `.codex/session/HANDOFF.md`.
- Do not treat every uploaded image as a design/UI reference. Only register it as design/UI when the user's text explicitly makes it a design reference.
- If user-provided images or reference files matter, save/copy them under the project when possible and register them in `.codex/session/ASSETS.md` with an asset type and explicit user intent.
- Put runtime/test/debug screenshots in `.codex/session/DEBUG_SCREENSHOTS.md`, not in `.codex/session/ASSETS.md`, and prune stale entries regularly.
- Do not read `.codex/session/archive/` unless explicitly asked or referenced by the active handoff.
"""


def write_if_missing(path: Path, text: str) -> str:
    if path.exists():
        return f"exists  {path}"
    path.write_text(text, encoding="utf-8", newline="\n")
    return f"created {path}"


def ensure_project_agents(root: Path) -> str:
    path = root / "AGENTS.md"
    marker = "$codex-session-continuity"
    if not path.exists():
        path.write_text(agents_template(root), encoding="utf-8", newline="\n")
        return f"created {path}"
    text = path.read_text(encoding="utf-8")
    if marker in text or ".codex/session/HANDOFF.md" in text:
        return f"exists  {path}"
    addition = "\n\n" + agents_template(root).replace("# Codex Project Instructions\n\n", "## Codex Session Continuity\n\n")
    path.write_text(text.rstrip() + addition, encoding="utf-8", newline="\n")
    return f"updated {path}"


def ensure_gitignore(root: Path) -> str:
    path = root / ".gitignore"
    entry = ".codex/session/"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if entry in text.splitlines():
            return f"ignored {entry} already present in {path}"
        newline = "" if text.endswith("\n") or not text else "\n"
        path.write_text(f"{text}{newline}\n# Local Codex session continuity memory\n{entry}\n", encoding="utf-8", newline="\n")
        return f"ignored {entry} added to {path}"
    path.write_text(f"# Local Codex session continuity memory\n{entry}\n", encoding="utf-8", newline="\n")
    return f"ignored {entry} added to {path}"


def cmd_init(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    base = session_dir(root)
    (base / "archive").mkdir(parents=True, exist_ok=True)
    messages = [
        write_if_missing(base / "PROJECT.md", project_template(root)),
        write_if_missing(base / "HANDOFF.md", handoff_template(root)),
        write_if_missing(base / "ASSETS.md", assets_template(root)),
        write_if_missing(base / "DEBUG_SCREENSHOTS.md", debug_screenshots_template(root)),
        write_if_missing(base / "DECISIONS.md", decisions_template(root)),
    ]
    if not args.no_gitignore:
        messages.append(ensure_gitignore(root))
    if not args.no_project_agents:
        messages.append(ensure_project_agents(root))
    print("\n".join(messages))
    print(f"ready   {base}")


def cmd_roll(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    base = session_dir(root)
    base.mkdir(parents=True, exist_ok=True)
    archive = base / "archive"
    archive.mkdir(exist_ok=True)
    handoff = base / "HANDOFF.md"
    archived_path: Path | None = None
    if handoff.exists() and handoff.read_text(encoding="utf-8").strip():
        stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        archived_path = archive / f"HANDOFF-{stamp}.md"
        archived_path.write_text(handoff.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    handoff.write_text(
        handoff_template(root, str(archived_path) if archived_path else None),
        encoding="utf-8",
        newline="\n",
    )
    print(f"archived {archived_path}" if archived_path else "archived none")
    print(f"reset    {handoff}")


def cmd_status(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    base = session_dir(root)
    print(f"root: {root}")
    for name in ["PROJECT.md", "HANDOFF.md", "ASSETS.md", "DEBUG_SCREENSHOTS.md", "DECISIONS.md"]:
        path = base / name
        if not path.exists():
            print(f"missing {path}")
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.count("\n") + (1 if text else 0)
        words = len(text.split())
        label = "ok"
        if name == "HANDOFF.md" and lines > args.max_handoff_lines:
            label = "warn: roll or compress"
        if name == "PROJECT.md" and lines > args.max_project_lines:
            label = "warn: compress durable memory"
        if name == "DEBUG_SCREENSHOTS.md" and lines > args.max_debug_lines:
            label = "warn: prune stale debug captures"
        print(f"{name}: {lines} lines, {words} words, {len(text)} chars [{label}]")


def cmd_where(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    print(root)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Codex session continuity files.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create .codex/session files if missing.")
    init.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    init.add_argument("--no-gitignore", action="store_true", help="Do not add .codex/session/ to .gitignore.")
    init.add_argument("--no-project-agents", action="store_true", help="Do not create or update project AGENTS.md.")
    init.set_defaults(func=cmd_init)

    roll = sub.add_parser("roll", help="Archive HANDOFF.md and create a fresh template.")
    roll.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    roll.set_defaults(func=cmd_roll)

    status = sub.add_parser("status", help="Show rough size of active session files.")
    status.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    status.add_argument("--max-handoff-lines", type=int, default=150, help="Warn when HANDOFF.md is longer than this.")
    status.add_argument("--max-project-lines", type=int, default=250, help="Warn when PROJECT.md is longer than this.")
    status.add_argument("--max-debug-lines", type=int, default=120, help="Warn when DEBUG_SCREENSHOTS.md is longer than this.")
    status.set_defaults(func=cmd_status)

    where = sub.add_parser("where", help="Print the auto-detected project memory root.")
    where.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    where.set_defaults(func=cmd_where)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
