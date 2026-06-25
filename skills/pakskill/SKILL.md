---
name: pakskill
description: Package Unreal content paks with UnrealPakTool. Use when Codex needs to build a pak from an existing UnrealPakTool config, inspect packaging logs, verify generated pak outputs, install pak files to an Android device over ADB, or clean the target DLC directory before reinstalling.
---

# PakSkill

Use this skill for Unreal projects that already contain an `UnrealPakTool` workflow. Do not hardcode drive letters, project names, or absolute paths.

Resolve paths from the requested config file:
- Project root: parent directory of the config's `project` path
- Tool directory: directory containing the config file and `UnrealPakTool.exe`
- Output directory: config `output` path, or `Pak` under the project root if omitted

## Workflow

1. Confirm the requested config exists under the project's `UnrealPakTool` directory.
Prefer an existing generated config such as `pak_settings_s01.generated.json`. If the user asks for one specific target, package only that target unless they explicitly request a broader repack.

2. Read `UnrealPakTool\README.md` when the project-specific workflow needs confirmation.
General rules:
- Keep the log file in the same directory as `UnrealPakTool.exe`
- Use a fresh timestamped log name for each run
- Expect the tool to delete an old pak before rebuilding it

3. Check for stale packer processes before starting.
On Windows PowerShell, inspect processes matching `UnrealPakTool*`, `SimpleUnrealPakTool*`, `UnrealEditor-Cmd*`, or `UnrealPak*`.

4. Run `scripts/run_unreal_pak_tool.py`.
It supports:
- `--action package`: build the pak from the config, then auto-detect ADB devices and auto-install the built pak when exactly one online device is available
- `--action install`: push one or more pak files to the Android DLC directory
- `--action clean`: recursively delete all files and subdirectories under the Android DLC directory while keeping the DLC directory itself

For package auto-install, install, and clean:
- Resolve `adb.exe` from `UnrealPakTool\platform-tools\ADB\adb.exe`
- Resolve the default device target path from `UnrealPakTool\pak_install_path.txt`
- Query `adb devices -l` before running and report the connected device list
- Do not read or depend on any `device_sn.txt` under the project directory
- If exactly one online device is connected, install against that device by default
- If no online device is connected, package still succeeds and auto-install is skipped
- If multiple online devices are connected, skip auto-install and require `--device-id` for an explicit target
- `--device-id` and `--install-path` apply to package auto-install as well as explicit install and clean actions
- Before pushing pak files, ensure the device target path is a directory. If a previous push accidentally created a file at that exact path, replace it with a directory first.
- After every push, verify each installed pak on the device against the local file. The helper must compare remote size and SHA1 with the local pak, and treat missing files, size mismatches, checksum mismatches, or failed verification commands as install failure even if `adb push` returned success.
- Treat the device pak storage directory as the primary location to report for installed builds. The helper exposes it as `device_storage.directory`, with installed pak files under `device_storage.pak_paths`.

5. Verify results after execution.
- Read the generated log
- Confirm whether the expected `.pak` exists in the resolved output directory
- Confirm the helper's `output_verification` reports `ok: true`. Record the resolved output directory and every expected local pak path, and verify each path is under that resolved output directory so stale files or wrong output locations do not get mistaken for the current build.
- For installs and package auto-installs, confirm the helper's device verification reports `ok: true` for every pushed pak, with matching local and remote sizes and SHA1 hashes.
- For installs and package auto-installs, record and report the device pak storage directory from `device_storage.directory` and the installed remote pak path(s) from `device_storage.pak_paths`. This device directory is the primary "pak storage path"; the local output directory is only supporting evidence for build freshness.
- Report the pak path, timestamp, size, and final task status from the log

6. If the log reports updated dependencies or directories that were not packed, summarize the affected paths and warn the user.
When the project follows a clear directory convention, summarize at the most useful shared directory level instead of listing every file.

## Command Pattern

Prefer this script:

```bash
python scripts/run_unreal_pak_tool.py --config G:\UnrealProjects\MyProject\UnrealPakTool\pak_settings_s01.generated.json
```

Optional flags:
- `--target-name S01`
- `--stop-existing`
- `--action install`
- `--action clean`
- `--device-id <serial>` when more than one device is connected or when the user wants a specific target
- `--pak <absolute pak path>` to install an explicit pak instead of the config-derived output
- `--install-path <device path>` to override `pak_install_path.txt`

## Reporting Rules

- Say whether the pak was produced successfully
- For package auto-install and install, include the device pak storage directory first, plus each installed remote pak path.
- Include the resolved local output directory and exact local pak path(s) as build verification details, not as the primary installed pak location.
- Mention the log path in the resolved `UnrealPakTool` directory
- Report whether local output verification passed. If it failed, list the affected pak names and whether the failure was missing file, outside output directory, or stale/not freshly updated.
- For package auto-install, install, and clean, include the current `adb devices` result and identify the selected device when possible
- For package auto-install and install, report whether device verification passed. If it failed, list the affected pak names and whether the failure was missing remote file, size mismatch, SHA1 mismatch, or a failed verification command.
- If package auto-install is skipped, say whether it was skipped because there was no online device or because multiple devices require `--device-id`
- If the final status warns about missing updated dependencies, list those paths clearly
- If the pak is missing, say so explicitly even if the tool returned exit code `0`

## Notes

- `OpenXR` warnings can appear during cook; do not treat them as the final result by themselves
- The authoritative outcome comes from the final status in the UnrealPakTool log and the existence of the expected pak file
- Reuse existing generated config files when possible instead of inventing new configs
- Treat dependency-inclusive repacks as opt-in unless the user explicitly asks for them
