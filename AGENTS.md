# Codex Project Instructions

## Repository Layout

- This repository stores reusable Codex skills.
- Skill packages live under `skills/<skill-name>/`.
- Each skill intended for Codex discovery must contain `SKILL.md`.
- Local Codex installs should expose skills by junction/symlink from `$CODEX_HOME/skills/<skill-name>` to this repo's `skills/<skill-name>`.
- Do not commit local runtime outputs, caches, API keys, or generated experiments unless they are intentionally promoted to durable assets/references.
