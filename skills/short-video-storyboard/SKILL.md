---
name: short-video-storyboard
description: Plan storyboard sheets, system Imagegen/image2 director-board packages, visual frame packages, visual+text shot cards with real rendered labels, no-text video reference frames, continuous 5-10s prompts, start/end keyframes, hierarchical 100s macro-storyboards, text-paired shot boards, weighted references, domestic Chinese video-model safe prompt variants, and image-to-video prompt packs. Use for 分镜, 图文镜头, 图文故事版, 有画面, 有文字说明, 不只是文字, 画面参考, 首帧图, 角色选择, 女主选择, 温暖手绘动画, 剧本转视频, 剧本分镜, 10秒一集, 100秒故事, 首尾帧, 文案/旁白/字幕分镜, 连续视频, 一镜到底, 不连续, 跳切, 像10个故事, 参考图权重, 国内模型, 敏感词, 正向画面约束, 唯美玄幻, 仙侠, xianxia, fantasy storyboard, keyframes, or AI-video planning.
---

# Short Video Storyboard

## Overview

Turn a rough idea into a usable storyboard workflow: lock the character or product, expand the concept into shots, prepare prompts for image or video tools, and assemble a reviewable contact sheet.

User preference from 2026-06-04: future script/storyboard deliverables should usually follow the polished director-board pattern: generate a system Imagegen/image2 visual storyboard sheet first, then provide copyable image-to-video prompts that map the shots/time beats while keeping video size/aspect/duration in a separate upload/settings note instead of repeating those tool settings inside the prompt body.

User preference from 2026-06-05: final image/storyboard/video-prompt packages must be easy to copy and save. Show generated or saved images inline with absolute-path Markdown image tags, include exact local paths, and put the final model-facing prompt in a fenced `text` code block. When useful, also write matching `.txt` and `.md` files in the output folder.

Prefer this skill for requests such as:
- `跳舞分镜`
- `舞蹈分镜`
- `AI带货分镜`
- `抖音服装带货分镜`
- `梦幻视频分镜`
- `唯美玄幻首尾帧`
- `仙侠分镜图`
- `国风神话视频关键帧`
- `10个大镜头，每个大镜头10秒`
- `100秒故事分层分镜`
- `每一镜对应一张连续图文故事版`
- `剧本转视频，先给分镜图再给提示词`
- `图文镜头，每镜要有文字说明`
- `有画面，不只是文字`
- `女主选择不对，重新锁定角色气质`
- `要能当视频首帧的画面参考`
- `一张图里 25 格以上分镜`
- `只有首尾帧，帮我补动作`
- consistent-character short-video planning
- storyboards that must later feed image-to-video tools

## Workflow Decision Tree

1. Decide the output mode.
   - `Pitch board`: one-sheet board for ideation or approval. One-shot 25-panel generation is acceptable as a preview.
   - `Production board`: a stable board that will drive image or video generation. Generate panels individually or in small groups, then stitch them.
   - `Xianxia fantasy board`: use when the user wants Chinese fantasy, immortal palace, mythic landscape, sacred tree, cloud sea, god rays, spell formation, flying creatures, or robed-figure spectacle.
   - `Start/end motion board`: use when the user has only the first and last frame or wants one motion arc completed between two locked poses.
   - `System Imagegen director board`: use by default for scripts, dynamic wallpapers, image-to-video plans, or when the user wants a storyboard image that will guide a video model. Create a polished visual board with system Imagegen/image2, then provide exact copyable prompts separately.
   - `Visual frame package`: use when the user asks for `有画面`, `不只是文字`, `画面参考`, `首帧图`, or a video-ready deliverable. Generate actual image files such as clean start frames, optional end frames, and visual storyboard boards. If the user says `图文镜头` or `图文故事版`, also create a visual+text card with real rendered labels/captions outside or beside the image panels. A no-text visual board alone is not sufficient for `图文`.
   - `Continuous single-video prompt`: use when the user wants one generated 5-10s video rather than edited shots, or reports that the output feels jumpy, discontinuous, or like multiple stories. Compress the storyboard into 3-4 connected action beats in one continuous space; do not write every panel as a hard one-second scene.
   - `Hierarchical macro-story board`: use when the user wants a longer story such as 100 seconds, 10 big shots, or 10-second episodes. Create a two-level package: one large overview board for the 10 macro beats, plus one large continuous story card for each macro beat.
   - `Domestic safe prompt variant`: use only when the user mentions 国内生成视频模型, 平台拦截, 敏感词, 审核, or wants a domestic test pack. Keep the foreign/original prompt pack unchanged, create a separate domestic-safe folder or file, replace risky terms with neutral positive descriptions, and replace `禁忌/不要/避免/负面提示词` blocks with `正向画面约束`.

