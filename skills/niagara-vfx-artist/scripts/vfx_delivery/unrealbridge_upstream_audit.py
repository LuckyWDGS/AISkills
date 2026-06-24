from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from .core import (
    default_report_path,
    load_json,
    normalize_cli_global_args_no_subcommand,
    resolve_root_context,
    save_json,
    utc_now_iso,
    write_text,
)


UPSTREAM_URL = "https://github.com/TornLux/UnrealBridge.git"
UPSTREAM_REF = "origin/main"
SKILL_UPSTREAM_ROOT = ".claude/skills/unreal-bridge"
PLUGIN_UPSTREAM_ROOT = "Plugin/UnrealBridge"

LOCAL_PLUGIN_OVERLAY_FILES = {
    "Source/UnrealBridge/Public/UnrealBridgeNiagaraLibrary.h": "Local Niagara bridge header; preserve local implementation.",
    "Source/UnrealBridge/Private/UnrealBridgeNiagaraLibrary.cpp": "Local Niagara bridge implementation; preserve local implementation.",
    "Source/UnrealBridge/Public/UnrealBridgeToolsetRegistryLibrary.h": "Local ToolsetRegistry bridge header; preserve local implementation.",
    "Source/UnrealBridge/Private/UnrealBridgeToolsetRegistryLibrary.cpp": "Local ToolsetRegistry bridge implementation; preserve local implementation.",
}

GENERATED_LOCAL_FILES = {
    ("skill", "scripts/bridge_manifest.json"): "Generated from the live local plugin surface; do not blindly replace with upstream.",
    ("plugin", "Content/Python/unreal_bridge.py"): "Generated from the live local plugin surface; keep or regenerate so local Niagara wrappers survive.",
}

CUSTOM_MERGE_FILES = {
    ("plugin", "Source/UnrealBridge/UnrealBridge.Build.cs"): "Merge upstream Build.cs, then re-inject local Niagara module dependencies.",
}

IGNORED_LOCAL_ARTIFACT_PREFIXES = (
    "Binaries/",
    "Intermediate/",
    "Saved/",
    "Content/Python/__pycache__/",
    "Content/Python/material_templates/__pycache__/",
)

LOCAL_NIAGARA_DEPENDENCY_MODULES = ("Niagara", "NiagaraEditor")


def sha256_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def sha256_text(path: Path) -> str:
    if not path.exists():
        return ""
    return sha256_bytes(path.read_bytes())


def run_git(
    args: list[str],
    cwd: Path | None = None,
    *,
    text: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        check=False,
    )


def ensure_upstream_repo(repo_dir: Path) -> dict:
    if (repo_dir / ".git").exists():
        fetch = run_git(["git", "fetch", "origin", "main"], cwd=repo_dir)
        status = run_git(["git", "status", "--short", "--branch"], cwd=repo_dir)
        return {
            "mode": "fetch",
            "returncode": fetch.returncode,
            "stdout": fetch.stdout,
            "stderr": fetch.stderr,
            "worktree_status": status.stdout,
            "worktree_dirty": bool(status.stdout.strip().splitlines()[1:]) if status.stdout else False,
        }
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    clone = run_git(["git", "clone", "--depth", "1", UPSTREAM_URL, str(repo_dir)])
    status = run_git(["git", "status", "--short", "--branch"], cwd=repo_dir) if clone.returncode == 0 else None
    return {
        "mode": "clone",
        "returncode": clone.returncode,
        "stdout": clone.stdout,
        "stderr": clone.stderr,
        "worktree_status": status.stdout if status else "",
        "worktree_dirty": False,
    }


def latest_commit(repo_dir: Path) -> dict:
    show = run_git(["git", "show", "--stat", "--oneline", f"{UPSTREAM_REF}", "-1"], cwd=repo_dir)
    return {"returncode": show.returncode, "stdout": show.stdout, "stderr": show.stderr}


