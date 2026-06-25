# picture_store.py Dynamic Black-Box Review

Test date: 2026-06-08 09:06-09:08 +0800

Target:

- `C:\Users\QY\.codex\skills\session-picture\scripts\picture_store.py`
- LastWriteTime observed: 2026-06-08 09:00:57
- Size observed: 55026 bytes

Write boundary honored:

- Wrote only under `D:\AISkills\SessionPicture\.subagent-review-20260608-dynamic`
- Did not modify skill files.
- Did not update or roll back any files outside the review directory.

Artifacts:

- Harness: `D:\AISkills\SessionPicture\.subagent-review-20260608-dynamic\dynamic_blackbox_tests.py`
- Final passing run: `D:\AISkills\SessionPicture\.subagent-review-20260608-dynamic\run-20260608-090620`
- Final run summary: `D:\AISkills\SessionPicture\.subagent-review-20260608-dynamic\run-20260608-090620\summary.json`
- Final command logs: `D:\AISkills\SessionPicture\.subagent-review-20260608-dynamic\run-20260608-090620\command-logs`
- Earlier exploratory/failed harness runs intentionally retained: `probe-schema`, `run-20260608-090047`, `run-20260608-090311`

## Overall Result

The final black-box suite ran 47 command invocations and 17 assertions. All 17 assertions passed.

No safety-boundary failure, data-loss failure, rollback failure, stale-lock failure, foreign-lock release failure, missing re-add failure, or HANDOFF cleanup-protection failure was observed.

## Command Results

### Basic workflow

- `init --root <basic>`: rc=0; created the project store.
- `add <png> --json`: rc=0; imported a local PNG as `source-media`.
- `find alpha --verify --json`: rc=0; returned the imported asset.
- `show <id> --json`: rc=0; returned `verification=ok` and a non-null `trusted_path`.
- `update <id> --tag alpha,reviewed --caption ... --json`: rc=0; updated caption and tags.
- `supersede <old> <new> --json`: rc=0; old item became `superseded`, moved to rejected storage, and the new item listed the old id in `supersedes`.
- `add-data-url <file> --json`: rc=0; imported the PNG data URL.
- `thread-only --json`: rc=0; produced `status=thread-only`, `local_path=null`, `resolved_path=null`.
- `cleanup --min-age-days 0 --statuses stale-delete-soon --apply --json`: rc=0; deleted the stale cleanup target and marked its record `deleted`.
- `doctor --json`: rc=0; returned `{"ok": true, "issues": []}`.

### Fresh-root read-only behavior

On a root with no `.codex/session`, these commands all failed with rc=2 and did not create `.codex`:

- `doctor`
- `find`
- `show`
- `update`
- `supersede`
- `cleanup`

### Batch add rollback

- `add valid.png invalid.txt --json`: rc=2 with `Source does not look like an image`.
- Index item count after failure: 0.
- Copied session-picture files after failure: 0.

### Path escape

Setup: imported an asset, then tampered the test root's JSON index so `local_path` was an absolute path outside `.codex/session`.

- `doctor --json`: rc=1; reported `local_path must be project-relative`.
- `show <id> --json`: rc=1; did not trust or return the outside path.
- `cleanup --apply --json`: rc=1; did not delete the outside file.
- Outside target file still existed after the commands.

### Tamper hash

Setup: marked an item `stale-delete-soon`, then overwrote its stored file with different PNG bytes.

- `show <id> --json`: rc=3; changed status to `integrity-failed`.
- `cleanup --apply --statuses stale-delete-soon --json`: rc=0; returned no candidates.
- The mismatched file was preserved.

### Missing re-add

Setup: imported an image, deleted its stored copy, then re-added the same source image.

- `show <id> --json` after deletion: rc=3; item became `missing`.
- `add same.png --json`: rc=0; restored the same item instead of duplicating it.
- Final index count for that root: 1 active item.

### HANDOFF reference protection

Setup: marked an item `stale-delete-soon`, wrote its id/path into the test root's `.codex/session/HANDOFF.md`, then ran cleanup.

- `cleanup --apply --statuses stale-delete-soon --json`: rc=0; `candidates=[]`.
- Referenced file still existed.
- Item status remained `stale-delete-soon`.

### Lock behavior

- Foreign active lock: `doctor --lock-timeout-seconds 1 --json` returned rc=2 after about 1.081s; the foreign lock remained until the harness removed it.
- Stale no-heartbeat lock older than 7 hours: `doctor --json` returned rc=0 and cleared the lock.
- Lock wait: a command blocked on an active lock, the harness removed the lock after about 1.4s, and `doctor --json` returned rc=0 after about 1.475s.
- Heartbeat: during a 1200-image long add, the harness observed the lock file and 90 distinct mtime updates across 449 samples; the lock was removed after the command completed.
- Concurrent wait: `doctor --lock-timeout-seconds 180 --json` waited behind the long add and returned rc=0 after about 90.558s.

## Findings

### P2: Path-escape tampering triggers Python tracebacks in `show` and `cleanup`

The safety boundary held: the outside path was not trusted and not deleted. However, when the index contained an absolute `local_path`, `show --json` and `cleanup --json --apply` crashed while syncing Markdown and printed Python tracebacks to stderr.

`cleanup --json --apply` also printed a JSON object to stdout before the traceback and non-zero exit. A caller that only parses stdout could misread this as a clean structured result.

Recommendation: validate indexed paths before any Markdown sync, catch path-resolution errors at the command boundary, and return a structured JSON error for `--json` callers. Avoid printing final-looking JSON until all commit/sync steps have succeeded.

### P3: Large batch add can hold the store lock for a long time

The 1200-image add held the lock long enough that a concurrent `doctor` waited about 90.558s. In the previous 4000-image run, a `doctor --lock-timeout-seconds 60` timed out while the add still completed successfully.

This is not a correctness failure because heartbeat refreshed and stale cleanup did not remove the active lock. It is a usability/performance risk for parallel agents.

Recommendation: reduce the lock critical section if feasible. For example, pre-scan and copy/import files outside the lock, then lock only for the JSON/Markdown commit phase. Also consider documenting higher `--lock-timeout-seconds` for large batch imports or adding a quiet/progress mode for long imports.

### P3: Large non-JSON add output is very noisy

The long add printed per-asset text for 1200 items; the harness truncated command logs for readability.

Recommendation: add a `--quiet` or summary output mode for large directory imports.

## Suggestions For Next Validation

- Add a dedicated regression test for tampered absolute and `..` `local_path` values where `show --json`, `cleanup --json`, and Markdown sync should all return structured errors without tracebacks.
- Add a stress test that runs two real long `add` commands against the same root and verifies the second either waits successfully with a sufficient timeout or fails cleanly without partial output.
- Add a batch-size performance threshold test so future changes do not unexpectedly increase lock hold time.
