#!/usr/bin/env python3
"""Initialize and maintain compact Codex session continuity files."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
from pathlib import Path
import re
import shutil


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

IGNORED_DIR_NAMES = {
    ".git",
    ".gradle",
    ".idea",
    ".codex",
    "build",
    "node_modules",
    "dist",
    "out",
    "coverage",
    "debug-artifacts",
    ".next",
    ".turbo",
}

COMMON_CODE_DIRS = {
    "src",
    "app",
    "ui",
    "screens",
    "components",
    "theme",
    "viewmodel",
    "viewmodels",
    "data",
    "remote",
    "local",
    "repository",
    "repositories",
    "api",
    "server",
    "client",
    "frontend",
    "backend",
    "features",
    "models",
    "model",
    "store",
    "state",
    "services",
    "service",
    "util",
    "utils",
    "hooks",
    "pages",
}

SEMANTIC_GROUPS = {
    "ui": {"ui", "screen", "screens", "page", "pages", "dialog", "layout", "component", "components", "theme", "style", "styles", "topbar", "header", "sidebar", "menu"},
    "data": {"data", "repository", "repositories", "remote", "local", "model", "models", "api", "network", "cache", "database", "db", "dao", "source", "sources"},
    "state": {"state", "viewmodel", "viewmodels", "store", "hook", "hooks"},
    "feature": {"feature", "flow", "module", "screen", "home", "search", "favorite", "favorites", "history", "player", "playback", "settings", "config"},
}


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


def git_run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def git_repo_root(root: Path) -> Path:
    value = git_value(root, "rev-parse", "--show-toplevel")
    if value == "unknown":
        raise SystemExit(f"Not a git repository root or child: {root}")
    return Path(value).resolve()


def git_current_branch(root: Path) -> str:
    return git_value(root, "branch", "--show-current")


def git_is_clean(root: Path) -> bool:
    result = git_run(root, "status", "--porcelain", check=False)
    return not result.stdout.strip()


def git_branch_exists(repo_root: Path, branch: str) -> bool:
    result = git_run(repo_root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
    return result.returncode == 0


def git_worktree_records(repo_root: Path) -> list[dict[str, str]]:
    result = git_run(repo_root, "worktree", "list", "--porcelain")
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        key, value = line.split(" ", 1)
        current[key] = value
    if current:
        records.append(current)
    return records


def find_worktree_record_by_branch(records: list[dict[str, str]], branch: str) -> dict[str, str] | None:
    for record in records:
        if record.get("branch", "") == f"refs/heads/{branch}":
            return record
    return None


def project_relative_to_repo(root: Path) -> Path:
    repo_root = git_repo_root(root)
    try:
        return root.resolve().relative_to(repo_root)
    except Exception:
        return Path(".")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "task"


def tokenize(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]


def default_task_branch(task: str) -> str:
    return f"codex/{slugify(task)}"


def default_worktree_path(root: Path, task: str) -> Path:
    repo_root = git_repo_root(root)
    project_name = root.name
    return (repo_root.parent / f"{repo_root.name}-worktrees" / project_name / slugify(task)).resolve()


def target_project_root_in_worktree(source_project_root: Path, worktree_root: Path) -> Path:
    rel = project_relative_to_repo(source_project_root)
    if str(rel) == ".":
        return worktree_root.resolve()
    return (worktree_root / rel).resolve()


def relative_str(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def collect_candidate_dirs(root: Path) -> list[Path]:
    candidates: list[Path] = []
    direct_code_roots: list[Path] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name in IGNORED_DIR_NAMES:
            continue
        if child.name in {"app", "src", "frontend", "backend", "server", "client"}:
            direct_code_roots.append(child)
        if child.name in COMMON_CODE_DIRS:
            candidates.append(child)

    java_root = root / "app" / "src" / "main" / "java"
    if java_root.exists():
        for path in java_root.rglob("*"):
            if path.is_dir() and path.name in COMMON_CODE_DIRS and "build" not in path.parts:
                candidates.append(path)

    for code_root in direct_code_roots:
        for path in code_root.rglob("*"):
            if not path.is_dir():
                continue
            if any(part in IGNORED_DIR_NAMES for part in path.parts):
                continue
            depth = len(path.relative_to(root).parts)
            if depth > 6:
                continue
            if path.name in COMMON_CODE_DIRS:
                candidates.append(path)

    unique: list[Path] = []
    seen = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def score_candidate_dir(path: Path, root: Path, tokens: set[str]) -> int:
    rel = relative_str(path, root).lower()
    parts = {part.lower() for part in Path(rel).parts}
    score = 0
    for token in tokens:
        if token in parts:
            score += 6
        if token in rel:
            score += 2
    for group_name, aliases in SEMANTIC_GROUPS.items():
        if tokens & aliases and (group_name in parts or parts & aliases):
            score += 4
    if "ui" in rel or "screen" in rel or "component" in rel:
        score += 1 if tokens & SEMANTIC_GROUPS["ui"] else 0
    if "data" in rel or "repository" in rel or "remote" in rel or "local" in rel:
        score += 1 if tokens & SEMANTIC_GROUPS["data"] else 0
    if "viewmodel" in rel or "state" in rel:
        score += 1 if tokens & SEMANTIC_GROUPS["state"] else 0
    depth = len(Path(rel).parts)
    if depth <= 4:
        score += 1
    return score


def fallback_scope(root: Path, tokens: set[str]) -> list[str]:
    java_app_root = root / "app" / "src" / "main" / "java" / "com" / "moviecat" / "app"
    if java_app_root.exists():
        if tokens & SEMANTIC_GROUPS["ui"]:
            return [str((java_app_root / "ui" / "screens").resolve())]
        if tokens & SEMANTIC_GROUPS["data"]:
            return [str((java_app_root / "data").resolve())]
        if tokens & SEMANTIC_GROUPS["state"]:
            return [str((java_app_root / "viewmodel").resolve())]
        return [str(java_app_root.resolve())]
    for name in ["src", "app", "frontend", "backend"]:
        path = root / name
        if path.exists():
            return [str(path.resolve())]
    return [str(root.resolve())]


def suggest_task_contract(root: Path, task: str, goal: str) -> dict[str, list[str] | str]:
    tokens = set(tokenize(task) + tokenize(goal))
    candidates = collect_candidate_dirs(root)
    scored = [(score_candidate_dir(path, root, tokens), path) for path in candidates]
    scored = [(score, path) for score, path in scored if score > 0]
    scored.sort(key=lambda item: (-item[0], len(relative_str(item[1], root))))

    owned: list[str] = []
    for score, path in scored:
        path_str = str(path.resolve())
        if any(path_str.startswith(existing.rstrip("*")) or existing.startswith(path_str) for existing in owned):
            continue
        owned.append(path_str)
        if len(owned) >= 3:
            break

    if not owned:
        owned = fallback_scope(root, tokens)

    avoid_candidates = []
    for path in candidates:
        path_str = str(path.resolve())
        if path_str in owned:
            continue
        if any(path_str.startswith(existing) for existing in owned):
            continue
        if any(existing.startswith(path_str) for existing in owned):
            continue
        avoid_candidates.append(path_str)
    avoid = avoid_candidates[:4] if avoid_candidates else ["[no-explicit-avoid-paths-yet]"]

    design_scope = []
    if "home" in tokens:
        design_scope.append("home-screen")
    if "search" in tokens:
        design_scope.append("search")
    if "player" in tokens or "playback" in tokens:
        design_scope.append("player")
    if "favorite" in tokens or "favorites" in tokens:
        design_scope.append("favorites")
    if "history" in tokens:
        design_scope.append("history")
    if "settings" in tokens or "config" in tokens:
        design_scope.append("settings")
    if "menu" in tokens or "sidebar" in tokens:
        design_scope.append("sidebar-or-menu")
    if "topbar" in tokens or "header" in tokens:
        design_scope.append("top-bar")
    if not design_scope:
        design_scope = [slugify(task)]

    confidence = "high" if scored and scored[0][0] >= 8 else ("medium" if scored else "low")
    return {
        "owned": owned,
        "avoid": avoid,
        "design_scope": design_scope,
        "confidence": confidence,
    }


def infer_task_responsibilities(
    task: str,
    goal: str,
    design_scope: list[str],
    owned_paths: list[str],
) -> list[str]:
    tokens = set(tokenize(task) + tokenize(goal))
    responsibilities: list[str] = []

    if "home-screen" in design_scope:
        responsibilities.append("Keep the task scoped to the home-screen surface and its immediately visible UI states.")
    if "top-bar" in design_scope or {"topbar", "header"} & tokens:
        responsibilities.append("Own the top-bar row: title/branding, category navigation, right-side status cluster, and focus/selection behavior for that row.")
    if {"action", "actions", "button", "buttons"} & tokens:
        responsibilities.append("Own the action-button row for this task: labels, icon alignment, focus treatment, and spacing within the declared scope.")
    if "search" in design_scope or "search" in tokens:
        responsibilities.append("Own the search flow inside scope: entry surface, search input/history/results states, and source/filter affordances when present.")
    if "player" in design_scope or {"player", "playback"} & tokens:
        responsibilities.append("Own the player-facing UI for this task: playback chrome, progress/controls overlay, and relevant full-screen or dialog states.")
    if "favorites" in design_scope or {"favorite", "favorites"} & tokens:
        responsibilities.append("Own the favorites surface for this task: list states, action entry points, and persistence-triggered UI updates that stay inside scope.")
    if "history" in design_scope or "history" in tokens:
        responsibilities.append("Own the history surface for this task: recent items presentation, empty state, and navigation behavior inside scope.")
    if "settings" in design_scope or {"setting", "settings", "config"} & tokens:
        responsibilities.append("Own the settings/config surface for this task: row layout, section grouping, and interaction states inside scope.")
    if {"sidebar", "menu"} & tokens or "sidebar-or-menu" in design_scope:
        responsibilities.append("Own the sidebar/menu presentation for this task: information architecture, focus order, and open/close behavior in scope.")

    if any("\\ui\\" in item.lower() or item.lower().endswith("\\ui\\screens") or "\\screens" in item.lower() for item in owned_paths):
        responsibilities.append("Cover loading, empty, error, selected, and focused states for the owned UI area instead of only the ideal/default visual state.")
    if any("\\theme" in item.lower() or "\\components" in item.lower() for item in owned_paths):
        responsibilities.append("Keep shared UI primitives consistent: only change theme/components that are necessary for the declared scope, and avoid accidental global visual drift.")
    if any("\\data" in item.lower() or "\\repository" in item.lower() or "\\viewmodel" in item.lower() for item in owned_paths):
        responsibilities.append("Keep data/state changes limited to what this task needs; do not reshape unrelated repositories, parsers, or ViewModel contracts without expanding the task contract.")

    if not responsibilities:
        responsibilities.append("Keep all edits focused on the declared owned paths and the task goal; avoid broad refactors or unrelated UI/behavior changes.")

    return responsibilities


def infer_task_validation(
    root: Path,
    task: str,
    goal: str,
    design_scope: list[str],
    owned_paths: list[str],
) -> list[str]:
    tokens = set(tokenize(task) + tokenize(goal))
    validation: list[str] = []

    if (root / "gradlew.bat").exists() and any("\\app" in item.lower() or "\\ui\\" in item.lower() or "\\viewmodel" in item.lower() or "\\data" in item.lower() for item in owned_paths):
        validation.append(r".\gradlew.bat :app:assembleDebug")

    if any("\\ui\\" in item.lower() or "\\screens" in item.lower() or "\\components" in item.lower() for item in owned_paths):
        validation.append("Verify the owned screen/section visually, including focus/selected states, not just static layout.")
        if {"tv", "topbar", "header", "sidebar", "menu", "button", "buttons"} & tokens or {"home-screen", "top-bar", "sidebar-or-menu"} & set(design_scope):
            validation.append("Test TV or keyboard focus traversal across the owned controls and confirm no focus traps or skipped items.")

    if any("\\data" in item.lower() or "\\repository" in item.lower() or "\\viewmodel" in item.lower() for item in owned_paths):
        validation.append("Verify the real data/state path for the owned flow, including empty/error handling when relevant.")

    validation.append("Run session continuity status before final response: `python C:\\Users\\QY\\.codex\\skills\\codex-session-continuity\\scripts\\session_continuity.py status --root auto`")
    validation.append("Confirm no edits leaked into Avoid Paths before finishing the task.")
    return validation


def session_dir(root: Path) -> Path:
    return root / ".codex" / "session"


def session_assets_dir(root: Path) -> Path:
    return session_dir(root) / "assets"


def parse_index_entries(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:]
        if ": " not in body:
            continue
        key, value = body.split(": ", 1)
        if key == "Path or source" and current:
            entries.append(current)
            current = {}
        current[key] = value.strip()
    if current:
        entries.append(current)
    return entries


def clean_value(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def local_path_from_entry(entry: dict[str, str]) -> Path | None:
    value = clean_value(entry.get("Path or source", ""))
    if not value or value.lower().startswith("description only"):
        return None
    if re.match(r"^[A-Za-z]:\\", value) or value.startswith("/"):
        return Path(value).expanduser()
    return None


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def age_days(path: Path) -> int:
    modified = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
    delta = dt.datetime.now(dt.timezone.utc) - modified
    return max(0, int(delta.total_seconds() // 86400))


def gather_index_state(root: Path) -> dict[str, object]:
    base = session_dir(root)
    assets_entries = parse_index_entries(base / "ASSETS.md")
    debug_entries = parse_index_entries(base / "DEBUG_SCREENSHOTS.md")
    referenced: dict[Path, dict[str, str]] = {}
    missing: list[tuple[Path, dict[str, str], str]] = []

    for source_name, entries in [("ASSETS.md", assets_entries), ("DEBUG_SCREENSHOTS.md", debug_entries)]:
        for entry in entries:
            local_path = local_path_from_entry(entry)
            if local_path is None:
                continue
            resolved = local_path.resolve()
            entry_copy = dict(entry)
            entry_copy["_source"] = source_name
            referenced[resolved] = entry_copy
            if not resolved.exists():
                missing.append((resolved, entry_copy, source_name))

    session_asset_files = []
    assets_root = session_assets_dir(root)
    if assets_root.exists():
        session_asset_files = [p.resolve() for p in assets_root.rglob("*") if p.is_file()]

    debug_artifacts_root = root / "debug-artifacts"
    debug_artifact_files = []
    if debug_artifacts_root.exists():
        debug_artifact_files = [p.resolve() for p in debug_artifacts_root.rglob("*") if p.is_file()]

    unreferenced_session_assets = [p for p in session_asset_files if p not in referenced]
    unreferenced_debug_artifacts = [p for p in debug_artifact_files if p not in referenced]

    stale_entries: list[tuple[Path, dict[str, str]]] = []
    fixed_entries: list[tuple[Path, dict[str, str]]] = []
    for entry in debug_entries:
        local_path = local_path_from_entry(entry)
        if local_path is None:
            continue
        resolved = local_path.resolve()
        status = entry.get("Status", "").strip()
        if status == "stale-delete-soon":
            stale_entries.append((resolved, entry))
        if status == "fixed-awaiting-cleanup":
            fixed_entries.append((resolved, entry))

    return {
        "assets_entries": assets_entries,
        "debug_entries": debug_entries,
        "referenced": referenced,
        "missing": missing,
        "unreferenced_session_assets": unreferenced_session_assets,
        "unreferenced_debug_artifacts": unreferenced_debug_artifacts,
        "stale_entries": stale_entries,
        "fixed_entries": fixed_entries,
    }


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


def task_template(
    root: Path,
    task: str = "[set-task-id]",
    goal: str = "[describe-goal]",
    status: str = "active",
    scope: list[str] | None = None,
    avoid: list[str] | None = None,
    design_scope: list[str] | None = None,
    responsibilities: list[str] | None = None,
    validation: list[str] | None = None,
    worktree_path: Path | None = None,
    branch_name: str | None = None,
) -> str:
    branch = branch_name or git_value(root, "branch", "--show-current")
    worktree = (worktree_path or Path.cwd()).resolve()
    scope = scope or ["[add-owned-paths]"]
    avoid = avoid or ["[add-avoid-paths-or-use-none]"]
    design_scope = design_scope or ["[add-design-or-feature-scope]"]
    responsibilities = responsibilities or ["[add-module-responsibilities]"]
    validation = validation or ["[add-validation-steps]"]
    scope_lines = "\n".join(f"- {item}" for item in scope)
    avoid_lines = "\n".join(f"- {item}" for item in avoid)
    design_lines = "\n".join(f"- {item}" for item in design_scope)
    responsibilities_lines = "\n".join(f"- {item}" for item in responsibilities)
    validation_lines = "\n".join(f"- {item}" for item in validation)
    return f"""# Task Contract