### Prompt Setting Separation

- Treat video size, aspect ratio, resolution, frame rate, total duration, and platform wrapper as upload/settings metadata.
- Do not repeat size/aspect/duration wrapper phrases inside the fenced copyable prompt when the tool UI, storyboard title, or upload note already carries that information.
- Timecoded beats are allowed inside the prompt because they control motion. The redundant task wrapper is what should be removed.
- If a target tool has no separate settings or the user explicitly asks for an all-in-one prompt, include one concise settings line at the top and do not repeat it later.

### Copy/Save Handoff Default

- For any final package that includes generated images, storyboards, motion references, start frames, or visual+text cards, embed each local image in the final response with Markdown image syntax and an absolute path, for example `![图2 动作参考图](D:/.../motion-guide.png)`.
- Also list the exact local file path for each image so the user can find, drag, copy, upload, or save it outside the chat.
- Put the final prompt in one fenced `text` code block that contains only the copyable model-facing prompt body. Keep upload order, settings, file paths, and explanatory notes outside the code block unless the user explicitly asks for all-in-one text.
- When reference image roles matter, label them by upload number (`图1`, `图2`, `图3`) and make the same numbers appear in both the upload note and the copyable prompt.
- If a required source image is thread-only and not saved locally, say so clearly, keep its role in the upload map, and show/save the generated companion images that are available locally.
- For multi-segment AI video series, default each segment to 10 seconds unless the user gives a specific duration. Split each segment into two layers: a human-review layer and a video-model upload layer.
  - Human-review layer: 图文故事版 / visual-text storyboard, generated by Imagegen when the user wants a real storyboard image. It is for rhythm, shot discussion, and prompt binding.
  - Video-model upload layer: clean first/start frame, optional clean last/end frame when the tool supports it, and optional no-text action reference. Do not make a text-heavy storyboard board the default upload reference.
- For Doubao/Seedance-style tools, first identify the UI mode: 首帧/尾帧, 图生视频, or 全能参考/多模态参考. If the mode is unclear, default to the minimal upload: one clean protagonist/start-frame anchor plus one clean no-text action reference. Do not upload visual-text boards, contact sheets, route maps, or multi-panel cards as formal video references unless the user intentionally wants a pollution test.
- When a visual-text storyboard is mentioned in a prompt, explicitly mark it as human rhythm review only and state that the final video must not inherit its text, titles, timecodes, borders, layout, or panel grid.

2. Lock the protagonist and the visual system before expanding shots.
   - If the user wants a specific person, avatar, IP, or seller persona, ask for or reuse 3-8 reference images when available.
   - If no protagonist is provided and visual style depends on the protagonist, generate a `character bible` or `protagonist selection board` first: front view, 3/4 view, full body, close-up, expression samples, and a simple action pose.
   - For requests like `宫崎骏那种感觉`, do not imitate or name a living artist/studio in generation prompts. Translate the intent into safe traits: classic warm hand-drawn Japanese animated-film heroine energy, rounded simple face, soft expressive eyes, small natural nose/mouth, gentle everyday proportions, modest rural clothing, slightly wind-tousled hair, wholesome curiosity, hand-painted watercolor background, cozy domestic detail. Use these traits as the character lock before generating frames.
   - Lock hairstyle, face shape, age range, garment silhouette, footwear, accessories, product colorway, and environment family in text before prompting panels.

3. Choose the shot count by task.
   - `9-12 panels`: fast motion test or start/end interpolation.
   - `16 panels`: one beat with light variation.
   - `25 panels`: preferred default for Douyin/TikTok commerce and dance explainability.
   - `25+ panels`: use for transformations, costume changes, multi-room fantasy sequences, or seller-to-product narrative arcs.