def git_rev_parse(repo_dir: Path, ref: str) -> str:
    result = run_git(["git", "rev-parse", ref], cwd=repo_dir)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def git_ls_tree(repo_dir: Path, ref: str, prefix: str) -> list[str]:
    result = run_git(["git", "ls-tree", "-r", "--name-only", ref, "--", prefix], cwd=repo_dir)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def git_show_bytes(repo_dir: Path, ref: str, repo_path: str) -> bytes:
    result = run_git(["git", "show", f"{ref}:{repo_path}"], cwd=repo_dir, text=False)
    if result.returncode != 0:
        return b""
    return result.stdout


def plugin_public_headers(repo_dir: Path) -> list[str]:
    headers = git_ls_tree(repo_dir, UPSTREAM_REF, f"{PLUGIN_UPSTREAM_ROOT}/Source/UnrealBridge/Public")
    return sorted(Path(item).name for item in headers if item.endswith(".h"))


def relative_target_path(source_repo_path: str, source_root: str) -> str:
    prefix = f"{source_root}/"
    if source_repo_path == source_root:
        return ""
    if source_repo_path.startswith(prefix):
        return source_repo_path[len(prefix) :]
    return source_repo_path


def is_generated_file(target_kind: str, rel_path: str) -> bool:
    return (target_kind, rel_path) in GENERATED_LOCAL_FILES


def is_custom_merge_file(target_kind: str, rel_path: str) -> bool:
    return (target_kind, rel_path) in CUSTOM_MERGE_FILES


def is_overlay_file(target_kind: str, rel_path: str) -> bool:
    return target_kind == "plugin" and rel_path in LOCAL_PLUGIN_OVERLAY_FILES


def is_ignored_local_artifact(rel_path: str) -> bool:
    return any(rel_path.startswith(prefix) for prefix in IGNORED_LOCAL_ARTIFACT_PREFIXES)


def collect_local_files(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file()
    )


def classify_action(
    *,
    target_kind: str,
    rel_path: str,
    upstream_exists: bool,
    local_exists: bool,
    local_hash: str,
    upstream_hash: str,
) -> tuple[str, str]:
    if upstream_exists:
        if is_overlay_file(target_kind, rel_path):
            return "preserve_overlay", LOCAL_PLUGIN_OVERLAY_FILES[rel_path]
        if is_generated_file(target_kind, rel_path):
            return "regenerate", GENERATED_LOCAL_FILES[(target_kind, rel_path)]
        if is_custom_merge_file(target_kind, rel_path):
            return "custom_merge", CUSTOM_MERGE_FILES[(target_kind, rel_path)]
        if local_exists and local_hash == upstream_hash:
            return "unchanged", "Local file already matches upstream."
        return "copy", "Upstream changed or local file missing; copy upstream version."

    if is_overlay_file(target_kind, rel_path):
        return "preserve_overlay", LOCAL_PLUGIN_OVERLAY_FILES[rel_path]
    if is_generated_file(target_kind, rel_path):
        return "regenerate", GENERATED_LOCAL_FILES[(target_kind, rel_path)]
    if is_ignored_local_artifact(rel_path):
        return "ignored_local_artifact", "Generated binary/cache/build artifact outside upstream source control."
    return "local_only", "Local file has no upstream counterpart; inspect whether it is intentional local customization."


