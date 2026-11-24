# AISkills

Personal Codex skills managed as a single repository.

## Quick skill picker

This repository contains 22 Codex skill packages; the five Unreal Engine skills
exist in a UE 5.8 and a UE 5.9 version. You can simply describe the
task in natural language; Codex selects a matching skill when available. For
an explicit request, write `$<skill-name>` in the prompt, for example
`$unreal-engine-mcp inspect the open UE 5.8 editor and report PIE state`.

Choose by intent:

- Plan a product feature or UI flow: `feature-experience` first; use
  `ui-from-design` when an accepted design image already exists.
- Generate/edit images or request native GIF/SVG: [cm-imagegen](skills/cm-imagegen/README.md) (GPT Image 2.6, single-provider Sub2API support; format access depends on the upstream); use `image-generation-director` for
  prompt direction, trend/content strategy, or image-to-video planning.
- Use [portrait-recipe-studio](skills/portrait-recipe-studio/SKILL.md) when explicitly
  requesting its portrait and clothing prompt recipes.
- Prepare or publish Douyin content with
  [douyin-ai-publisher](skills/douyin-ai-publisher/README.md); actual publication
  requires a specific user instruction and a logged-in creator account.
- Research Douyin AI creators and develop an original direction, pilot package,
  and feedback loop with [douyin-ai-creator-lab](skills/douyin-ai-creator-lab/SKILL.md).
- Upload and prepare a finalized video for Bilibili (dual-ratio covers, AI
  declaration, BV verification) with
  [bilibili-video-publisher](skills/bilibili-video-publisher/SKILL.md); it stops at
  the filled submission page unless the user authorizes that specific video.
- Upload a finalized video or Short through YouTube Studio (audience, altered
  content disclosure, checks, visibility) with
  [youtube-video-publisher](skills/youtube-video-publisher/SKILL.md); it stops
  before the final Publish/Save unless the user authorizes that specific video.
- Create WeChat illustrated stories with [wechat-story-publisher](skills/wechat-story-publisher/SKILL.md): recent research, complete stories, compelling titles, coherent images and reload-verified drafts; publish when the current request authorizes it.
- Build characters, storyboards, or VFX assets: combine
  `fantasy-character-design`, `short-video-storyboard`,
  `niagara-vfx-artist`, and `vfx-flipbook-generator` as appropriate.
- Work in Unreal Engine: start with `unreal-engine-mcp`; use
  `unreal-material-artist` for materials/shaders, `niagara-vfx-artist` for
  Niagara systems, and `unreal-sequencer` for Level Sequences, cameras and
  cinematics. The five UE skills live in `skills/ue5.8/` and `skills/ue5.9/`
  with the same names; link one set with `install.ps1 -UEVersion`. Each set
  targets only its own engine version, and its client refuses an editor of the
  other one. See the
  [UE 技能总览与安装](docs/zh/ue-skills-overview.md) for the bundle,
  dependencies, shared rules, version switching and setup.
- Deploy or troubleshoot an owned VPS proxy and subscription with
  [vps-proxy-deploy](skills/vps-proxy-deploy/SKILL.md).
- Compile screenplay director packages into video prompts with
  [ai-video-prompt-director](skills/ai-video-prompt-director/SKILL.md).
- Prepare and publish a specifically authorized Xiaohongshu note, or review
  note performance read-only, with
  [xiaohongshu-content-publisher](skills/xiaohongshu-content-publisher/SKILL.md).
- Prepare and publish a specifically authorized Toutiao image article (body
  images plus independent three-image cover), archive it, or review it
  read-only with [toutiao-content-publisher](skills/toutiao-content-publisher/SKILL.md).

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
  ue5.8/                  # UE 5.8 bundle: the five UE skills as siblings
    unreal-engine-mcp/
    unreal-material-artist/
    niagara-vfx-artist/
    unreal-sequencer/
    vfx-flipbook-generator/
  ue5.9/                  # UE 5.9 bundle, same skill names
    ...
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

By default this links every `skills/<name>/SKILL.md` package, plus the five UE
skills from one `skills/ue<version>/` bundle, into:

```text
$HOME\.codex\skills\<name>
```

The UE bundles share skill names, so only one is linked at a time. Choose it
with `-UEVersion`; without it the script keeps the currently linked version
(first install: 5.8). Restart Codex after switching.

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\install.ps1 -UEVersion 5.9
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
