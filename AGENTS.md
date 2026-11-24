# Codex Project Instructions

## Repository Layout

- This repository stores reusable Codex skills.
- Skill packages live under `skills/<skill-name>/`.
- The five Unreal Engine skills are grouped by engine version under
  `skills/ue<major.minor>/<skill-name>/` (currently `ue5.8` and `ue5.9`). Each
  group holds all five as siblings with unchanged skill names; never import or
  link across groups. Change a version only inside its own group.
- Each skill intended for Codex discovery must contain `SKILL.md`.
- Local Codex installs should expose skills by junction/symlink from `$CODEX_HOME/skills/<skill-name>` to this repo's `skills/<skill-name>` (UE skills: `skills/ue<version>/<skill-name>`,
  one version at a time via `tools/install.ps1 -UEVersion`).
- Do not commit local runtime outputs, caches, API keys, or generated experiments unless they are intentionally promoted to durable assets/references.

## UE 5.9 skills

Develop and test UE 5.9 work in `skills/ue5.9/`; keep `skills/ue5.8/` as the
UE 5.8 baseline and port a change back only after verifying it on 5.8. The
original development branch is archived as tag `archive/ue5.9-mcp`.

Read `skills/ue5.9/unreal-engine-mcp/references/ue-5.9-preview-audit.md` before a
5.9 MCP task. Keep local paths, setup evidence and continuation notes in
`.codex/session/` (ignored); the 5.9 setup is recorded in `HANDOFF.md` there.

Use a new UE 5.9 test project or an explicitly selected copy of a UE 5.8
project. For concurrent editors, reserve port 8000 for the existing setup
and prefer 8001 for the test editor. Before asset writes, use fresh editor
identity and live schema discovery to verify UE 5.9 and the intended absolute
`.uproject` path. Keep MCP cache/session state separate with
`UE_MCP_CACHE_DIR`, or use `--no-cache --new-session` for initial discovery.

Treat installed-source findings as candidates until the target editor exposes
the corresponding schema. Record read, write, compile and runtime validation
separately; do not claim UE 5.8 regression coverage from UE 5.9 tests.