4. Write the board in layers instead of one giant prompt.
   - `Global lock`: character, product, style, lighting, lens family, aspect ratio, platform.
   - `Text lock`: the source script/copy/narration beat that each panel visualizes, plus subtitle/voiceover and sound cues when useful.
   - `Sequence lock`: what changes across the board and what must never change.
   - `Panel prompt`: camera distance, pose or action, prop usage, emotion, environment detail, motion cue.
   - `Video handoff`: start frame, end frame, or keyframe notes for each beat that will become video.

5. Render and validate.
   - Use `scripts/storyboard_cli.py new-spec` to seed a template from `assets/`.
   - Fill or refine the panel prompts.
   - Use `scripts/storyboard_cli.py render-sheet` to build the review board.
   - Use `scripts/storyboard_cli.py export-markdown` to create a shot list that can be pasted into other tools or docs.
   - When the user expects an AI-looking storyboard image, generate the primary visual director board with system Imagegen/image2. Use script-rendered sheets for deterministic text, QA, and post-overlay, not as the only final visual.
   - If the user asked for visuals, generate or attach real image files before calling the deliverable complete. Placeholder text cards count only as planning artifacts.
   - If the user asked for `图文`, verify the final PNG visibly contains both image panels and readable real text rendered by the layout/postprocess step. Do not rely on image generation to create small Chinese text.

## Character And Product Lock

Treat protagonist consistency as a hard requirement, not a styling suggestion.

When the user provides a protagonist:
- Reuse the provided images directly when the downstream tool supports character reference or image reference.
- Record what is invariant: face, body shape, hair, costume core pieces, branded product details, and signature accessories.

When the user does not provide a protagonist:
- Create a neutral but reusable anchor first.
- Prefer one clean character sheet over improvising the face in 25 panels.
- Tell the user that the fastest path is a demo board now plus a later reference-based refinement pass.

For AI commerce, keep the product truthful:
- Do not let sleeve length, hemline, logo placement, fabric texture, or color drift across panels.
- Add dedicated detail shots for texture, zipper or button, back view, and movement behavior.

## Use The Right Output Pattern

### Dance storyboard

Use a 5x5 board when the user wants:
- motion progression
- blocking for arms and legs
- outfit reveal
- beat-synced pose changes

Cover:
- opening hook
- full-body rhythm shots
- side profile
- footwork insert
- hair or fabric motion
- climax pose
- landing pose or loop reset

### Douyin/TikTok AI commerce storyboard

Build the board around selling beats, not only beauty shots.

Include:
- first-3-second hook
- product-on-body hero
- silhouette proof
- fabric detail
- movement proof
- styling variations
- social-proof or host-energy shots
- CTA-ready closing frame

Read `references/workflow.md` for a ready-made 25-panel layout.

### Dreamy cinematic storyboard

Use slower camera grammar:
- floats, drifts, glides, reveals
- particles, haze, glow, water, fabric, mirrors
- foreground obstruction and parallax
- one emotional arc, not random spectacle

Lock the color logic before panel expansion so the sequence feels intentional.

### Xianxia fantasy storyboard

Use `xianxia-fantasy-25` when the request says `唯美玄幻`, `仙侠`, `国风神话`, `东方幻想`, `山海经`, `仙宫`, `神殿`, `巨树`, `云海`, `御剑`, `飞升`, or similar.

Default contract:
- Treat the world itself as a continuity object: palace silhouette, mountain layout, sacred tree, cloud sea, lighting direction, and magic color should not drift randomly.
- Keep the protagonist small in some wide shots so the scale reads; use close shots sparingly to preserve emotion.
- Separate spectacle beats from action beats. Do not combine a new world, new power, new costume, and new camera move in one panel unless the brief asks for a transformation.
- If the user only asks for `首尾帧`, produce or plan two strong endpoint frames plus 5-9 bridge beats, not a loose 25-panel sequence.
- If the user says `分镜图` or `镜头拆解`, default to a 25-panel board with labels, captions, per-panel prompts, and video handoff fields.

### Start/end-frame motion board

Use when the user has only the beginning and ending pose or scene.

Rules:
- Keep one action arc per board.
- Keep the camera family stable unless a deliberate mid-shot change is part of the brief.
- Insert 5-9 bridge beats between start and end.
- Avoid changing costume, room, or product mid-interpolation unless the change itself is the point.

## Default Operating Pattern

