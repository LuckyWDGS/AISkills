---
name: mentalout-image-browser
description: Use `https://image.mentalout.top/` to generate or edit images for UI mockups, redesign concepts, poster art, image restyling, and reference-based image generation. Trigger this skill when the user wants image generation or image editing through the Mentalout Snow AI Image page, especially for UI redesign previews, “按参考图生图”, poster/cover concepts, local-image + web-image reference generation, iterative visual exploration, or multi-image design work that must stay visually unified across many original/reference images.
---

# Mentalout Image Browser

## Overview

Use the Mentalout Snow AI Image page as the default image workflow for this user. Prefer this site over other image-generation tools unless the user explicitly asks for a different tool.

Read the API key from the local user environment variable `MENTALOUT_IMAGE_API_KEY`. Do not print the key in chat, commit it into repos, or duplicate it into project files.

Do not ask for or fill an API domain by default. The page should use its configured backend; only fill the API key unless the user explicitly requests a custom endpoint.

For multi-image projects, do not treat each image as a standalone generation. First establish a compact visual system, then reuse it for every later image so the results feel like one coherent product, campaign, or art direction board.

## Workflow

1. Read the visual request carefully.
2. Gather reference materials:
   - Use attached images when already present in the chat.
   - Use local-image upload when the user gives filesystem paths.
   - Use web-image upload when the user gives remote image URLs.
3. Identify the reference role for each image:
   - `structure reference`: preserve layout, content order, object placement, or screen information architecture.
   - `style reference`: borrow color, mood, material, lighting, typography, or rendering quality.
   - `content reference`: preserve a character, product, logo, scene, poster, or object identity.
4. For any multi-image or follow-up design task, create or reuse a `style lock` before generating.
5. Open `https://image.mentalout.top/`.
6. Fill the API key only if the page field is empty:
   - Value source: `MENTALOUT_IMAGE_API_KEY`
7. Fill the prompt with a clean, production-oriented prompt that includes the style lock and image-specific instructions.
8. Choose generation settings based on the requested output.
9. Generate.
10. Review results against the user’s request and the style lock.
11. If needed, iterate with targeted corrections rather than large prompt rewrites.
12. Download the best image and return its saved path to the user.

## Unified Design System

Use this section whenever the user will provide multiple original images, asks for consistency, or says later images should share the same design language.

### Style lock

Before generating, define a short reusable style lock with these fields:

- `visual direction`: the overall taste level and genre, such as premium cinematic streaming UI, editorial poster system, soft 3D product board, or clean technical app mockup.
- `palette`: 3-5 recurring colors, including background, primary accent, secondary accent, surface, and text color.
- `composition`: common grid, crop, spacing, framing, safe area, and focal hierarchy.
- `materials`: glass, matte panels, grain, metal, paper, neon, glow, depth, shadows, or texture rules.
- `typography`: font personality, size hierarchy, Chinese/English treatment, and text density.
- `lighting`: direction, contrast, glow strength, vignette, and background atmosphere.
- `negative rules`: no watermark, no browser chrome, no unreadable clutter, no random logos, no mismatched style, no overdecorated background.

Keep the style lock stable across generations. Change it only when the user explicitly approves a new direction or when the current style clearly fails the task.

### Multi-image consistency process

1. For the first original image, generate `2-4` options to discover the best direction.
2. Pick the strongest option as the canonical style reference, or ask the user to choose if multiple directions are meaningfully different.
3. For every later original image, upload the new original as the structure/content reference and the approved output as the style reference when available.
4. Reuse the same style lock verbatim, then add only image-specific changes.
5. Keep recurring tokens consistent: palette, corner radius, card density, glow intensity, background atmosphere, icon style, title treatment, and poster/image treatment.
6. If a later image has a different aspect ratio or purpose, adapt composition while preserving the same visual DNA.

### Reasonable beautification rules

- Preserve the user’s original intent before polishing. Do not remove important layout regions, product facts, characters, or content hierarchy.
- Improve spacing, hierarchy, alignment, contrast, material quality, and focal clarity.
- Prefer restrained premium detail over decorative noise.
- Make UI concepts implementation-friendly: realistic components, readable hierarchy, believable navigation, and clear content zones.
- For posters or art boards, prioritize recognizable focal subject, controlled lighting, and consistent campaign styling.
- For screenshots, remove accidental browser/app chrome unless the user wants it preserved.

## Page Controls

The page exposes these controls:

