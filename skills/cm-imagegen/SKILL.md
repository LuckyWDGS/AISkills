---
name: "cm-imagegen"
description: "Generate or edit raster images through CodexManager's OpenAI-compatible Images API when Codex should use the current Codex provider base_url and auth.json API key instead of the official built-in image_gen tool. Use when the user asks for CodexManager image generation, API-key/provider-mode image generation, or image generation through CodexManager account pools, routing, logs, and billing."
---

# CM Image Generation Skill

Generates or edits images for the current project (for example website assets, game assets, UI mockups, product mockups, wireframes, logo design, photorealistic images, or infographics).

This skill follows the same request semantics, prompt workflow, decision tree, and output expectations as the official `imagegen` skill. The only intentional difference is the execution layer: image requests are sent to CodexManager's OpenAI-compatible Images API using the current Codex provider `base_url` and `auth.json` API key.

## Top-level modes and rules

This skill has one top-level mode:

- **CodexManager CLI mode:** bundled `scripts/cm_image_gen.py` CLI. It uses the current Codex configuration and calls CodexManager's image endpoints.

The CLI exposes two subcommands:

- `generate`
- `edit`

Rules:
- Use this skill only when the user explicitly asks for CodexManager image generation or when the official built-in `image_gen` tool is unavailable in API-key/provider mode.
- Do not ask the user for a separate image API key or image base URL by default.
- Do not create one-off SDK runners.
- Never modify the official system `imagegen` skill.

CodexManager config policy:
- If `CODEXMANAGER_IMAGE_BASE_URL` is set, use it as the image request base URL.
- Otherwise, read the active `model_provider` from `$CODEX_HOME/config.toml`.
- Read that provider's `base_url` from `[model_providers.<provider>]`.
- Read `OPENAI_API_KEY` from `$CODEX_HOME/auth.json`.
- Use `CODEXMANAGER_IMAGE_MODEL` only for the image model override; otherwise use `gpt-image-2`.
- Use `CODEXMANAGER_IMAGE_OUTPUT_DIR` only for the output directory override; otherwise save under the current working directory's `generated-images/` folder.

Save-path policy:
- CodexManager generated images are saved under the current working directory's `generated-images/` folder by default.
- If the user names a destination, use `--out-dir` and/or `--filename`, or move/copy the selected output there.
- Do not edit, create, or attach unrelated project files such as `AGENTS.md`.
- If the image is meant for the current project, keep the final selected image in `generated-images/` unless the user named another destination.
- If the image is only for preview or brainstorming, render the generated PNG inline in the final response using Markdown image syntax with an absolute local file path. Use forward slashes in the Markdown URL for Windows paths, for example `![alt](D:/absolute/path/image.png)`.
- Never report an unrelated file card as the generated image result.
- Do not overwrite an existing asset unless the user explicitly asked for replacement; otherwise create a sibling versioned filename such as `hero-v2.png` or `item-icon-edited.png`.

Shared prompt guidance lives in `references/prompting.md` and `references/sample-prompts.md`.
For a Chinese beginner-facing usage guide, see `README.zh-CN.md`.

CLI docs/resources:
- `README.zh-CN.md`
- `references/cli.md`
- `references/image-api.md`
- `references/codex-network.md`
- `scripts/cm_image_gen.py`

## When to use
- Generate a new image (concept art, product shot, cover, website hero)
- Generate a new image using one or more reference images for style, composition, or mood
- Edit an existing image (inpainting, lighting or weather transformations, background replacement, object removal, compositing, transparent background)
- Produce many assets or variants for one task

## When not to use
- Extending or matching an existing SVG/vector icon set, logo system, or illustration library inside the repo
- Creating simple shapes, diagrams, wireframes, or icons that are better produced directly in SVG, HTML/CSS, or canvas
- Making a small project-local asset edit when the source file already exists in an editable native format
- Any task where the user clearly wants deterministic code-native output instead of a generated bitmap
- When the user explicitly wants the official built-in `image_gen` workflow and that tool is available

## Decision tree

Think about two separate questions:

1. **Intent:** is this a new image or an edit of an existing image?
2. **Execution strategy:** is this one asset or many assets/variants?

Intent:
- If the user wants to modify an existing image while preserving parts of it, treat the request as **edit**.
- If the user provides images only as references for style, composition, mood, or subject guidance, treat the request as **generate**.
- If the user provides no images, treat the request as **generate**.

Edit semantics:
- Edit mode is for images already visible in the conversation context, images generated earlier in the thread, or local image files whose paths are available.
- If a local file is the edit target, pass its absolute path with `--image`.
- For edits, preserve invariants aggressively and save non-destructively by default.

Execution strategy:
- For one asset, issue one CLI call.
- For many assets or variants, issue one CLI call per requested asset or variant. Do not rely on `--n` for multi-image delivery in the current CodexManager route; it may return only one `data[]` item even when a larger `--n` is requested.
- For many assets with reference or edit images, repeat the same relevant `--image` arguments on every independent CLI call so each request has the full visual context.
- When generating multiple independent images, stream progress back to the user: after each CLI call succeeds, immediately send a commentary message with the newly completed image rendered inline. Do not wait for all images to finish before showing completed results. A final response can then briefly summarize the batch.
- If independent calls are safe to run in parallel, use parallel tool calls, but still report images as each tool result becomes available. If strict ordering matters, run them sequentially and report each image immediately.