1. Read `references/workflow.md` for the decision matrix and mode-specific shot plans.
2. Read `references/prompt-recipes.md` for prompt formulas and Chinese examples.
3. Read `references/research.md` only when tool selection or capability claims need verification.
4. Seed a JSON spec from `assets/`.
5. Use `inspect-brief` when you want to see how the brief will be parsed before touching a spec.
6. For a quick first pass, use `apply-brief` to inject a Chinese or English brief and create a reusable global lock automatically.
7. Use `attach-references` to register protagonist images, layered references, and first/last frames in the spec. Use `--reference-weight`, `--reference-priority`, `--reference-crop`, `--reference-focus`, and `--reference-lock` when one reference should win conflicts or only affect a crop/focus area. Use `--panel` when one anchor should only affect a specific shot.
8. If the user gave earlier text, script copy, narration, subtitles, or beat notes, map that text before or while setting camera language. Prefer `source_panel`, `source_visual`, `story_beat`, `subtitle`, `voiceover`, `sound_design`, and `binding_status`; keep `text_source`, `story_text`, and `subtitle_voiceover` for simpler or legacy combined cases. If no text is provided but the user wants a complete storyboard, write short original lines and mark them as `generated/original`.
9. Use `annotate-panel` to set formal video handoff fields such as `keyframe_role`, `duration_sec`, `camera_move`, `transition_to_next`, `motion_strength`, and `loop_safe`, plus text fields via `--source-panel`, `--source-visual`, `--story-beat`, `--subtitle`, `--voiceover`, `--text-source`, `--story-text`, `--subtitle-voiceover`, `--sound-design`, and `--binding-status`.
10. Fill or refine `panels[].prompt`, `panels[].caption`, and `panels[].image` as the board evolves. When adding text bindings, preserve existing `image` paths instead of replacing the visual panel with text-only notes.
11. Render the board with the script.
12. Use `export-prompts` to create per-panel prompt files, grouped prompt files, JSONL, CSV, and video handoff exports for the next stage.
13. If the user wants video next, turn the same board into per-shot video prompts or start/end-frame pairs.
14. If the user wants one continuous 10s video, or says the generated result changes too much every second, create a separate continuous-video prompt. Preserve one location/camera path, merge the board into 3-4 macro beats, use at most one or two image references, and explicitly forbid hard cuts, scene jumps, and “ten image slideshow” behavior. Put size/aspect/duration as upload/settings metadata rather than repeating it in the prompt body.
15. For a Seedance/Doubao mismatch fix, do not just add more storyboard text. First audit whether uploaded images are fighting each other. If the output follows the landscape/storyboard instead of the intended human action, remove the visual-text board from the upload set, regenerate a cleaner action reference or first frame, and rewrite the prompt around concrete subject actions from the first second.
16. For a continuity fix, do not add more panels. Remove beats instead: choose a later start point, lock one spatial route, write a single camera path, and recommend two 5s clips when the board spans more geography than one generation can handle.
17. If the user says the deliverable needs `有画面` or is not allowed to be only text, generate at least one clean visual start frame per continuous clip and, when useful, a no-text visual storyboard board for video planning. Store generated images under the project output folder, copy from temporary generation folders instead of deleting originals, and list exact image paths in the README/copy-ready handoff.
18. For script-to-video, dynamic wallpaper, or image-to-video packages, prefer a polished system Imagegen/image2 director board as the primary human-review visual. The video-model upload package should still use clean no-text start/end/action references. The video prompt should explicitly define reference roles, subject locks, motion beats, and continuity; do not stuff video size/aspect/duration wrappers into the prompt body unless requested.
19. If exact text is important, use a two-pass board: let system Imagegen create the high-quality visual director board, then render real Chinese timecodes, shot labels, captions, or notes with PIL/local layout. Treat small text generated inside the Imagegen board as visual texture until verified.
20. If the user says `图文镜头`, `图文故事版`, `每一镜对应文字`, or complains that the visual board has no text, create a separate visual+text card. Use generated images for the visual area and render timecode, shot goal, action, camera, subtitle/voiceover, and sound notes as real text with PIL or the local renderer. Keep video-reference images clean/no-text, but the human review card must include text.
21. If the user wants 10 big shots where each big shot is its own 10s clip, build hierarchy instead of one dense sheet: `overview` = 10 macro story beats for the full 100s story; `episode cards` = each macro beat expanded into a continuous 10s route with 0-2s, 2-5s, 5-8s, and 8-10s beats. Keep each episode prompt separate.
22. For readability, do not put all 100 seconds into one tiny contact sheet. Use a large overview board and separate per-episode boards, each with enough pixel space for readable Chinese text and a large visual anchor.
23. For human copy/paste, separate reference paths and upload/settings metadata from the actual prompt. Provide `copy-ready` Markdown with one fenced `text` code block per episode, plus clean TXT files that contain only the model-facing prompt body.
24. For user handoff, show every final local image inline with absolute-path Markdown image tags, list the image paths, and provide the copyable prompt in a fenced `text` block. Do not finish with only file paths when the user expected saveable images.
25. For domestic Chinese video-model variants, keep the original/foreign-tested pack intact and write a separate domestic-safe output. In the domestic prompt body, use only positive model-facing fields: `定位`, `人物锁定`, `承接上一集`, `本集目标`, `引出下一集`, `时间节拍`, `镜头要求`, `动作细节`, `构图节奏`, `视觉风格`, `平台适配`, and `正向画面约束`. Do not include a negative-prompt block.