Updated: {now()}
Root: {root}
Worktree path: {worktree}
Git branch: {branch}
Task id: {task}
Status: {status}

## Goal

- {goal}

## Owned Paths

{scope_lines}

## Avoid Paths

{avoid_lines}

## Design Scope

{design_lines}

## Module Responsibilities

{responsibilities_lines}

## Related Assets

- Add relevant entries from `ASSETS.md`.

## Related Debug Captures

- Add relevant entries from `DEBUG_SCREENSHOTS.md`.

## Validation

{validation_lines}

## Change Guardrails

- Stay within `Owned Paths` unless this file is updated first.
- If work requires editing outside scope, update the contract and explain why.
- If another parallel task likely touches the same file, reconcile scope before editing.
- Prefer a dedicated Git worktree for this task. Use sparse-checkout when the scope is narrow and file-level isolation would help.
"""


def task_handoff_template(
    root: Path,
    task: str,
    goal: str,
    branch_name: str,
    worktree_path: Path,
    base_branch: str,
    source_project_root: Path,
    scope: list[str] | None = None,
    avoid: list[str] | None = None,
    design_scope: list[str] | None = None,
    responsibilities: list[str] | None = None,
    validation: list[str] | None = None,
) -> str:
    scope = scope or ["[add-owned-paths]"]
    avoid = avoid or ["[add-avoid-paths-or-use-none]"]
    design_scope = design_scope or ["[add-design-or-feature-scope]"]
    responsibilities = responsibilities or ["[add-module-responsibilities]"]
    validation = validation or ["[add-validation-steps]"]
    scope_lines = "\n".join(f"- {item}" for item in scope)
    avoid_lines = "\n".join(f"- {item}" for item in avoid)
    design_lines = "\n".join(f"- {item}" for item in design_scope)
    responsibilities_lines = "\n".join(f"- {item}" for item in responsibilities)
    validation_lines = "\n".join(f"- {item}" for item in validation)
    return f"""# Active Handoff