Failure and retry policy:
- If an image request fails, tell the user the readable reason in Chinese, including the HTTP status or CLI error summary when available.
- Retry transient failures up to 3 total attempts per independent image request. Count the first attempt as attempt 1, so at most 2 retries follow it.
- Treat network timeouts, connection resets, HTTP 408, HTTP 409, HTTP 429, and HTTP 5xx as retryable unless the error body clearly says the request is invalid.
- Do not retry clearly non-transient failures such as missing input image files, missing `OPENAI_API_KEY`, invalid `config.toml`, HTTP 400 validation errors, HTTP 401/403 auth or permission errors, unsupported model/parameter errors, or policy/safety rejections. Report the reason and stop that item.
- For multi-image jobs, a failure in one independent request must not hide completed images from other requests. Return successful images as they complete; report failed items with their final reason and attempt count.
- If all retry attempts fail for an item, report in Chinese that the item failed after 3 attempts and include the final error summary. Do not silently skip failed images.

Assume the user wants a new image unless they clearly ask to change an existing one.

## Workflow
1. Decide the intent: `generate` or `edit`.
2. Decide whether the output is preview-only or meant to be consumed by the current project.
3. Decide the execution strategy: single asset vs repeated calls.
4. Collect inputs up front: prompt(s), exact text (verbatim), constraints/avoid list, and any input images.
5. For every input image, label its role explicitly:
   - reference image
   - edit target
   - supporting insert/style/compositing input
6. If the user asked for a photo, illustration, sprite, product image, banner, or other explicitly raster-style asset, use CodexManager image generation rather than substituting SVG/HTML/CSS placeholders. If the request is for an icon, logo, or UI graphic that should match existing repo-native SVG/vector/code assets, prefer editing those directly instead.
7. Augment the prompt based on specificity:
   - If the user's prompt is already specific and detailed, normalize it into a clear spec without adding creative requirements.
   - If the user's prompt is generic, add tasteful augmentation only when it materially improves output quality.
8. Call `scripts/cm_image_gen.py` under the failure and retry policy.
9. If the call fails, classify the failure as retryable or non-retryable, retry when appropriate, and tell the user the final readable reason if it cannot be completed.
10. Inspect outputs and validate: subject, style, composition, text accuracy, and invariants/avoid items.
11. Iterate with a single targeted change, then re-check.
12. For preview-only work, render the generated PNG inline in the final response using Markdown image syntax with the absolute local file path so the Codex App chat window shows the image.
13. For project-bound work, keep the selected artifact in `generated-images/` or move/copy it only to a user-named destination, then update consuming code or references if needed.
14. For batches, persist only the selected finals in the workspace unless the user explicitly asked to keep discarded variants. Return each completed batch item inline as soon as that item is saved.
15. Keep the final response minimal. Do not print the final prompt, validation details, file size, JSON output, model, base URL, or absolute path unless the user explicitly asks for them.

## Commands

Generate:

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" generate --prompt "<final prompt>"
```

Edit:

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" edit --image "<absolute image path>" --prompt "<edit prompt>"
```

Useful options:

```powershell
--size 1024x1024
--response-format b64_json
--out-dir "D:\path\to\output"
--filename "asset-name.png"
--quality high
--background transparent
--output-format png
```

After a successful call:
- Parse the printed JSON.
- Use the first absolute `paths[]` item as the final image path unless the user requested multiple outputs.
- Do not call a local image viewing tool for the final answer. In Codex App this can create a broken gray preview placeholder for CLI-created local images.
- Render each final generated PNG inline in the final response using standard Markdown image syntax and the absolute local file path. Use forward slashes in the Markdown URL for Windows paths, for example `![generated image](D:/path/to/generated-images/asset.png)`.
- For multi-image jobs, also render each completed PNG inline in a commentary update as soon as that individual image is saved, using the same absolute-path Markdown syntax.
- Do not use relative paths, `file://` URLs, HTML image tags, fake preview blocks, or unrelated file cards.
- Do not attach or report unrelated files such as `AGENTS.md`.
- The normal saved path should be the current working directory's `generated-images/<filename>` file, but do not print the path in the final response unless the user asks.
- Do not print the final prompt, prompt spec, validation result, file size, model, base URL, raw JSON, or command output in the final response unless the user asks.
- For single-image jobs, the final response should be only a short completion sentence plus the inline generated image, unless the user asks for details. For multi-image jobs, show each image in commentary as it completes; the final response should be a short completion summary and may repeat the final set inline if useful.
- For edits, also keep track of the source image path.

After a failed call:
- Read the CLI stderr/stdout and surface a short readable reason to the user in Chinese. Prefer the exact HTTP status plus a concise API error message when available.
- Retry only according to the failure and retry policy above, with at most 3 total attempts per independent image request.
- For non-retryable errors, stop immediately and explain in Chinese what needs to change, such as fixing auth, choosing a supported model/parameter, or providing an existing image path.