Ask a concise question only when the missing answer changes the output type:
- `你要两张首尾帧，还是一张分镜图/25格分镜板？`
- `视频比例/尺寸按工具默认，还是需要我在上传建议里单独标出来？`
- `主角要固定同一个人吗？如果要，最好给人物参考图。`

## Commands

Seed a 25-panel commerce template:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py new-spec --profile commerce-fashion-25 --language zh --out D:\path\to\board.json
```

Seed a 25-panel xianxia fantasy template:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py new-spec --profile xianxia-fantasy-25 --language zh --out D:\path\to\xianxia-board.json
```

Inspect a brief before writing files:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py inspect-brief --profile commerce-fashion-25 --brief "抖音秋装针织裙带货，温柔姐姐主播，米色极简直播间，高级真实，重点突出显瘦和面料垂感"
```

Apply a brief and build the global lock:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py apply-brief --spec D:\path\to\board.json --out D:\path\to\board-filled.json --brief "抖音秋装针织裙带货，温柔姐姐主播，米色极简直播间，高级真实，重点突出显瘦和面料垂感"
```

Attach protagonist images, references, and first/last frames:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py attach-references --spec D:\path\to\board-filled.json --out D:\path\to\board-final.json --protagonist-image D:\path\to\hero-front.png --protagonist-image D:\path\to\hero-fullbody.png --reference-image D:\path\to\product-detail.png --first-frame D:\path\to\frame-start.png --last-frame D:\path\to\frame-end.png
```

Attach weighted anchors with explicit crop/focus guidance:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py attach-references --spec D:\path\to\board-filled.json --out D:\path\to\board-final.json --face-anchor D:\path\to\face-crop.png --reference-weight 1.0 --reference-priority 100 --reference-crop "face close-up / 3:4 portrait crop" --reference-focus "face identity, hairline, eyes, expression" --reference-lock hard-identity
```

Attach a product-detail override to one specific panel:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py attach-references --spec D:\path\to\board-final.json --out D:\path\to\board-final.json --panel 8 --product-anchor D:\path\to\collar-detail.png --reference-weight 0.95 --reference-priority 105 --reference-crop "collar macro crop" --reference-focus "领口、肩线、扣位和面料纹理" --reference-lock hard-detail --panel-note "这一格优先看领口和肩线细节"
```

Annotate video handoff fields for a panel:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py annotate-panel --spec D:\path\to\board-final.json --out D:\path\to\board-final.json --panel 1 --keyframe-role start --duration-sec 1.1 --camera-move push-in --transition-to-next cut --motion-strength medium --loop-safe false --shot-note "首格负责3秒内钩子"
```

Annotate a panel with prior text, subtitle or voiceover, and sound:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py annotate-panel --spec D:\path\to\board-final.json --out D:\path\to\board-final.json --panel 1 --source-panel "V2#01" --source-visual "黄沙地下入口，三位探险者围在入口边缘准备进入" --story-beat "入口风声暗示下方另有空间" --subtitle "下面的风，是从更深处吹上来的。" --voiceover "下面的风，是从更深处吹上来的。" --sound-design "低频风声、沙粒滑落、绳索轻响" --binding-status derived
```

Render a board:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py render-sheet --spec D:\path\to\board.json --out D:\path\to\board.png
```

