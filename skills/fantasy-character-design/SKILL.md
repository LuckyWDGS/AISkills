---
name: fantasy-character-design
description: Create production-ready fantasy, xianxia, mythic, goddess, empress, spirit, deity, and Chinese fantasy character design sheets, character bibles, costume sheets, prop or magic-weapon sheets, material palettes, close-up detail panels, weighted/cropped reference anchors, and image-generation prompt packs. Use when Codex needs to turn a character brief or reference image into consistent visual assets before making keyframes, first/last frames, storyboards, or image-to-video shots, especially when face, costume, prop, style, or generic references need weight/crop-priority metadata. Trigger on requests such as 角色设定图, 人物设定, 设定板, 三视图, 转面图, 服装设定, 法器设定, 参考图权重, 裁剪优先级, 神女设定, 玄幻女帝, 仙侠角色, 星尘神女, 牡丹仙子, character sheet, character bible, costume sheet, fantasy character design, or when a storyboard/keyframe task first needs a locked protagonist.
---

# Fantasy Character Design

## Overview

Create character source assets before video planning: a stable protagonist, costume, material palette, prop or magic-device design, and detail panels that can later drive images, start/end frames, or storyboards.

This skill is independent from `short-video-storyboard`. Use this skill to define the character. Use `short-video-storyboard` only after the character is locked and the user wants start/end frames, bridge motion, shot breakdowns, or 25-panel storyboards.

## Decision Tree

1. Choose the output type.
   - `Character design sheet`: one tall board with hero art, turnarounds, face/eye details, fabric/accessory panels, palette, and notes.
   - `Character bible`: a text and prompt pack that defines identity, costume, palette, props, and invariants for later image generation.
   - `Costume or prop sheet`: focus on clothing, fabric, jewelry, weapon, magic circle, or footwear.
   - `Storyboard handoff pack`: export character anchors and prompt constraints for `short-video-storyboard`.

2. Decide whether the user needs actual images now.
   - If yes, use `$cm-imagegen` after creating the prompt pack.
   - If no, deliver the spec, prompts, and a rendered placeholder layout.
   - Do not invent that the user must buy first/last frames or storyboards elsewhere; the local skill chain can produce the planning assets and prompt packs.

3. Ask only when the missing answer changes the output.
   - `你要角色设定板，还是首尾帧/分镜图？`
   - `要不要中文标签？如果要，建议脚本排版文字，不让图片模型硬画小字。`
   - `主角要固定真实参考脸吗？如果要，请提供人物参考图。`

## Required Contract

Capture these fields before production-quality image generation:

- `character_name`: e.g. `璇玑女帝`, `牡丹仙子`, `星尘神女`
- `archetype`: empress, goddess, flower spirit, star deity, sword cultivator, demon queen, saintess
- `visual_theme`: xianxia, oriental fantasy, celestial, floral, starry, dark luxury, game concept sheet
- `identity_lock`: face shape, age impression, hair, expression, body proportion
- `costume_lock`: silhouette, dress shape, sleeves, train, embroidery, transparency, armor or jewelry
- `materials`: silk, gauze, jade, crystal, gold thread, starlight particles, petals, nebula fabric
- `props`: scepter, magic circle, sword, flower, fan, orb, constellation device
- `palette`: main color, secondary color, light color, metal color, shadow color
- `detail_panels`: face, eyes, hair ornament, chest/shoulder, fabric, hand, foot, weapon, magic emblem
- `avoid`: extra characters, random costume drift, unreadable generated text, modern objects, storyboard panels, video timeline

## Workflow

