# AISkills

Personal Codex skills managed as a single repository.

## Layout

```text
skills/
  <skill-name>/
    SKILL.md
    agents/
    references/
    scripts/
tools/
  install.ps1
  update.ps1
```

Use one branch for the stable collection, and feature branches for edits or experiments. Do not use long-lived branches as separate skill packages.

## Install On A Machine

Clone this repository, then expose the skills to Codex with junctions:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\install.ps1
```

By default this links every `skills/<name>/SKILL.md` package into:

```text
$HOME\.codex\skills\<name>
```

To refresh a machine after pulling updates:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\update.ps1
```

Restart Codex after adding, removing, or renaming skills so the skill list is refreshed.

## Notes

- Keep generated experiments and local outputs out of Git.
- Promote only durable references, scripts, templates, and docs into a skill directory.
- `C:\Users\<you>\.codex\skills\<skill-name>` may be a real directory, junction, or symlink; Codex only needs to read the `SKILL.md` through that path.