def build_target_plan(
    *,
    repo_dir: Path,
    target_kind: str,
    source_root: str,
    target_root: Path,
) -> dict:
    upstream_repo_files = git_ls_tree(repo_dir, UPSTREAM_REF, source_root)
    upstream_actions: list[dict] = []
    upstream_rel_set: set[str] = set()

    for repo_path in upstream_repo_files:
        rel_path = relative_target_path(repo_path, source_root)
        upstream_rel_set.add(rel_path)
        target_path = target_root / rel_path
        upstream_bytes = git_show_bytes(repo_dir, UPSTREAM_REF, repo_path)
        upstream_hash = sha256_bytes(upstream_bytes) if upstream_bytes else ""
        local_exists = target_path.exists()
        local_hash = sha256_text(target_path) if local_exists else ""
        status, reason = classify_action(
            target_kind=target_kind,
            rel_path=rel_path,
            upstream_exists=True,
            local_exists=local_exists,
            local_hash=local_hash,
            upstream_hash=upstream_hash,
        )
        upstream_actions.append(
            {
                "target_kind": target_kind,
                "relative_path": rel_path,
                "source_repo_path": repo_path,
                "target_path": str(target_path),
                "status": status,
                "reason": reason,
                "upstream_sha256": upstream_hash,
                "local_sha256": local_hash,
                "local_exists": local_exists,
            }
        )

    local_only_actions: list[dict] = []
    for rel_path in collect_local_files(target_root):
        if rel_path in upstream_rel_set:
            continue
        status, reason = classify_action(
            target_kind=target_kind,
            rel_path=rel_path,
            upstream_exists=False,
            local_exists=True,
            local_hash=sha256_text(target_root / rel_path),
            upstream_hash="",
        )
        local_only_actions.append(
            {
                "target_kind": target_kind,
                "relative_path": rel_path,
                "source_repo_path": "",
                "target_path": str(target_root / rel_path),
                "status": status,
                "reason": reason,
                "upstream_sha256": "",
                "local_sha256": sha256_text(target_root / rel_path),
                "local_exists": True,
            }
        )

    actions = upstream_actions + local_only_actions
    counts: dict[str, int] = {}
    for item in actions:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    return {
        "target_kind": target_kind,
        "source_root": source_root,
        "target_root": str(target_root),
        "counts": counts,
        "actions": actions,
    }


def merge_build_cs(upstream_text: str) -> str:
    merged = upstream_text
    missing = [module for module in LOCAL_NIAGARA_DEPENDENCY_MODULES if f'"{module}"' not in merged]
    if not missing:
        return merged

    insertion = "".join(f'\n\t\t\t"{module}",' for module in missing)
    anchor = '"MaterialEditor",'
    if anchor in merged:
        return merged.replace(anchor, anchor + insertion, 1)

    fallback = '"PoseSearch",'
    if fallback in merged:
        return merged.replace(fallback, insertion + "\n\t\t\t" + fallback, 1)

    block_end = "});"
    if block_end in merged:
        return merged.replace(block_end, insertion + "\n\t\t" + block_end, 1)
    return merged


def apply_action(repo_dir: Path, action: dict) -> dict:
    target_path = Path(action["target_path"])
    status = action["status"]
    result = {
        "relative_path": action["relative_path"],
        "status": status,
        "applied": False,
        "detail": action["reason"],
    }

    if status not in {"copy", "custom_merge"}:
        return result

    repo_path = action["source_repo_path"]
    upstream_bytes = git_show_bytes(repo_dir, UPSTREAM_REF, repo_path)
    if not upstream_bytes:
        result["detail"] = f"Failed to read upstream blob: {repo_path}"
        return result

    if status == "custom_merge":
        merged = merge_build_cs(upstream_bytes.decode("utf-8"))
        new_bytes = merged.encode("utf-8")
    else:
        new_bytes = upstream_bytes

    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and target_path.read_bytes() == new_bytes:
        result["applied"] = False
        result["detail"] = "Already up to date after merge/copy."
        return result

    target_path.write_bytes(new_bytes)
    result["applied"] = True
    result["detail"] = "Updated local target from upstream."
    return result


