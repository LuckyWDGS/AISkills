# AISkills

Personal Codex skills managed as a single repository.

## Quick skill picker

This repository contains 19 focused Codex skills. You can simply describe the
task in natural language; Codex selects a matching skill when available. For
an explicit request, write `$<skill-name>` in the prompt, for example
`$unreal-bridge inspect the open UE 5.8 editor and report PIE state`.

Choose by intent:

- Plan a product feature or UI flow: `feature-experience` first; use
  `ui-from-design` when an accepted design image already exists.
- Generate or edit images: `cm-imagegen`; use `image-generation-director` for
  prompt direction, trend/content strategy, or image-to-video planning; use
  `mentalout-image-browser` only when Mentalout/Snow AI is explicitly named.
- Build characters, storyboards, voice, or VFX assets: combine
  `fantasy-character-design`, `short-video-storyboard`, `speech`,
  `niagara-vfx-artist`, and `vfx-flipbook-generator` as appropriate.
- Work in Unreal Engine: start with `unreal-bridge`; use
  `unreal-material-artist` for materials/shaders, `niagara-vfx-artist` for
  Niagara systems, and `pakskill` for pak/DLC packaging.
- Automate or inspect a browser: use `playwright` for one-off CLI flows and
  `playwright-interactive` for a persistent debugging/QA session.
- Capture or preserve images: use `screenshot` for desktop capture and
  `session-picture` for durable project image indexing.
- Keep a long project resumable: use `codex-session-continuity` to maintain
  handoff, project facts, decisions, and verification records.

See the [中文技能目录](docs/zh/README.md) for a per-skill purpose, use case,
recommended combination, and copyable example prompt.

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

## 中文说明

仓库里有一组面向中文阅读的技能说明：

- [docs/zh/README.md](docs/zh/README.md)