- `API Key`
- `Prompt`
- `添加本地图片`
- `添加网页图片`
- `尺寸`
- `数量`
- `风格提示`
- `生成质量`
- `输出格式`
- `输出压缩`
- `生成图片`
- `展示区`
- `历史记录`

## Recommended Defaults

### Unified multi-image design

- First calibration: `2 张` or `4 张`
- Later images: `1 张` or `2 张`
- Quality: `高质量，通常更慢`
- Format: `PNG，无损`
- Prompt: include the same style lock every time
- References: one original image plus one approved style image when available

### UI mockups and redesign boards

- Size: `1536×1024 (横版)` for desktop / TV / landscape layouts
- Size: `1024×1536 (竖版)` for mobile portrait screens
- Count: `2 张` or `4 张`
- Style: `无` or `写实`
- Quality: `高质量，通常更慢`
- Format: `PNG，无损`

### Posters, covers, and hero art

- Count: `2 张` or `4 张`
- Style: `写实`, `动漫`, or `3D` only when requested
- Format: `PNG` for detail work, `JPEG` for fast iteration

### Fast exploration

- Count: `1 张` or `2 张`
- Quality: `中质量`
- Format: `JPEG`

## Prompt Structure

Use compact prompts with this structure:

`style lock + reference roles + subject + composition + materials/colors + lighting + preservation rules + negative rules`

### Unified redesign prompt template

`Use the uploaded original image as the structure reference. Preserve its core layout, content hierarchy, and subject identity. Restyle it using this consistent visual system: [visual direction], [palette], [composition], [materials], [typography], [lighting]. Improve spacing, contrast, alignment, hierarchy, and polish. Keep the result realistic, premium, cohesive with prior outputs, no watermark, no browser chrome, no random logos, no unreadable clutter.`

### TV / desktop UI prompt template

`Use the uploaded original image as the structure reference. Preserve the app screen information architecture. Restyle into a high-end TV streaming interface: cinematic dark graphite background, deep teal and warm amber accents, glassmorphism top navigation, large poster grid, soft vignette, refined spacing, sharp Chinese typography, consistent card radius, premium media-dashboard polish, no watermark, no browser chrome, no random logos.`

### Mobile UI prompt template

`Use the uploaded original image as the structure reference. Restyle into a modern mobile app screen: premium dark interface, card-based layout, subtle blur panels, clear thumb-friendly hierarchy, clean Chinese typography, consistent accent color, realistic product mockup, no watermark, no browser chrome, no unreadable clutter.`

### Reference-edit prompt template

`Preserve the original layout and information architecture. Restyle into the approved visual system. Improve contrast, spacing, typography, alignment, and visual hierarchy. Keep the page readable, realistic, cohesive with previous outputs, and free of watermarks or random UI artifacts.`

## Reference Image Guidance

- Prefer `1-3` references per generation.
- Use local upload for screenshots, sketches, and user-provided mockups.
- Use web-image upload for online inspiration boards or remote references.
- For unified redesigns, use one structure reference plus one approved style reference whenever possible.
- Do not upload many unrelated originals at once. Process them sequentially so each output can follow the same style lock.
- If a user provides many originals, start with the most representative image as the calibration sample.

## Review Checklist

Check the result for:

- correct orientation
- readable UI hierarchy
- preserved key layout intent
- consistency with the approved style lock
- consistent palette, spacing, surface treatment, and typography across the series
- no extra fingers / broken geometry / nonsense text dominating the image
- no visible watermark
- suitable density for TV vs mobile

If the result misses the layout, tighten the prompt around structure.
If the result matches layout but misses polish, tighten style/material wording.
If the result is polished but inconsistent with the series, reuse the exact style lock and add: `match the approved visual system more closely`.

## Iteration Strategy

- Change only one major variable per retry: layout preservation, color palette, material detail, typography, or lighting.
- Prefer concrete corrections: `keep the original poster grid count`, `reduce neon glow`, `use warmer amber accents`, `make text hierarchy cleaner`.
- Do not abandon the style lock after a weak result. Tighten the reference role and negative rules first.
- When the user approves a direction, summarize the reusable style lock before moving to later images.

## Output Handling

- Save the selected image into a user-visible local path.
- Tell the user which settings produced the chosen result.
- For a multi-image series, mention the active style lock or approved style reference so later work can stay aligned.
- For UI work, mention whether the selected output is better suited as:
  - concept image
  - implementation reference
  - poster / art direction board

## Safety and Secret Handling

- Read the API key from `MENTALOUT_IMAGE_API_KEY`.
- Do not echo the raw key unless the user explicitly asks to see it.
- Do not store the key in project repos or app source files.