## Prompt augmentation

Reformat user prompts into a structured, production-oriented spec. Make the user's goal clearer and more actionable, but do not blindly add detail.

Treat this as prompt-shaping guidance, not a closed schema. Use only the lines that help, and add a short extra labeled line when it materially improves clarity.

### Specificity policy

Use the user's prompt specificity to decide how much augmentation is appropriate:

- If the prompt is already specific and detailed, preserve that specificity and only normalize/structure it.
- If the prompt is generic, you may add tasteful augmentation when it will materially improve the result.

Allowed augmentations:
- composition or framing hints
- polish level or intended-use hints
- practical layout guidance
- reasonable scene concreteness that supports the stated request

Not allowed augmentations:
- extra characters or objects that are not implied by the request
- brand names, slogans, palettes, or narrative beats that are not implied
- arbitrary side-specific placement unless the surrounding layout supports it

## Use-case taxonomy (exact slugs)

Classify each request into one of these buckets and keep the slug consistent across prompts and references.

Generate:
- photorealistic-natural — candid/editorial lifestyle scenes with real texture and natural lighting.
- product-mockup — product/packaging shots, catalog imagery, merch concepts.
- ui-mockup — app/web interface mockups and wireframes; specify the desired fidelity.
- infographic-diagram — diagrams/infographics with structured layout and text.
- logo-brand — logo/mark exploration, vector-friendly.
- illustration-story — comics, children's book art, narrative scenes.
- stylized-concept — style-driven concept art, 3D/stylized renders.
- historical-scene — period-accurate/world-knowledge scenes.

Edit:
- text-localization — translate/replace in-image text, preserve layout.
- identity-preserve — try-on, person-in-scene; lock face/body/pose.
- precise-object-edit — remove/replace a specific element (including interior swaps).
- lighting-weather — time-of-day/season/atmosphere changes only.
- background-extraction — transparent background / clean cutout.
- style-transfer — apply reference style while changing subject/scene.
- compositing — multi-image insert/merge with matched lighting/perspective.
- sketch-to-render — drawing/line art to photoreal render.

## Shared prompt schema

Use the following labeled spec as shared prompt scaffolding:

```text
Use case: <taxonomy slug>
Asset type: <where the asset will be used>
Primary request: <user's main prompt>
Input images: <Image 1: role; Image 2: role> (optional)
Scene/backdrop: <environment>
Subject: <main subject>
Style/medium: <photo/illustration/3D/etc>
Composition/framing: <wide/close/top-down; placement>
Lighting/mood: <lighting + mood>
Color palette: <palette notes>
Materials/textures: <surface details>
Text (verbatim): "<exact text>"
Constraints: <must keep/must avoid>
Avoid: <negative constraints>
```

Notes:
- `Asset type` and `Input images` are prompt scaffolding, not dedicated CLI flags.
- `Scene/backdrop` refers to the visual setting. It is not the same as the CLI `background` parameter, which controls output transparency behavior.

Augmentation rules:
- Keep it short.
- Add only the details needed to improve the prompt materially.
- For edits, explicitly list invariants (`change only X; keep Y unchanged`).
- If any critical detail is missing and blocks success, ask a question; otherwise proceed.

## Examples

### Generation example (hero image)
```text
Use case: product-mockup
Asset type: landing page hero
Primary request: a minimal hero image of a ceramic coffee mug
Style/medium: clean product photography
Composition/framing: wide composition with usable negative space for page copy if needed
Lighting/mood: soft studio lighting
Constraints: no logos, no text, no watermark
```

### Edit example (invariants)
```text
Use case: precise-object-edit
Asset type: product photo background replacement
Primary request: replace only the background with a warm sunset gradient
Constraints: change only the background; keep the product and its edges unchanged; no text; no watermark
```

## Prompting best practices
- Structure prompt as scene/backdrop -> subject -> details -> constraints.
- Include intended use (ad, UI mock, infographic) to set the mode and polish level.
- Use camera/composition language for photorealism.
- Only use SVG/vector stand-ins when the user explicitly asked for vector output or a non-image placeholder.
- Quote exact text and specify typography + placement.
- For tricky words, spell them letter-by-letter and require verbatim rendering.
- For multi-image inputs, reference images by index and describe how they should be used.
- For edits, repeat invariants every iteration to reduce drift.
- Iterate with single-change follow-ups.
- If the prompt is generic, add only the extra detail that will materially help.
- If the prompt is already detailed, normalize it instead of expanding it.

More principles: `references/prompting.md`.
Copy/paste specs: `references/sample-prompts.md`.

## Guidance by asset type
Asset-type templates (website assets, game assets, wireframes, logo) are consolidated in `references/sample-prompts.md`.

## Reference map
- `references/prompting.md`: shared prompting principles.
- `references/sample-prompts.md`: shared copy/paste prompt recipes.
- `references/cli.md`: CLI usage reference.
- `references/image-api.md`: API/CLI parameter reference.
- `references/codex-network.md`: network/sandbox troubleshooting.
- `scripts/cm_image_gen.py`: CodexManager CLI implementation.
