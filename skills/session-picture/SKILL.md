---
name: session-picture
description: Save, tag, verify, retrieve, and clean up user-provided session images for Codex projects. Use when the user uploads, pastes, references, asks to preserve, asks to find, asks to return, asks to tag, or asks to prune images/screenshots/design references/media assets across Codex sessions, especially when chat-visible images may otherwise lack a durable filesystem path. Also use when creating or auditing `.codex/session/ASSETS.md` and `.codex/session/DEBUG_SCREENSHOTS.md` image entries.
---

# Session Picture

## Core Rule

Only call an image recoverable after it has been copied to a project-local file and verified by hash. A chat-visible image without a local source path, attachment file handle, or image bytes is not durable; record it as `thread-only` instead of inventing a path.

Never use the clipboard as a capture source. If the interface does not expose a path or bytes, ask for a file path/re-upload/drop-folder route, and record the limitation.

## Quick Start

Use the bundled script:

```bash
python C:/Users/QY/.codex/skills/session-picture/scripts/picture_store.py <command> --root auto
```

Common commands:

```bash
# Create the project-local store and index.
python C:/Users/QY/.codex/skills/session-picture/scripts/picture_store.py init --root auto

# Import one or more image files and tag them.
python C:/Users/QY/.codex/skills/session-picture/scripts/picture_store.py add path/to/image.png --root auto --asset-type source-media --tag logo --tag user-upload --caption "User-provided logo"

# Record an image that was visible in chat but had no durable path.
python C:/Users/QY/.codex/skills/session-picture/scripts/picture_store.py thread-only --root auto --asset-type unclassified --tag needs-reupload --caption "Visible in chat, no source path exposed"

# Find images by id, tag, caption, task, or scope.
python C:/Users/QY/.codex/skills/session-picture/scripts/picture_store.py find logo --root auto

# Return and touch a specific image path after hash verification.
python C:/Users/QY/.codex/skills/session-picture/scripts/picture_store.py show asset_20260605_abcd1234 --root auto

# Preview cleanup candidates.
python C:/Users/QY/.codex/skills/session-picture/scripts/picture_store.py cleanup --root auto --min-age-days 90
```

## Workflow

1. Classify the image from the user's words, not from the pixels alone:
   - `design-reference`: explicit UI/design/reference intent.
   - `bug-screenshot`: user reports an error, visual bug, runtime state, or asks for debugging.
   - `source-media`: logo, texture, poster, product image, source photo, or other reusable media.
   - `generated-image`: image generated during the task.
   - `unclassified`: image is mentioned but intent is unclear.
2. Import only when a real source is available:
   - Local path: run `add`.
   - Data URL/base64 file: run `add-data-url`.
   - No path/bytes: run `thread-only` and ask for a durable source when the file matters.
3. Use project-local storage:
   - Non-debug images go under `.codex/session/assets/active/session-picture/`.
   - Rejected/superseded images go under `.codex/session/assets/rejected/session-picture/`.
   - Debug screenshots go under `.codex/session/debug-screenshots/session-picture/`.
4. Treat `.codex/session/assets/session-picture-index.json` as the machine-readable source of truth. `ASSETS.md` and `DEBUG_SCREENSHOTS.md` are summaries generated from it.
5. Before returning a path to the user, run `show` or `find --verify`. `show --json` and `find --verify --json` return `trusted_path` only when verification is `ok`; on failure they exit non-zero and may include `untrusted_path` for audit only. Plain `find --json` is an index lookup and does not return an absolute trusted path.
6. If an image remains important for the next session, mention its id/path in `.codex/session/HANDOFF.md`.

The script rejects indexed paths that are absolute, contain `..` escape behavior, or resolve outside `.codex/session`.

The script uses a project-local heartbeat lock at `.codex/session/assets/session-picture.lock` so concurrent commands do not overwrite each other's index updates. If a lock is held, commands wait up to 30 seconds by default. Active commands refresh the lock heartbeat; stale-lock cleanup is only for abandoned locks that have not heartbeated for six hours.

`init`, `add`, `add-data-url`, and `thread-only` may create a missing store. Other commands, including `find`, `show`, `doctor`, `update`, `supersede`, and `cleanup`, require an existing store and fail instead of creating `.codex/session` in a wrong working directory.

Multi-file `add` prevalidates inputs and rolls back files plus JSON/Markdown summaries if the import fails.

## Metadata

Use stable labels. Prefer these fields:

- `asset_type`: `design-reference`, `bug-screenshot`, `source-media`, `generated-image`, `unclassified`.
- `status`: `active`, `pinned`, `superseded`, `rejected`, `missing`, `thread-only`, `stale-delete-soon`, `integrity-failed`, `deleted`.
- `retention`: `keep`, `task-lifetime`, `cleanup-after-verification`, `auto-unused`.
- `task_id`, `scope`, `tags`, `caption`, and `user_intent`.

Use `pinned` or `retention=keep` for assets that must not be automatically deleted.

For field-level details, read `references/metadata-schema.md` only when auditing or modifying the index schema.

## Cleanup

Cleanup is dry-run by default. Use `--apply` only after reading the candidate list.

At the start or end of a session-picture task, run a cleanup dry-run when practical. This gives automatic stale-candidate discovery without silently deleting user images.

The script protects:

- `status=active` and `status=pinned` unless `--include-unused` is explicitly supplied and the item is old enough.
- `retention=keep`.
- Items referenced by `.codex/session/HANDOFF.md`.
- Index entries with untrusted `local_path` values; cleanup refuses to proceed until the path issue is fixed.
- Files whose hash no longer matches the index; these become `integrity-failed` instead of being silently removed.
- `missing` records whose former path now contains an unrelated file; those files are not deleted.

For routine pruning, prefer:

```bash
python C:/Users/QY/.codex/skills/session-picture/scripts/picture_store.py cleanup --root auto --min-age-days 90
python C:/Users/QY/.codex/skills/session-picture/scripts/picture_store.py cleanup --root auto --min-age-days 90 --apply
```

Use `--include-unused` only when the user explicitly wants old unpinned active images removed.

## Validation

Run these checks after changing the skill or script:

```bash
python C:/Users/QY/.codex/skills/.system/skill-creator/scripts/quick_validate.py C:/Users/QY/.codex/skills/session-picture
python C:/Users/QY/.codex/skills/session-picture/scripts/picture_store.py doctor --root auto
```

For realistic testing, create a temporary root, import a small image, verify `find/show`, delete the copied image, and confirm `show` reports `missing` rather than a trusted path.
