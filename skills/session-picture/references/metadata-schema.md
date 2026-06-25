# Metadata Schema

`picture_store.py` stores machine-readable entries in `.codex/session/assets/session-picture-index.json`. Index and summary updates are serialized with the heartbeat lock `.codex/session/assets/session-picture.lock`.

Required trust rule: a record with `local_path=null` or `status=thread-only` is not recoverable across sessions. Treat its `caption` as a reminder only.

Important fields:

- `id`: stable lookup key such as `asset_20260605_101500_abc12345`.
- `asset_type`: `design-reference`, `bug-screenshot`, `source-media`, `generated-image`, or `unclassified`.
- `status`: `active`, `pinned`, `superseded`, `rejected`, `missing`, `thread-only`, `stale-delete-soon`, `integrity-failed`, or `deleted`.
- `retention`: `keep`, `task-lifetime`, `cleanup-after-verification`, or `auto-unused`.
- `local_path`: project-relative path; resolve it from the current project root before returning it.
- `sha256`: original copied-file hash; `show` verifies this before returning a trusted path.
- `task_id`, `scope`, `tags`, `caption`, `user_intent`: retrieval and intent metadata.
- `import_history`: later duplicate imports of the same recoverable image append context here instead of overwriting the first caption/scope.

`show --json` may include `resolved_path`/`untrusted_path` for audit, but only `trusted_path` is safe to return to the user. Cleanup must protect `retention=keep`, `status=pinned`, and anything referenced by `.codex/session/HANDOFF.md`.