Updated: {now()}
Root: {root}
Git branch: {branch_name}

## Current Objective

- {goal}

## Current State

- Task worktree opened for `{task}` from source project root `{source_project_root}`.
- Base branch for this task is `{base_branch}`.
- Current worktree path is `{worktree_path}`.
- This handoff was seeded from `task-open` with an initial task contract summary so a fresh Codex thread can start immediately.

## Task Boundaries

### Owned Paths

{scope_lines}

### Avoid Paths

{avoid_lines}

### Design Scope

{design_lines}

## Module Responsibilities

{responsibilities_lines}

## Important Files

- `.codex/session/TASK.md`
- `.codex/session/PROJECT.md`
- `.codex/session/ASSETS.md`
- `.codex/session/DEBUG_SCREENSHOTS.md`

## Commands And Verification

{validation_lines}

## Risks And Assumptions

- Stay inside `Owned Paths` unless `TASK.md` is updated first.
- If the task needs edits outside scope, update the task contract before coding.

## Next Steps

1. Confirm or refine the seeded task contract before editing code.
2. Register any design references in `ASSETS.md` and debug captures in `DEBUG_SCREENSHOTS.md`.
3. Start implementation only after the task boundaries and validation plan look correct.
"""


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def replace_updated_stamp(text: str) -> str:
    if not text:
        return text
    return re.sub(r"^Updated: .*$", f"Updated: {now()}", text, count=1, flags=re.MULTILINE)


def upsert_h2_section(text: str, title: str, body_lines: list[str]) -> str:
    body = "\n".join(body_lines).rstrip()
    replacement = f"## {title}\n\n{body}\n"
    pattern = re.compile(rf"^## {re.escape(title)}\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    if pattern.search(text):
        return pattern.sub(lambda _m: replacement, text)
    suffix = "" if text.endswith("\n") else "\n"
    return f"{text}{suffix}\n{replacement}"


def archive_task_snapshot(
    current_project_root: Path,
    target_project_root: Path,
    branch_name: str,
    task_id: str,
) -> Path:
    current_archive_root = session_dir(current_project_root) / "archive" / "closed-tasks"
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    archive_dir = current_archive_root / f"{slugify(task_id or branch_name)}-{stamp}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    source_base = session_dir(target_project_root)
    for name in ["HANDOFF.md", "TASK.md", "ASSETS.md", "DEBUG_SCREENSHOTS.md", "DECISIONS.md"]:
        src = source_base / name
        if src.exists():
            shutil.copy2(src, archive_dir / name)
    return archive_dir


def infer_task_id(target_project_root: Path, fallback_branch: str) -> str:
    task_path = session_dir(target_project_root) / "TASK.md"
    text = read_text_if_exists(task_path)
    match = re.search(r"^Task id: (.+)$", text, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()
    return slugify(fallback_branch or "task")


def target_project_root_from_worktree(current_project_root: Path, target_worktree: Path) -> Path:
    return target_project_root_in_worktree(current_project_root, target_worktree)


def assets_template(root: Path) -> str:
    return f"""# Asset Index