1. Read `references/workflow.md` for the production workflow and prompt module order.
2. Read `references/prompt-recipes.md` for complete Chinese and English prompt blocks.
3. Read `references/sheet-layouts.md` when layout, section count, or text placement matters.
4. Use `scripts/character_design_cli.py new-spec` to seed a starter spec from `assets/`.
5. Use `inspect-brief` before editing if the user gives a short Chinese brief and you want to audit inferred fields.
6. Use `apply-brief` to inject the brief into the spec and refresh all section prompts.
7. Use `attach-references` when face, costume, prop, style, or general reference images are available. Use `--reference-weight`, `--reference-priority`, `--reference-crop`, `--reference-focus`, and `--reference-lock` when one crop or anchor must win conflicts.
8. Use `render-layout` to create a placeholder design-board PNG for structure review.
9. Use `validate-sheet` to check required design-sheet coverage.
10. Use `export-prompts` to create the full board prompt, per-section prompts, prompt JSONL/CSV, and storyboard handoff package.
11. If actual images are requested, use `$cm-imagegen` with the exported full-board prompt or section prompts. Prefer generating no-text art panels, then add readable labels with layout tools.
12. If the user asks for keyframes or storyboard after the character is locked, pass the exported handoff package and selected generated images to `short-video-storyboard`.

## Commands

Seed a Chinese character sheet:

```powershell
python skills/fantasy-character-design/scripts/character_design_cli.py new-spec --profile starlight-deity --language zh --out D:\path\to\character.json
```

Inspect a brief:

```powershell
python skills/fantasy-character-design/scripts/character_design_cli.py inspect-brief --profile flower-spirit --brief "牡丹仙子角色设定图，红金华服，花神气质，三视图，眼睛和花瓣法器细节"
```

Apply a brief:

```powershell
python skills/fantasy-character-design/scripts/character_design_cli.py apply-brief --spec D:\path\to\character.json --out D:\path\to\character-filled.json --brief "星尘神女设定板，银白长发，蓝紫星云薄纱，星盘法器，三视图和眼睛细节"
```

Attach references:

```powershell
python skills/fantasy-character-design/scripts/character_design_cli.py attach-references --spec D:\path\to\character-filled.json --out D:\path\to\character-final.json --face-anchor D:\path\to\face.png --costume-anchor D:\path\to\dress.png --style-anchor D:\path\to\style.png
```

Attach one weighted crop/focus anchor:

```powershell
python skills/fantasy-character-design/scripts/character_design_cli.py attach-references --spec D:\path\to\character-filled.json --out D:\path\to\character-final.json --face-anchor D:\path\to\face-crop.png --reference-weight 1.0 --reference-priority 100 --reference-crop "face close-up / 3:4 portrait crop" --reference-focus "脸型、五官、发际线、妆容、眼神" --reference-lock hard-identity
```

Render a placeholder board:

```powershell
python skills/fantasy-character-design/scripts/character_design_cli.py render-layout --spec D:\path\to\character-final.json --out D:\path\to\character-layout.png
```

Export prompts and handoff files:

```powershell
python skills/fantasy-character-design/scripts/character_design_cli.py export-prompts --spec D:\path\to\character-final.json --out-dir D:\path\to\character-prompts
```

Validate the sheet:

```powershell
python skills/fantasy-character-design/scripts/character_design_cli.py validate-sheet --spec D:\path\to\character-final.json
```

## Validation

Before presenting a character sheet as production-ready, verify:

- The same character identity is preserved in hero, turnaround, face, and detail prompts.
- Costume silhouette, hair, color palette, prop language, and magic motif do not drift.
- Required panels exist: hero full body, front/side/back turnaround, face close-up, eye detail, costume/material detail, prop or magic emblem, footwear or hem detail, palette.
- Generated image text is not relied on for small Chinese labels; labels should be added by layout or post-processing when accuracy matters.
- Exported handoff files can be consumed by storyboard or keyframe workflows without re-inventing character details.
- Reference anchors include usable `weight`, `priority`, `crop`, `focus`, and `lock`, and exports preserve that metadata in prompt text, JSONL/CSV, and storyboard handoff.

## Resources

- `references/workflow.md`: production workflow, input contract, and routing rules
- `references/prompt-recipes.md`: reusable prompt modules and examples
- `references/sheet-layouts.md`: layout grammar for tall character design sheets
- `references/handoff-to-storyboard.md`: how to pass character assets into start/end frame or storyboard work
- `assets/*.json`: starter specs for empress, goddess, flower spirit, and starlight deity sheets
- `scripts/character_design_cli.py`: seed specs, parse briefs, attach references, render placeholder boards, validate coverage, and export prompt packs