Export the shot list:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py export-markdown --spec D:\path\to\board.json --out D:\path\to\board.md
```

Export production-ready prompt packs:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py export-prompts --spec D:\path\to\board-final.json --out-dir D:\path\to\prompt-pack --group-size 5
```

Scan a domestic-safe prompt package before testing it in Chinese video tools:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py scan-domestic-safety --path D:\path\to\domestic-safe
```

## Validation

Check all of the following before presenting the board as final:
- The protagonist still looks like the same person across the sequence.
- The product details remain truthful.
- The panel order communicates a real motion or selling arc.
- The board still works if captions are removed.
- Attached references are stored with the right hierarchy: face, outfit, product, scene, style, and panel overrides.
- Reference anchors include usable `weight`, `priority`, `crop`, `focus`, and `lock`; conflict resolution reads priority first, then weight.
- If the user gave text, copy, narration, or a prior written version, every shot maps to it through `source_panel`, `source_visual`, `story_beat`, `subtitle`, `voiceover`, `sound_design`, `binding_status`, or a documented `generated/original` marker.
- Subtitle/voiceover text is treated as post-production guidance unless the user explicitly asks to render text inside the image.
- Text-paired shot storyboards still preserve the visual panel through `panels[].image`, Markdown image/path columns, prompt-pack TXT, CSV/JSONL, and `video-handoff.json`.
- Video handoff fields are present and meaningful for every panel.
- Per-panel copyable prompts stay near the user's practical limit, usually under 2000 Chinese characters unless a downstream tool explicitly accepts longer prompts.
- A single generated video prompt does not read like ten separate one-second stories. It should use one continuous action path, one spatial geography, 3-4 macro beats, one or two reference images at most, and explicit anti-jump-cut language.
- For Doubao/Seedance-style handoffs, visual-text boards are labeled human review only. The upload set should use clean first/start frames, optional end frames, and no-text action references; every uploaded asset must have one narrow role in the prompt.
- A hierarchical 100s package does not collapse into a 100-panel tiny sheet. It must have one 10-beat overview plus separate readable per-episode story cards.
- Copy-ready prompt packs keep upload/reference paths and video settings outside the prompt code block; the code block itself should be clean, structured, model-facing, and easy to copy.
- Final image/storyboard handoffs show local images inline via absolute Markdown image tags, include exact file paths, and include a fenced `text` prompt block that can be copied in one action.
- If the user asked for visuals, the final package contains real image files, not only text placeholders. Verify the image paths exist, dimensions are readable, and text-heavy story cards are clearly marked as human review only.
- If the user expected the new director-board workflow, the primary storyboard image should be a polished system Imagegen/image2 board, not only a local table or script-rendered contact sheet.
- If the user asked for `图文`, the final package contains at least one visual+text PNG where the text is readable and rendered by the layout step. A no-text visual storyboard board does not satisfy `图文`.
- For continuous-video generation, provide clean start-frame references separately from no-text visual storyboard boards and visual+text review cards. Recommend uploading the start frame to video tools, and using visual+text cards for human review rather than as the main video reference.
- For domestic Chinese video-model prompt packs, run `scan-domestic-safety` on the domestic-safe output. The prompt bodies should not contain the bundled sensitive-term list or negative-prompt markers, and should use `正向画面约束` instead of `禁忌`.
- Xianxia boards preserve the same world logic: palace or sacred-tree layout, light direction, magic color, costume silhouette, and scale relationship.
- `export-prompts` produces the machine-readable files needed by the next generation step.
- The first and last panels can feed an image-to-video model without ambiguous jumps.
- The board is readable as a 5x5 or 4x4 sheet on a normal desktop screen.

## Resources

- `references/workflow.md`: detailed workflow, decision matrix, and panel layouts
- `references/prompt-recipes.md`: prompt blocks and scenario-specific Chinese templates
- `references/research.md`: dated notes from official product pages and GitHub projects
- `assets/*.json`: starter specs for dance, commerce, dreamy, xianxia fantasy, and start/end workflows in English and Chinese
- `scripts/storyboard_cli.py`: inspect briefs, create template specs, apply briefs, attach layered references, annotate video handoff fields, render boards, and export prompt packs