Updated: {now()}
Root: {root}

## Active Assets

- Add only user-provided assets that the task actually depends on: design/UI references, bug screenshots, PDFs, mockups, reference files, generated assets, or other external artifacts that future Codex sessions may need.

## Recording Format

- Path or source: Where the file lives, or "description only" when the original attachment cannot be saved.
- Related task: Task id from `TASK.md`, or `shared-design` when the asset is intentionally cross-task.
- UI scope: Which screen/section this asset applies to.
- Status: `active-reference`, `partial-override`, `superseded`, or another short lifecycle label.
- Supersedes: Older asset id/description when this reference replaces a previous one.
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
- Related task: Task id from `TASK.md`, or `shared-debug` when intentionally cross-task.
- Affected scope: Which screen/feature/code area the screenshot helps verify or debug.
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
- Read `.codex/session/TASK.md` when present. Treat it as the current worktree's task contract.
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


def copy_or_write(src: Path, dst: Path, fallback: str) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copy2(src, dst)
        return f"copied  {src} -> {dst}"
    dst.write_text(fallback, encoding="utf-8", newline="\n")
    return f"created {dst}"


def seed_task_session(
    source_project_root: Path,
    target_project_root: Path,
    task: str,
    goal: str,
    branch_name: str,
    base_branch: str,
    worktree_path: Path,
    scope: list[str] | None,
    avoid: list[str] | None,
    design_scope: list[str] | None,
) -> list[str]:
    source_base = session_dir(source_project_root)
    target_base = session_dir(target_project_root)
    (target_base / "archive").mkdir(parents=True, exist_ok=True)
    messages = [
        copy_or_write(source_base / "PROJECT.md", target_base / "PROJECT.md", project_template(target_project_root)),
        copy_or_write(source_base / "DECISIONS.md", target_base / "DECISIONS.md", decisions_template(target_project_root)),
    ]
    scope = scope or ["[add-owned-paths]"]
    avoid = avoid or ["[add-avoid-paths-or-use-none]"]
    design_scope = design_scope or ["[add-design-or-feature-scope]"]
    responsibilities = infer_task_responsibilities(task, goal, design_scope, scope)
    validation = infer_task_validation(target_project_root, task, goal, design_scope, scope)
    (target_base / "HANDOFF.md").write_text(
        task_handoff_template(
            root=target_project_root,
            task=task,
            goal=goal,
            branch_name=branch_name,
            worktree_path=worktree_path,
            base_branch=base_branch,
            source_project_root=source_project_root,
            scope=scope,
            avoid=avoid,
            design_scope=design_scope,
            responsibilities=responsibilities,
            validation=validation,
        ),
        encoding="utf-8",
        newline="\n",
    )
    messages.append(f"created {target_base / 'HANDOFF.md'}")
    (target_base / "TASK.md").write_text(
        task_template(
            root=target_project_root,
            task=task,
            goal=goal,
            status="active",
            scope=scope,
            avoid=avoid,
            design_scope=design_scope,
            responsibilities=responsibilities,
            validation=validation,
            worktree_path=worktree_path,
            branch_name=branch_name,
        ),
        encoding="utf-8",
        newline="\n",
    )
    messages.append(f"created {target_base / 'TASK.md'}")
    messages.append(write_if_missing(target_base / "ASSETS.md", assets_template(target_project_root)))
    messages.append(write_if_missing(target_base / "DEBUG_SCREENSHOTS.md", debug_screenshots_template(target_project_root)))
    messages.append(ensure_gitignore(target_project_root))
    messages.append(ensure_project_agents(target_project_root))
    return messages