def discover_bridge_endpoint(local_bridge_script: Path, bridge_project: str) -> tuple[str, list[str]]:
    cmd = [
        sys.executable,
        str(local_bridge_script),
        f"--project={bridge_project}",
        "--json",
        "list-editors",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        return "", [f"list-editors failed: {result.stderr.strip() or result.stdout.strip()}"]
    try:
        editors = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return "", [f"Could not parse list-editors JSON: {exc}"]
    if not editors:
        return "", ["No live UnrealBridge editor found via list-editors."]

    project_path_lower = bridge_project.lower()
    for item in editors:
        project = str(item.get("project_path") or item.get("project") or "").lower()
        if project and (project_path_lower in project or project.endswith(Path(bridge_project).name.lower())):
            bind = item.get("tcp_bind") or "127.0.0.1"
            port = item.get("tcp_port")
            if bind and port:
                return f"{bind}:{port}", []

    first = editors[0]
    bind = first.get("tcp_bind") or "127.0.0.1"
    port = first.get("tcp_port")
    if bind and port:
        return f"{bind}:{port}", [f"Fell back to the first live editor endpoint: {bind}:{port}"]
    return "", ["list-editors returned entries but no usable tcp_bind/tcp_port."]


def ping_bridge_endpoint(local_bridge_script: Path, endpoint: str) -> tuple[bool, str]:
    cmd = [
        sys.executable,
        str(local_bridge_script),
        f"--endpoint={endpoint}",
        "--json",
        "ping",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return False, f"Could not parse ping JSON: {exc}"
    if not payload.get("success"):
        return False, payload.get("error") or "Bridge ping failed."
    if not payload.get("ready", False):
        return False, "Bridge responded but editor is not ready yet."
    return True, "pong"


def load_generator_module(upstream_dir: Path):
    generator_path = upstream_dir / "tools" / "gen_manifest.py"
    source = generator_path.read_text(encoding="utf-8")
    marker = "# ── Entry point"
    if marker in source:
        source = source.split(marker, 1)[0]
    namespace = {
        "__file__": str(generator_path),
        "__name__": "unrealbridge_gen_manifest_runtime",
    }
    exec(compile(source, str(generator_path), "exec"), namespace, namespace)
    return namespace


def regenerate_generated_surfaces(
    *,
    upstream_dir: Path,
    local_bridge_script: Path,
    local_skill_root: Path,
    local_plugin_root: Path,
    bridge_project: str,
    bridge_endpoint: str | None,
) -> dict:
    notes: list[str] = []
    endpoint = bridge_endpoint or ""
    if not endpoint:
        endpoint, discover_notes = discover_bridge_endpoint(local_bridge_script, bridge_project)
        notes.extend(discover_notes)

    if not endpoint:
        return {
            "attempted": False,
            "succeeded": False,
            "endpoint": "",
            "notes": notes + ["Could not discover a live UnrealBridge endpoint; preserved current generated files."],
        }

    ok, ping_note = ping_bridge_endpoint(local_bridge_script, endpoint)
    notes.append(ping_note)
    if not ok:
        return {
            "attempted": True,
            "succeeded": False,
            "endpoint": endpoint,
            "notes": notes + ["Endpoint did not pass ping/ready check; preserved current generated files."],
        }

    generator_path = upstream_dir / "tools" / "gen_manifest.py"
    cmd = [
        sys.executable,
        str(local_bridge_script),
        f"--endpoint={endpoint}",
        "--json",
        "exec-file",
        str(generator_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        return {
            "attempted": True,
            "succeeded": False,
            "endpoint": endpoint,
            "notes": notes + [f"bridge exec-file failed: {result.stderr.strip() or result.stdout.strip()}"],
        }

    try:
        bridge_payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "attempted": True,
            "succeeded": False,
            "endpoint": endpoint,
            "notes": notes + [f"Could not parse bridge exec JSON: {exc}"],
        }

    if not bridge_payload.get("success"):
        return {
            "attempted": True,
            "succeeded": False,
            "endpoint": endpoint,
            "notes": notes + [bridge_payload.get("error") or "Bridge exec returned success=false."],
        }

    try:
        manifest = json.loads(bridge_payload.get("output") or "")
    except json.JSONDecodeError as exc:
        return {
            "attempted": True,
            "succeeded": False,
            "endpoint": endpoint,
            "notes": notes + [f"Could not parse reflected manifest JSON: {exc}"],
        }

    manifest_out = local_skill_root / "scripts" / "bridge_manifest.json"
    save_json(manifest_out, manifest)

    generator = load_generator_module(upstream_dir)
    wrapper_src, wrapper_stats = generator["_generate_wrapper"](manifest)
    wrapper_out = local_plugin_root / "Content" / "Python" / "unreal_bridge.py"
    wrapper_out.parent.mkdir(parents=True, exist_ok=True)
    wrapper_out.write_text(wrapper_src, encoding="utf-8")

    return {
        "attempted": True,
        "succeeded": True,
        "endpoint": endpoint,
        "notes": notes,
        "manifest_out": str(manifest_out),
        "wrapper_out": str(wrapper_out),
        "wrapper_stats": wrapper_stats,
        "manifest_generated_at": manifest.get("generated_at", ""),
        "ue_version": manifest.get("ue_version", ""),
    }


def build_report(ctx, args: argparse.Namespace, previous_report: dict | None) -> dict:
    upstream_dir = Path(args.upstream_dir).resolve()
    sync_result = ensure_upstream_repo(upstream_dir)
    commit = latest_commit(upstream_dir)
    upstream_head = git_rev_parse(upstream_dir, UPSTREAM_REF)
    previous_upstream_head = str((previous_report or {}).get("upstream_head") or "")
    upstream_changed_since_last_audit = bool(previous_upstream_head and upstream_head and previous_upstream_head != upstream_head)

    local_bridge_script = Path(args.local_bridge_script).resolve()
    local_skill_root = Path(args.local_skill_root).resolve()
    local_plugin_root = Path(args.local_plugin_root).resolve()
    upstream_bridge_repo_path = f"{SKILL_UPSTREAM_ROOT}/scripts/bridge.py"

    local_bridge_hash = sha256_text(local_bridge_script)
    upstream_bridge_bytes = git_show_bytes(upstream_dir, UPSTREAM_REF, upstream_bridge_repo_path)
    upstream_bridge_hash = sha256_bytes(upstream_bridge_bytes) if upstream_bridge_bytes else ""

    upstream_headers = plugin_public_headers(upstream_dir)
    has_upstream_niagara_library = "UnrealBridgeNiagaraLibrary.h" in upstream_headers
    local_niagara_header = local_plugin_root / "Source" / "UnrealBridge" / "Public" / "UnrealBridgeNiagaraLibrary.h"
    has_local_niagara_library = local_niagara_header.exists()

    skill_plan = build_target_plan(
        repo_dir=upstream_dir,
        target_kind="skill",
        source_root=SKILL_UPSTREAM_ROOT,
        target_root=local_skill_root,
    )
    plugin_plan = build_target_plan(
        repo_dir=upstream_dir,
        target_kind="plugin",
        source_root=PLUGIN_UPSTREAM_ROOT,
        target_root=local_plugin_root,
    )

    sync_apply = {
        "requested": bool(args.sync_local),
        "applied": False,
        "copied": 0,
        "custom_merged": 0,
        "updated_files": [],
        "regeneration": {
            "attempted": False,
            "succeeded": False,
            "endpoint": "",
            "notes": [],
        },
    }

    if args.sync_local:
        updated_files: list[dict] = []
        copied = 0
        custom_merged = 0
        for plan in (skill_plan, plugin_plan):
            for action in plan["actions"]:
                result = apply_action(upstream_dir, action)
                if result["applied"]:
                    updated_files.append(result)
                    if action["status"] == "copy":
                        copied += 1
                    elif action["status"] == "custom_merge":
                        custom_merged += 1
        sync_apply["applied"] = True
        sync_apply["copied"] = copied
        sync_apply["custom_merged"] = custom_merged
        sync_apply["updated_files"] = updated_files
        if not args.no_regen:
            sync_apply["regeneration"] = regenerate_generated_surfaces(
                upstream_dir=upstream_dir,
                local_bridge_script=local_bridge_script,
                local_skill_root=local_skill_root,
                local_plugin_root=local_plugin_root,
                bridge_project=args.bridge_project,
                bridge_endpoint=args.bridge_endpoint,
            )

    recommendations: list[str] = []
    if local_bridge_hash and upstream_bridge_hash and local_bridge_hash != upstream_bridge_hash:
        recommendations.append("Upstream bridge.py changed; pull the installed unreal-bridge skill baseline instead of skipping sync.")
    else:
        recommendations.append("bridge.py is already aligned today, but the upstream audit should still run and sync any other upstream deltas.")

    recommendations.append(
        "If upstream changed at all, sync the upstream skill/plugin baseline first; do not gate the pull on whether upstream has Niagara capability."
    )
    recommendations.append(
        "Preserve local UnrealBridge Niagara overlay files, regenerate bridge_manifest/unreal_bridge.py from the live local plugin surface, and do not let upstream baseline sync erase local Niagara control."
    )

    if not has_upstream_niagara_library and has_local_niagara_library:
        recommendations.append(
            "Upstream still lacks UnrealBridgeNiagaraLibrary. Keep the local Niagara overlay and treat upstream as a baseline that must be merged with local Niagara extensions."
        )
    elif has_upstream_niagara_library:
        recommendations.append("Upstream now exposes a Niagara bridge library; compare it against the local overlay before dropping custom Niagara code.")

    if sync_result.get("worktree_dirty"):
        recommendations.append(
            "The upstream helper clone has local dirt. Audit against origin/main content, not the helper worktree files, or rebuild a clean mirror if needed."
        )

    return {
        "tool": "unrealbridge_upstream_audit",
        "generated_at": utc_now_iso(),
        "upstream_url": UPSTREAM_URL,
        "upstream_dir": str(upstream_dir),
        "upstream_ref": UPSTREAM_REF,
        "sync_result": sync_result,
        "latest_commit": commit,
        "upstream_head": upstream_head,
        "previous_upstream_head": previous_upstream_head,
        "upstream_changed_since_last_audit": upstream_changed_since_last_audit,
        "local_skill_root": str(local_skill_root),
        "local_bridge_script": str(local_bridge_script),
        "upstream_bridge_script": upstream_bridge_repo_path,
        "local_bridge_hash": local_bridge_hash,
        "upstream_bridge_hash": upstream_bridge_hash,
        "bridge_script_matches": bool(local_bridge_hash and upstream_bridge_hash and local_bridge_hash == upstream_bridge_hash),
        "local_plugin_root": str(local_plugin_root),
        "upstream_public_headers": upstream_headers,
        "has_upstream_niagara_library": has_upstream_niagara_library,
        "has_local_niagara_library": has_local_niagara_library,
        "local_overlay_rules": {
            "preserve_overlay_files": LOCAL_PLUGIN_OVERLAY_FILES,
            "generated_files": {
                f"{kind}:{rel_path}": reason
                for (kind, rel_path), reason in GENERATED_LOCAL_FILES.items()
            },
            "custom_merge_files": {
                f"{kind}:{rel_path}": reason
                for (kind, rel_path), reason in CUSTOM_MERGE_FILES.items()
            },
            "ignored_local_artifact_prefixes": list(IGNORED_LOCAL_ARTIFACT_PREFIXES),
        },
        "sync_plan": {
            "skill": skill_plan,
            "plugin": plugin_plan,
        },
        "sync_apply": sync_apply,
        "recommendations": recommendations,
    }


def render_plan_counts(plan: dict) -> list[str]:
    counts = plan.get("counts", {})
    order = ("copy", "custom_merge", "regenerate", "preserve_overlay", "unchanged", "local_only", "ignored_local_artifact")
    items = [f"{key}={counts[key]}" for key in order if key in counts]
    return items or ["no-files"]


def render_markdown(report: dict) -> str:
    commit_summary = (report.get("latest_commit", {}).get("stdout", "") or "").strip().splitlines()
    skill_counts = ", ".join(render_plan_counts(report["sync_plan"]["skill"]))
    plugin_counts = ", ".join(render_plan_counts(report["sync_plan"]["plugin"]))
    regen = report.get("sync_apply", {}).get("regeneration", {}) or {}
    lines = [
        "# UnrealBridge Upstream Audit",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Upstream URL: `{report['upstream_url']}`",
        f"- Upstream dir: `{report['upstream_dir']}`",
        f"- Upstream head: `{report.get('upstream_head', '')}`",
        f"- Previous audited head: `{report.get('previous_upstream_head', '')}`",
        f"- Upstream changed since last audit: `{report.get('upstream_changed_since_last_audit', False)}`",
        f"- Local bridge.py matches upstream: `{report['bridge_script_matches']}`",
        f"- Local plugin has Niagara library: `{report['has_local_niagara_library']}`",
        f"- Upstream has Niagara library: `{report['has_upstream_niagara_library']}`",
        "",
        "## Latest Commit",
        "",
    ]
    if commit_summary:
        lines.extend(f"- {line}" for line in commit_summary)
    else:
        lines.append("- unavailable")

    lines.extend(
        [
            "",
            "## Sync Plan",
            "",
            f"- Installed skill: `{skill_counts}`",
            f"- Project plugin: `{plugin_counts}`",
            "",
            "## Overlay Rules",
            "",
            "- Preserve local Niagara overlay source files.",
            "- Do not replace generated `bridge_manifest.json` or project `unreal_bridge.py` with upstream copies; regenerate them from the live local plugin surface instead.",
            "- Merge `UnrealBridge.Build.cs` so upstream additions land while local Niagara dependencies remain present.",
        ]
    )

    sync_apply = report.get("sync_apply", {})
    if sync_apply.get("requested"):
        lines.extend(
            [
                "",
                "## Sync Apply",
                "",
                f"- Requested: `{sync_apply.get('requested')}`",
                f"- Applied: `{sync_apply.get('applied')}`",
                f"- Files copied: `{sync_apply.get('copied')}`",
                f"- Files custom-merged: `{sync_apply.get('custom_merged')}`",
                f"- Generated surface regen attempted: `{regen.get('attempted', False)}`",
                f"- Generated surface regen succeeded: `{regen.get('succeeded', False)}`",
            ]
        )
        endpoint = regen.get("endpoint") or ""
        if endpoint:
            lines.append(f"- Regeneration endpoint: `{endpoint}`")
        for note in regen.get("notes", [])[:10]:
            lines.append(f"- Regen note: {note}")

    lines.extend(["", "## Recommendations", ""])
    for item in report.get("recommendations", []):
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    out = Path(args.out) if args.out else default_report_path(ctx, "upstream-audit", "unrealbridge", "unrealbridge-upstream-audit", ".json")
    previous_report = load_json(out, {}) if out.exists() else {}
    report = build_report(ctx, args, previous_report)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch/audit TornLux/UnrealBridge upstream, plan local sync, and optionally apply upstream baseline updates while preserving local Niagara overlay work."
    )
    parser.add_argument("--root", default="auto")
    parser.add_argument("--upstream-dir", default=r"D:\Temp\UnrealBridge_upstream")
    parser.add_argument("--local-skill-root", default=r"C:\Users\QY\.codex\skills\unreal-bridge")
    parser.add_argument("--local-bridge-script", default=r"C:\Users\QY\.codex\skills\unreal-bridge\scripts\bridge.py")
    parser.add_argument("--local-plugin-root", default=r"C:\UnrealEngineProject\UnrealAI\Plugins\UnrealBridge")
    parser.add_argument("--bridge-project", default=r"C:\UnrealEngineProject\UnrealAI\UnrealAI.uproject")
    parser.add_argument("--bridge-endpoint", default="")
    parser.add_argument("--sync-local", action="store_true", help="Copy upstream baseline files into the installed skill and project plugin while preserving/regenerating local overlay files.")
    parser.add_argument("--no-regen", action="store_true", help="Do not try to regenerate bridge_manifest.json / unreal_bridge.py after sync.")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args_no_subcommand(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