def cmd_init(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    base = session_dir(root)
    (base / "archive").mkdir(parents=True, exist_ok=True)
    messages = [
        write_if_missing(base / "PROJECT.md", project_template(root)),
        write_if_missing(base / "HANDOFF.md", handoff_template(root)),
        write_if_missing(base / "TASK.md", task_template(root)),
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
    for name in ["PROJECT.md", "HANDOFF.md", "TASK.md", "ASSETS.md", "DEBUG_SCREENSHOTS.md", "DECISIONS.md"]:
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
        if name == "TASK.md" and lines > args.max_task_lines:
            label = "warn: simplify task contract"
        if name == "DEBUG_SCREENSHOTS.md" and lines > args.max_debug_lines:
            label = "warn: prune stale debug captures"
        print(f"{name}: {lines} lines, {words} words, {len(text)} chars [{label}]")


def cmd_cleanup_report(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    state = gather_index_state(root)
    print(f"root: {root}")
    print(f"referenced files: {len(state['referenced'])}")
    print(f"missing referenced files: {len(state['missing'])}")
    for path, entry, source in state["missing"]:
        print(f"missing [{source}] {path}")
        if entry.get('Related task'):
            print(f"  task: {entry['Related task']}")
        if entry.get('Status'):
            print(f"  status: {entry['Status']}")

    print(f"stale-delete-soon entries: {len(state['stale_entries'])}")
    for path, entry in state["stale_entries"]:
        print(f"stale {path}")
        if entry.get('Related task'):
            print(f"  task: {entry['Related task']}")
        if entry.get('Affected scope'):
            print(f"  scope: {entry['Affected scope']}")

    print(f"fixed-awaiting-cleanup entries: {len(state['fixed_entries'])}")
    for path, entry in state["fixed_entries"]:
        print(f"fixed {path}")
        if entry.get('Related task'):
            print(f"  task: {entry['Related task']}")
        if entry.get('Affected scope'):
            print(f"  scope: {entry['Affected scope']}")

    print(f"unreferenced session assets: {len(state['unreferenced_session_assets'])}")
    for path in state["unreferenced_session_assets"]:
        if age_days(path) >= args.min_age_days:
            print(f"orphan-session-asset {path} age_days={age_days(path)}")

    print(f"unreferenced debug-artifacts files: {len(state['unreferenced_debug_artifacts'])}")
    for path in state["unreferenced_debug_artifacts"]:
        if age_days(path) >= args.min_age_days:
            print(f"orphan-debug-artifact {path} age_days={age_days(path)}")


def cmd_cleanup_apply(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    state = gather_index_state(root)
    delete_paths: list[Path] = []

    for path, _entry in state["stale_entries"]:
        if path.exists() and path_is_within(path, root):
            delete_paths.append(path)

    if args.include_fixed:
        for path, _entry in state["fixed_entries"]:
            if path.exists() and path_is_within(path, root):
                delete_paths.append(path)

    if args.include_orphan_session_assets:
        for path in state["unreferenced_session_assets"]:
            if path.exists() and path_is_within(path, root) and age_days(path) >= args.min_age_days:
                delete_paths.append(path)

    if args.include_orphan_debug_artifacts:
        for path in state["unreferenced_debug_artifacts"]:
            if path.exists() and path_is_within(path, root) and age_days(path) >= args.min_age_days:
                delete_paths.append(path)

    unique_paths = []
    seen = set()
    for path in delete_paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(resolved)

    if not unique_paths:
        print("nothing to delete")
        return

    if not args.apply:
        print("dry-run candidates:")
        for path in unique_paths:
            print(path)
        print("re-run with --apply to delete")
        return

    for path in unique_paths:
        if path.is_file():
            path.unlink()
            print(f"deleted {path}")


def cmd_cleanup_auto(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    state = gather_index_state(root)
    print(f"root: {root}")
    print("auto cleanup policy:")
    print("- delete stale-delete-soon entries")
    print("- delete fixed-awaiting-cleanup entries")
    print("- optionally delete orphan session assets older than the threshold")
    print("- do not auto-delete orphan debug-artifacts unless explicitly requested elsewhere")
    delete_paths: list[Path] = []

    for path, _entry in state["stale_entries"]:
        if path.exists() and path_is_within(path, root):
            delete_paths.append(path.resolve())
    for path, _entry in state["fixed_entries"]:
        if path.exists() and path_is_within(path, root):
            delete_paths.append(path.resolve())
    for path in state["unreferenced_session_assets"]:
        if path.exists() and path_is_within(path, root) and age_days(path) >= args.min_age_days:
            delete_paths.append(path.resolve())

    unique_paths = []
    seen = set()
    for path in delete_paths:
        if path in seen:
            continue
        seen.add(path)
        unique_paths.append(path)

    print(f"candidates: {len(unique_paths)}")
    for path in unique_paths:
        print(path)
    print(f"orphan debug-artifacts still requiring manual review: {len(state['unreferenced_debug_artifacts'])}")

    if not args.apply:
        print("re-run with --apply to perform the safe auto cleanup")
        return

    for path in unique_paths:
        if path.is_file():
            path.unlink()
            print(f"deleted {path}")


def cmd_task_init(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    base = session_dir(root)
    base.mkdir(parents=True, exist_ok=True)
    task_path = base / "TASK.md"
    scope = args.scope or ["[add-owned-paths]"]
    avoid = args.avoid or ["[add-avoid-paths-or-use-none]"]
    design_scope = args.design_scope or ["[add-design-or-feature-scope]"]
    responsibilities = infer_task_responsibilities(args.task, args.goal, design_scope, scope)
    validation = infer_task_validation(root, args.task, args.goal, design_scope, scope)
    content = task_template(
        root=root,
        task=args.task,
        goal=args.goal,
        status=args.status,
        scope=scope,
        avoid=avoid,
        design_scope=design_scope,
        responsibilities=responsibilities,
        validation=validation,
    )
    task_path.write_text(content, encoding="utf-8", newline="\n")
    print(f"updated {task_path}")


def cmd_task_open(args: argparse.Namespace) -> None:
    source_project_root = resolve_root(args.root)
    repo_root = git_repo_root(source_project_root)
    base_branch = args.base or git_current_branch(repo_root)
    branch_name = args.branch or default_task_branch(args.task)
    worktree_path = Path(args.worktree).expanduser().resolve() if args.worktree else default_worktree_path(source_project_root, args.task)
    records = git_worktree_records(repo_root)
    suggestions = suggest_task_contract(source_project_root, args.task, args.goal)
    scope = args.scope or list(suggestions["owned"])
    avoid = args.avoid or list(suggestions["avoid"])
    design_scope = args.design_scope or list(suggestions["design_scope"])
    responsibilities = infer_task_responsibilities(args.task, args.goal, design_scope, scope)
    validation = infer_task_validation(source_project_root, args.task, args.goal, design_scope, scope)

    source_clean = git_is_clean(repo_root)
    if args.apply and not args.allow_dirty_source and not source_clean:
        raise SystemExit("Source repository has uncommitted changes. Commit/stash first or use --allow-dirty-source.")

    for record in records:
        branch_ref = record.get("branch", "")
        if branch_ref == f"refs/heads/{branch_name}":
            raise SystemExit(f"Branch already checked out in another worktree: {record.get('worktree', '')}")

    branch_exists = git_branch_exists(repo_root, branch_name)
    if worktree_path.exists() and any(worktree_path.iterdir()):
        raise SystemExit(f"Target worktree path is not empty: {worktree_path}")

    target_project_root = target_project_root_in_worktree(source_project_root, worktree_path)
    rel = project_relative_to_repo(source_project_root)

    if not args.apply:
        print(f"dry-run task-open")
        print(f"repo_root: {repo_root}")
        print(f"source_project_root: {source_project_root}")
        print(f"project_relative_path: {rel}")
        print(f"source_clean: {source_clean}")
        if not source_clean and not args.allow_dirty_source:
            print("warning: source repository is dirty; apply would fail unless you commit/stash first or use --allow-dirty-source")
        print(f"base_branch: {base_branch}")
        print(f"branch_name: {branch_name}")
        print(f"worktree_path: {worktree_path}")
        print(f"target_project_root: {target_project_root}")
        print(f"branch_exists: {branch_exists}")
        print(f"suggested_scope_confidence: {suggestions['confidence']}")
        print("owned_paths:")
        for item in scope:
            print(f"- {item}")
        print("avoid_paths:")
        for item in avoid:
            print(f"- {item}")
        print("design_scope:")
        for item in design_scope:
            print(f"- {item}")
        print("module_responsibilities:")
        for item in responsibilities:
            print(f"- {item}")
        print("validation:")
        for item in validation:
            print(f"- {item}")
        print("re-run with --apply to create the worktree and task memory")
        return

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    if branch_exists:
        git_run(repo_root, "worktree", "add", str(worktree_path), branch_name)
    else:
        git_run(repo_root, "worktree", "add", "-b", branch_name, str(worktree_path), base_branch)

    messages = seed_task_session(
        source_project_root=source_project_root,
        target_project_root=target_project_root,
        task=args.task,
        goal=args.goal,
        branch_name=branch_name,
        base_branch=base_branch,
        worktree_path=worktree_path,
        scope=scope,
        avoid=avoid,
        design_scope=design_scope,
    )
    print(f"created worktree {worktree_path}")
    print(f"project root {target_project_root}")
    for message in messages:
        print(message)


def cmd_task_close(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    repo_root = git_repo_root(root)
    current_worktree_root = repo_root.resolve()
    target_worktree = Path(args.target_worktree).expanduser().resolve() if args.target_worktree else current_worktree_root
    target_branch = args.branch or git_current_branch(target_worktree)
    base_branch = args.base
    records = git_worktree_records(repo_root)

    target_record = None
    for record in records:
        if Path(record.get("worktree", "")).resolve() == target_worktree:
            target_record = record
            break

    target_exists = target_worktree.exists()
    if not target_branch and target_record:
        ref = target_record.get("branch", "")
        if ref.startswith("refs/heads/"):
            target_branch = ref.removeprefix("refs/heads/")
    target_clean = git_is_clean(target_worktree) if target_exists else False
    branch_exists = bool(target_branch) and git_branch_exists(repo_root, target_branch)
    merged = False
    if branch_exists and target_branch == base_branch:
        merged = True
    elif branch_exists and target_branch != base_branch:
        merged = git_run(repo_root, "merge-base", "--is-ancestor", target_branch, base_branch, check=False).returncode == 0
    is_current_process_worktree = target_worktree == current_worktree_root

    print(f"target_worktree: {target_worktree}")
    print(f"target_exists: {target_exists}")
    print(f"target_branch: {target_branch}")
    print(f"branch_exists: {branch_exists}")
    print(f"base_branch: {base_branch}")
    print(f"merged_into_base: {merged}")
    print(f"worktree_clean: {target_clean}")
    print(f"registered_worktree: {bool(target_record)}")
    print(f"current_process_worktree: {is_current_process_worktree}")

    if not args.apply:
        print("dry-run task-close")
        print("re-run with --apply after confirming the branch is merged and the worktree is clean")
        return

    if not target_branch or target_branch == base_branch:
        raise SystemExit("Refusing to close the base branch/current default branch.")
    if not branch_exists:
        raise SystemExit(f"Branch does not exist: {target_branch}")
    if not merged:
        raise SystemExit(f"Branch {target_branch} is not merged into {base_branch}.")
    if target_exists and not target_clean:
        raise SystemExit(f"Target worktree is not clean: {target_worktree}")
    if is_current_process_worktree:
        raise SystemExit("Refusing to remove the current worktree from inside itself. Run task-close from another worktree/root and pass --target-worktree.")

    if target_record and target_exists and not args.keep_worktree:
        git_run(repo_root, "worktree", "remove", str(target_worktree))
        print(f"removed worktree {target_worktree}")
    else:
        print(f"kept worktree {target_worktree}")

    if not args.keep_branch:
        git_run(repo_root, "branch", "-d", target_branch)
        print(f"deleted branch {target_branch}")
    else:
        print(f"kept branch {target_branch}")


def cmd_task_finish(args: argparse.Namespace) -> None:
    current_project_root = resolve_root(args.root)
    repo_root = git_repo_root(current_project_root)
    current_worktree_root = repo_root.resolve()
    records = git_worktree_records(repo_root)

    merge_from = args.merge_from
    target_branch = args.branch or merge_from
    target_record = find_worktree_record_by_branch(records, target_branch) if target_branch else None
    if args.target_worktree:
        target_worktree = Path(args.target_worktree).expanduser().resolve()
    elif target_record:
        target_worktree = Path(target_record.get("worktree", "")).resolve()
    else:
        target_worktree = current_worktree_root
    target_project_root = target_project_root_from_worktree(current_project_root, target_worktree)

    if not target_record:
        for record in records:
            if Path(record.get("worktree", "")).resolve() == target_worktree:
                target_record = record
                break

    if not target_branch and target_record:
        ref = target_record.get("branch", "")
        if ref.startswith("refs/heads/"):
            target_branch = ref.removeprefix("refs/heads/")
    if not target_branch and target_worktree.exists():
        target_branch = git_current_branch(target_worktree)
    base_branch = args.base
    target_exists = target_worktree.exists()
    branch_exists = bool(target_branch) and git_branch_exists(repo_root, target_branch)
    current_base_branch = git_current_branch(current_worktree_root)
    base_worktree_clean = git_is_clean(current_worktree_root)
    merged = False
    if branch_exists and target_branch == base_branch:
        merged = True
    elif branch_exists and target_branch != base_branch:
        merged = git_run(repo_root, "merge-base", "--is-ancestor", target_branch, base_branch, check=False).returncode == 0
    worktree_clean = git_is_clean(target_worktree) if target_exists else False
    task_id = infer_task_id(target_project_root, target_branch or "task")
    cleanup_state = gather_index_state(target_project_root)
    auto_cleanup_candidates = len(cleanup_state["stale_entries"]) + len(cleanup_state["fixed_entries"])
    can_merge = bool(merge_from) and branch_exists and target_branch == merge_from and current_base_branch == base_branch and base_worktree_clean and target_worktree != current_worktree_root
    missing_target_worktree = not target_exists and target_worktree != current_worktree_root

    if missing_target_worktree:
        print(f"target_worktree: {target_worktree}")
        print(f"target_exists: {target_exists}")
        print(f"target_branch: {target_branch}")
        print(f"branch_exists: {branch_exists}")
        print(f"base_branch: {base_branch}")
        print(f"merged_into_base: {merged}")
        print(f"base_worktree_branch: {current_base_branch}")
        print(f"base_worktree_clean: {base_worktree_clean}")
        print("target worktree does not exist; task-finish will not write handoff/task files for a non-existent worktree")
        if args.apply:
            raise SystemExit("Refusing to apply task-finish because the target worktree does not exist.")
        print("dry-run task-finish")
        return

    if args.apply and merge_from:
        if not branch_exists:
            raise SystemExit(f"Merge source branch does not exist: {merge_from}")
        if current_base_branch != base_branch:
            raise SystemExit(f"Current worktree is on branch {current_base_branch}, expected base branch {base_branch}.")
        if not base_worktree_clean:
            raise SystemExit(f"Base worktree is not clean: {current_worktree_root}")
        if target_worktree == current_worktree_root:
            raise SystemExit("Refusing to merge and close a task from inside the same worktree. Run this from the base worktree and point --target-worktree at the task worktree.")
        merge_result = git_run(current_worktree_root, "merge", "--no-ff", "--no-edit", merge_from, check=False)
        if merge_result.returncode != 0:
            raise SystemExit(f"Merge failed for {merge_from} into {base_branch}.\nSTDOUT:\n{merge_result.stdout}\nSTDERR:\n{merge_result.stderr}")
        merged = True
        base_worktree_clean = git_is_clean(current_worktree_root)

    can_auto_close = bool(target_branch) and branch_exists and merged and target_exists and worktree_clean and target_worktree != current_worktree_root

    handoff_path = session_dir(target_project_root) / "HANDOFF.md"
    handoff_text = read_text_if_exists(handoff_path) or handoff_template(target_project_root)
    handoff_text = replace_updated_stamp(handoff_text)
    finish_lines = [
        f"- Task id: `{task_id}`",
        f"- Target worktree: `{target_worktree}`",
        f"- Target project root: `{target_project_root}`",
        f"- Target branch: `{target_branch}`",
        f"- Base branch: `{base_branch}`",
        f"- Merge from: `{merge_from}`",
        f"- Branch exists: `{branch_exists}`",
        f"- Merged into base: `{merged}`",
        f"- Worktree exists: `{target_exists}`",
        f"- Worktree clean: `{worktree_clean}`",
        f"- Base worktree branch: `{current_base_branch}`",
        f"- Base worktree clean: `{base_worktree_clean}`",
        f"- Merge eligible: `{can_merge}`",
        f"- Cleanup report: stale={len(cleanup_state['stale_entries'])}, fixed={len(cleanup_state['fixed_entries'])}, orphan-session-assets={len(cleanup_state['unreferenced_session_assets'])}, orphan-debug-artifacts={len(cleanup_state['unreferenced_debug_artifacts'])}",
        f"- Auto-close eligible: `{can_auto_close}`",
    ]
    if args.note:
        finish_lines.append(f"- Finish note: {args.note}")
    handoff_text = upsert_h2_section(handoff_text, "Finish Review", finish_lines)
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(handoff_text, encoding="utf-8", newline="\n")

    task_path = session_dir(target_project_root) / "TASK.md"
    task_text = read_text_if_exists(task_path)
    if task_text:
        if can_auto_close and args.apply:
            new_status = "closed"
        elif target_branch == base_branch:
            new_status = "finished-on-base-branch"
        elif merged:
            new_status = "merged-awaiting-close"
        else:
            new_status = "finished-awaiting-merge"
        task_text = replace_updated_stamp(task_text)
        task_text = re.sub(r"^Status: .*$", f"Status: {new_status}", task_text, count=1, flags=re.MULTILINE)
        task_path.write_text(task_text, encoding="utf-8", newline="\n")

    print(f"updated handoff {handoff_path}")
    if task_text:
        print(f"updated task contract {task_path}")
    print(f"cleanup summary: stale={len(cleanup_state['stale_entries'])}, fixed={len(cleanup_state['fixed_entries'])}, orphan-session-assets={len(cleanup_state['unreferenced_session_assets'])}, orphan-debug-artifacts={len(cleanup_state['unreferenced_debug_artifacts'])}")
    print(f"merge check: branch_exists={branch_exists} merged={merged} worktree_exists={target_exists} worktree_clean={worktree_clean} current_process_worktree={target_worktree == current_worktree_root}")

    if not args.apply:
        print("dry-run task-finish")
        if can_auto_close:
            print("eligible for automatic close; re-run with --apply to archive the task snapshot and remove the worktree/branch")
        else:
            print("not eligible for automatic close yet; handoff/task status were still refreshed")
        return

    if not can_auto_close:
        print("task-finish applied the handoff/task updates but did not close the task because the close conditions are not satisfied")
        return

    archive_dir = archive_task_snapshot(
        current_project_root=current_project_root,
        target_project_root=target_project_root,
        branch_name=target_branch or task_id,
        task_id=task_id,
    )
    print(f"archived task snapshot {archive_dir}")

    close_args = argparse.Namespace(
        root=str(current_project_root),
        target_worktree=str(target_worktree),
        branch=target_branch,
        base=base_branch,
        keep_worktree=False,
        keep_branch=False,
        apply=True,
    )
    cmd_task_close(close_args)


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

    task_init = sub.add_parser("task-init", help="Create or replace the current worktree task contract.")
    task_init.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    task_init.add_argument("--task", required=True, help="Task id or short slug.")
    task_init.add_argument("--goal", default="[describe-goal]", help="Short task goal.")
    task_init.add_argument("--status", default="active", help="Task status, for example active or paused.")
    task_init.add_argument("--scope", nargs="*", default=None, help="Owned paths for this task.")
    task_init.add_argument("--avoid", nargs="*", default=None, help="Paths to avoid changing in this task.")
    task_init.add_argument("--design-scope", nargs="*", default=None, help="Screens or UI areas this task owns.")
    task_init.set_defaults(func=cmd_task_init)

    task_open = sub.add_parser("task-open", help="Create a dedicated branch worktree and seed task-local memory.")
    task_open.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    task_open.add_argument("--task", required=True, help="Task id or short slug.")
    task_open.add_argument("--goal", required=True, help="Short task goal.")
    task_open.add_argument("--branch", help="Branch name. Defaults to codex/<task>.")
    task_open.add_argument("--base", help="Base branch to branch from. Defaults to the current branch.")
    task_open.add_argument("--worktree", help="Explicit worktree path. Defaults to a generated sibling worktree directory.")
    task_open.add_argument("--allow-dirty-source", action="store_true", help="Allow opening from a repository that has uncommitted changes.")
    task_open.add_argument("--scope", nargs="*", default=None, help="Owned paths for the new task contract.")
    task_open.add_argument("--avoid", nargs="*", default=None, help="Paths to avoid changing in the new task contract.")
    task_open.add_argument("--design-scope", nargs="*", default=None, help="Screens or UI areas the new task owns.")
    task_open.add_argument("--apply", action="store_true", help="Actually create the worktree and seed files. Without this flag, only show a dry run.")
    task_open.set_defaults(func=cmd_task_open)

    task_close = sub.add_parser("task-close", help="Safely remove a merged task worktree and delete its branch.")
    task_close.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    task_close.add_argument("--target-worktree", help="Target worktree root to close. Defaults to the current worktree root.")
    task_close.add_argument("--branch", help="Target branch. Defaults to the branch checked out in the target worktree.")
    task_close.add_argument("--base", default="main", help="Base branch that must already contain the task branch.")
    task_close.add_argument("--keep-worktree", action="store_true", help="Do not remove the worktree, only evaluate/delete the branch if allowed.")
    task_close.add_argument("--keep-branch", action="store_true", help="Do not delete the branch after checks pass.")
    task_close.add_argument("--apply", action="store_true", help="Actually remove the worktree and/or branch. Without this flag, only show a dry run.")
    task_close.set_defaults(func=cmd_task_close)

    task_finish = sub.add_parser("task-finish", help="Update handoff, run cleanup summary, check merge state, and auto-close when safe.")
    task_finish.add_argument("--root", default="auto", help="Current project root, or auto. Defaults to auto.")
    task_finish.add_argument("--target-worktree", help="Target task worktree root. Defaults to the current worktree root.")
    task_finish.add_argument("--branch", help="Target branch. Defaults to the branch checked out in the target worktree.")
    task_finish.add_argument("--merge-from", help="Merge this task branch into the base branch before attempting auto-close.")
    task_finish.add_argument("--base", default="main", help="Base branch that should already contain the task branch before auto-close.")
    task_finish.add_argument("--note", help="Optional finish note to store in the handoff.")
    task_finish.add_argument("--apply", action="store_true", help="Actually archive the task snapshot and close the task when conditions pass. Without this flag, only show a dry run.")
    task_finish.set_defaults(func=cmd_task_finish)

    cleanup_report = sub.add_parser("cleanup-report", help="Report stale or unreferenced screenshot/image files.")
    cleanup_report.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    cleanup_report.add_argument("--min-age-days", type=int, default=3, help="Minimum age for orphan-file reporting.")
    cleanup_report.set_defaults(func=cmd_cleanup_report)

    cleanup_apply = sub.add_parser("cleanup-apply", help="Delete stale screenshot/image files using explicit flags.")
    cleanup_apply.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    cleanup_apply.add_argument("--apply", action="store_true", help="Actually delete files. Without this flag, only show a dry run.")
    cleanup_apply.add_argument("--include-fixed", action="store_true", help="Also delete files marked fixed-awaiting-cleanup.")
    cleanup_apply.add_argument("--include-orphan-session-assets", action="store_true", help="Also delete unreferenced files under .codex/session/assets older than min-age-days.")
    cleanup_apply.add_argument("--include-orphan-debug-artifacts", action="store_true", help="Also delete unreferenced files under debug-artifacts older than min-age-days.")
    cleanup_apply.add_argument("--min-age-days", type=int, default=3, help="Minimum age for orphan-file deletion.")
    cleanup_apply.set_defaults(func=cmd_cleanup_apply)

    cleanup_auto = sub.add_parser("cleanup-auto", help="Apply the conservative automatic screenshot cleanup policy.")
    cleanup_auto.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    cleanup_auto.add_argument("--min-age-days", type=int, default=7, help="Minimum age for orphan session-asset deletion.")
    cleanup_auto.add_argument("--apply", action="store_true", help="Actually delete safe candidates. Without this flag, only show a dry run.")
    cleanup_auto.set_defaults(func=cmd_cleanup_auto)

    status = sub.add_parser("status", help="Show rough size of active session files.")
    status.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    status.add_argument("--max-handoff-lines", type=int, default=150, help="Warn when HANDOFF.md is longer than this.")
    status.add_argument("--max-project-lines", type=int, default=250, help="Warn when PROJECT.md is longer than this.")
    status.add_argument("--max-task-lines", type=int, default=120, help="Warn when TASK.md is longer than this.")
    status.add_argument("--max-debug-lines", type=int, default=120, help="Warn when DEBUG_SCREENSHOTS.md is longer than this.")
    status.set_defaults(func=cmd_status)

    where = sub.add_parser("where", help="Print the auto-detected project memory root.")
    where.add_argument("--root", default="auto", help="Project root, or auto. Defaults to auto.")
    where.set_defaults(func=cmd_where)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
