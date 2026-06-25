# Workflow Reference

## 1. Choose The Board Type First

Use this decision matrix before writing any prompts:

| Goal | Recommended board | Panel count | Generation strategy |
| --- | --- | --- | --- |
| Quick ideation or client pitch | One-sheet concept board | 9-25 | One-shot generation is acceptable |
| Reliable production board | Structured contact sheet | 16-25+ | Generate per panel or per row, then stitch |
| Dance blocking and pose progression | Motion storyboard | 25 | Keep one outfit and one space family |
| Douyin/TikTok apparel commerce | Selling storyboard | 25 | Reserve slots for hook, proof, detail, CTA |
| Dreamy fantasy clip | Mood storyboard | 16-25 | Lock atmosphere and color logic first |
| Xianxia / Chinese fantasy clip | Epic mythic storyboard | 25 | Lock world geography, scale, light direction, magic color, and protagonist costume |
| First/last frame action completion | Bridge board | 9-12 | Insert 5-9 bridge beats between endpoints |
| Existing script/copy/voiceover to shots | Text-paired shot storyboard | Match script beats | Map text beats first, then add camera/action/prompt fields |
| Prompt package must have actual visuals / 有画面 | Visual frame package | start frame + optional visual board | Generate real image files; text-only cards are planning artifacts |
| 图文镜头 / 图文故事版 | Visual+text shot card | match story beats | Composite real images with readable rendered text; no-text boards do not satisfy this |
| One generated 5-10s video | Continuous video prompt | 3-4 macro beats | Keep one spatial geography and avoid hard one-second cuts |
| Doubao/Seedance mismatch fix | Upload-role audit + clean references | start frame + optional action/end reference | Remove text-heavy boards from formal upload; make each uploaded asset serve one narrow role |
| 100s story / 10 big shots | Hierarchical macro-story package | 10 macro beats + 10 episode cards | Overview shows the whole story; each card is one continuous 10s clip |
| 国内视频模型被隐形拦截 | Domestic safe prompt variant | same story structure | Keep the foreign-tested pack unchanged; rewrite prompt bodies with positive-only wording |

## 2. Collect The Minimum Input Contract

Capture these fields before expanding shots:

1. `platform`: Douyin, TikTok, Reels, Xiaohongshu, pitch deck, or internal previs.
2. `aspect`: usually `9:16` for short-video boards, but contact sheets can be rendered on larger portrait canvases like `2400x3200`.
3. `board_type`: dance, commerce, dreamy, or start-end motion.
4. `protagonist`: exact person, generated anchor, or no protagonist yet.
5. `product`: for commerce, list category, silhouette, colorway, texture, brand marks, and truth constraints.
6. `mood`: energetic, luxurious, ethereal, intimate, club, editorial, fairy-tale, and so on.
7. `environment`: studio cyclorama, livestream room, rooftop, mirror hall, fantasy lake, tunnel, street, etc.
8. `must_keep`: things that cannot drift, such as face shape, garment details, logo position, background family, or lens language.
9. `must_change`: what should progress across panels, such as pose, distance, product angle, lighting intensity, or transformation stage.
10. `video_handoff`: which panels are only planning artifacts and which panels will feed an image-to-video tool.
11. `text_handoff`: prior script/copy/narration/subtitles that must stay paired with specific panels.
12. `hierarchy`: whether the user wants one dense board, or a two-level structure such as 10 macro shots x 10 seconds each.

Infer simple defaults when safe. Ask only if the missing detail affects layout, character identity, product truth, or the downstream tool choice.

## 3. Decide Whether You Need A Protagonist Reference

### When The User Should Provide A Protagonist

Require or strongly recommend user-provided references when:

- the face must match a real host, seller, influencer, or mascot
- the user wants the same person across many shots
- the product is worn by a repeatable brand persona
- the next step will use character-reference or keyframe-based video tools

Preferred pack:

1. front portrait
2. 3/4 portrait
3. full-body neutral stance
4. full-body action stance
5. close-up smiling or talking
6. product-holding pose

### When You Can Proceed Without A Protagonist

Proceed without a user reference when the board is only a draft or idea exploration. In that case:

1. create a `character bible` first
2. reuse the same face/body description in every prompt
3. avoid wardrobe drift
4. tell the user that the face can be locked harder once real references arrive

## 4. Build The Board In Layers

Use the same four-layer structure every time:

1. `Global lock`
   - subject identity
   - wardrobe or product lock
   - style, lighting, and color logic
   - environment family
   - platform and aspect

2. `Sequence lock`
   - what changes from panel to panel
   - what never changes
   - tempo and camera family

3. `Text lock`
   - source text or script beat
   - story text the shot must visualize
   - subtitle or voiceover line for post-production
   - sound or music cue

4. `Panel block`
   - shot size
   - angle
   - exact action
   - expression
   - prop or product emphasis
   - motion cue

5. `Video handoff`
   - whether the panel becomes a start frame, end frame, or internal key beat
   - whether the next tool needs text guidance, character references, or both

## 5. Default 25-Panel Dance Layout

Use this when the core task is movement explainability:

1. hook silhouette
2. full-body front pose
3. first weight shift
4. arm extension
5. torso twist
6. side profile rhythm
7. footwork insert
8. head turn
9. hair or fabric motion
10. low-angle power pose
11. traveling step
12. front medium shot
13. hands detail
14. half-spin
15. spin midpoint
16. spin exit
17. landing stance
18. smile or charisma close-up
19. diagonal pose
20. backward step
21. full-body climax
22. wide reset
23. final accent
24. hold pose
25. loop-ready ending pose

## 6. Default 25-Panel Commerce Layout

Use this when the board must sell apparel or styling:

1. first-3-second hook
2. hero full-body front
3. 3/4 pose
4. side silhouette
5. back silhouette
6. walking approach
7. fabric movement proof
8. collar or neckline detail
9. sleeve detail
10. waist fit
11. hem movement
12. pocket or zipper detail
13. seated or casual lifestyle pose
14. dance-like energy pose
15. turn-around midpoint
16. smile to camera
17. mirror or selfie angle
18. close hero on texture
19. styling variation A
20. styling variation B
21. layering variation
22. social-proof or livestream energy
23. close hero with product held closer
24. clean front hero reset
25. CTA-ready final frame

Commerce rule: the garment must remain truthful even when the background or pose changes.

## 7. Default 25-Panel Dreamy Layout

Use this when the clip is about atmosphere rather than hard selling:

1. establishing dream space
2. slow entry
3. subject reveal through haze
4. floating close-up
5. hand through light particles
6. draped fabric motion
7. reflective surface shot
8. side portrait
9. low-angle glow
10. mirror double
11. walking through veil
12. pause and breathe
13. eye close-up
14. water, glass, or dew macro
15. wide emotional release
16. turning away
17. over-shoulder recall
18. foreground obstruction
19. halo or rim-light shot
20. drifting medium shot
21. reaching gesture
22. environment reaction
23. full-body surreal hero
24. fade-like stillness
25. exit or dissolve frame

## 8. Start/End Motion Workflow

Use a smaller bridge board when the user says "I only have the first and last frame" or "Use start and end frame to finish the action."

Recommended pattern:

1. start frame
2. anticipation
3. action start
4. midpoint A
5. midpoint B
6. climax of movement
7. deceleration
8. settle
9. end frame

Rules:

- keep the same outfit, environment, and subject unless the transformation itself is the brief
- keep the same camera family or document the exact moment it changes
- do not combine a major camera move and a major pose change and a costume change in one jump
- if the action is too large, split it into two boards

## 9. Generate The Images The Right Way

Do not rely on one giant prompt for the final production board unless the user explicitly wants speed over control.

If the user asks for `有画面`, `不只是文字`, `画面参考`, or video-ready references, a text-only contact sheet is incomplete. Produce actual image files: at minimum a clean start frame for each continuous clip, and when useful a visual storyboard board.

If the user asks for `图文镜头`, `图文故事版`, `每镜对应文字`, or complains that the visual board has no text, a no-text storyboard is also incomplete. Produce a separate visual+text shot card with actual readable text rendered by the layout/postprocess step.

Use this order:

1. write the board spec
2. generate a protagonist anchor if needed
3. generate key panels or rows
4. correct any drift
5. attach image paths into the JSON spec
6. render the final contact sheet
7. for `图文`, render a final composited visual+text card from real images plus real text; do not ask the image model to draw small Chinese labels

For fast ideation, a single board-generation prompt is acceptable. For production, panel-by-panel or row-by-row control is more reliable.

Visual delivery rules:

- Store generated frames in the project output folder and keep the original generator output in place unless the user asks to delete it.
- Record exact image paths in the README or copy-ready package.
- Keep two outputs when needed: clean no-text frames for video tools, and visual+text cards for human review.
- Mark visual+text or text-heavy story cards as human review only; do not recommend uploading them as video references.
- For one continuous video, upload one clean start frame, optionally one clean end frame when the tool supports it. Do not upload a multi-panel board as the primary video reference.
- For Doubao/Seedance-style UIs, distinguish `首尾帧` from `全能参考/多模态参考` before recommending uploads. In `首尾帧`, upload only actual start/end frames. In reference mode, upload clean role-specific references such as protagonist anchor, scene/action reference, or motion video reference. Never assume a visual-text storyboard is a safe second image.
- When fixing bad output, first ask which uploaded image the video seems to obey. If it obeys the landscape, title, grid, or story card instead of the intended action, remove that asset from the upload set and regenerate a closer no-text action reference.
- Keep video size, aspect ratio, resolution, frame rate, total duration, and platform wrapper in upload/settings notes. Do not repeat them inside fenced copy-ready prompt bodies when the target video tool already has those controls.
- Validate image dimensions and existence before calling the visual package complete.

Character-style correction rules:

- If the user names a living artist or studio style, do not put that name in generation prompts. Translate the desired feeling into concrete traits.
- For a warm classic hand-drawn Japanese animated-film heroine, lock: rounded simple face, soft expressive eyes, small natural nose/mouth, unglamorous everyday hair, modest practical clothing, gentle curious expression, slightly imperfect hand-drawn proportions, watercolor rural/domestic atmosphere.
- When the user criticizes the `女主选择`, regenerate or propose a protagonist selection board before regenerating the video frames.
- Do not rely on a generic `young woman, East Asian, apron` description when the protagonist style is the core creative requirement.

## 9A. Fast Chinese Brief Workflow

Use this when the user gives a short Chinese request and wants a board quickly:

1. `new-spec --profile ... --language zh`
2. `inspect-brief` if you want to audit the inferred `subject`, `product`, `scene`, `mood`, and `focus_points`
3. `apply-brief` with the user's brief, and only add explicit `--subject`, `--product`, `--scene`, or `--mood` when the automatic inference is wrong
4. `attach-references` when protagonist images, first/last frames, or style references are available
5. Use `--panel` on `attach-references` when one anchor should affect only one shot, such as a collar detail or a product macro frame
6. `annotate-panel` for key shots that need explicit video handoff metadata
7. when source text exists, use `annotate-panel --source-panel --source-visual --story-beat --subtitle --voiceover --sound-design --binding-status` so the shot list stays paired with the writing
8. `render-sheet`
9. inspect whether Chinese captions and placeholder text still fit cleanly in the board

This fast path is especially useful for:

- `抖音秋装针织裙带货`
- `跳舞分镜，主角是银色上衣黑裤子女舞者`
- `只有首尾帧，帮我补中间动作`
- `唯美玄幻仙宫巨景，做首尾帧`
- `仙侠分镜图，巨树、云海、神殿、御剑飞升`

When `attach-references` is used, the spec should contain:

- `reference_inputs.global.face_anchors`
- `reference_inputs.global.outfit_anchors`
- `reference_inputs.global.product_anchors`
- `reference_inputs.global.scene_anchors`
- `reference_inputs.global.style_anchors`
- `reference_inputs.global.generic_references`
- `reference_inputs.global.first_frame`
- `reference_inputs.global.last_frame`
- `reference_inputs.panels.<index>` for panel-specific overrides

Downstream prompt packs should treat those as higher-priority constraints than the free-text brief alone.

### Reference Weight And Crop Priority

Every attached reference entry should carry:

- `weight`: influence strength from `0.0` to `1.0`
- `priority`: conflict order; higher wins before `weight` is considered
- `crop`: the intended crop or region to look at
- `focus`: what the model should extract from that crop
- `lock`: whether the anchor is hard identity/detail or soft style/scene

Default priorities:

| Anchor | Weight | Priority | Crop | Lock |
| --- | ---: | ---: | --- | --- |
| `first_frame` / `last_frame` | `1.0` | `110` | full frame | `hard-keyframe` |
| `face_anchors` | `1.0` | `100` | face close-up / 3:4 portrait crop | `hard-identity` |
| `product_anchors` | `0.95` | `90` | product/detail macro crop | `hard-detail` |
| `outfit_anchors` | `0.85` | `80` | full-body or garment crop | `hard-outfit` |
| `scene_anchors` | `0.65` | `55` | wide environment crop | `soft-scene` |
| `style_anchors` | `0.45` | `35` | style/color/mood crop | `soft-style` |
| `generic_references` | `0.35` | `20` | loose reference crop | `soft-inspiration` |

Conflict policy: resolve by `priority` first, then by `weight`. Face identity must not be rewritten by outfit or product references. Product/prop anchors only lock their local truth. Outfit anchors lock silhouette/materials. Scene and style anchors affect environment, mood, color, and lens language only.

Use separate `attach-references` calls when roles need different overrides. Use `--panel` for a one-shot override such as a sleeve, collar, logo, magic weapon, or close-up prop detail. Panel references merge over global references by path, so attaching the same path again with a higher priority updates that path's metadata for the panel scope.

## 9D. Xianxia Fantasy Workflow

Use `xianxia-fantasy-25` when the user asks for `唯美玄幻`, `仙侠`, `国风神话`, `东方幻想`, `山海经`, `仙宫`, `神殿`, `云海`, `巨树`, `御剑`, or similar epic fantasy scenes.

Minimum contract:

1. `world anchor`: temple/palace silhouette, sacred tree or mountain gate, cloud sea, primary light direction, magic color, and whether the world is heavenly, underwater, mountain, desert, or ancient-city based.
2. `protagonist anchor`: robed figure, immortal disciple, sword cultivator, goddess, monk, or no fixed hero yet.
3. `scale plan`: which panels make the protagonist tiny against the world and which panels provide readable emotion.
4. `motion plan`: walking, climbing steps, looking back, forming seals, drawing sword, flying on sword, ascension, or only a camera drift.
5. `endpoint plan`: if the user says `首尾帧`, decide whether the deliverable is two final image prompts, a 9-panel bridge, or a 25-panel board.

Default 25-panel xianxia layout:

1. immortal realm establishing shot
2. mountain gate entry
3. protagonist silhouette
4. palace low angle
5. sacred tree and god rays
6. spirit creatures crossing foreground
7. ascending steps
8. incense burner or talisman detail
9. sleeve and wind motion
10. lit profile
11. suspended bridge wide
12. spell formation wakes
13. water-mirror reflection
14. magic prop glows
15. gathered disciples or courtyard crowd
16. colossal temple doors open
17. clouds part
18. aerial realm reveal
19. emotional close-up
20. sword ascent or light-path rise
21. celestial waterfall or sky river
22. extreme wide scale pressure
23. hero wide frame
24. still look back
25. end-frame hold

Ask only when the missing answer changes the asset type. For example:

- If the user says `首尾帧`, ask whether they want two endpoint images or a bridge board unless their wording already implies one.
- If the user says `类似这张图`, treat the image as a style/scene reference, not as a fixed character, unless they explicitly ask to preserve the person or exact place.
- If the user wants a final video, ask or infer the downstream format: vertical 9:16 short video by default, horizontal cinematic only when requested.

## 9B. Video Handoff Schema

Every panel should expose a minimal video handoff object:

- `keyframe_role`
- `duration_sec`
- `camera_move`
- `transition_to_next`
- `motion_strength`
- `loop_safe`
- `shot_note`

Use `annotate-panel` for the shots that need explicit overrides. Keep these fields lightweight but real; they should be production hints, not decorative metadata.

## 9E. Text-Paired Shot Storyboards

Use this when the user says the storyboard should match previous text, script copy, narration, subtitles, sales copy, or scene writing.

Panel text fields:

- `source_panel`: original panel, beat id, or timecode, such as `V2#03`, `beat-03`, or `00:02-00:03`.
- `text_source`: where the line came from, such as `原文第1句`, `第2段`, `用户上一版旁白`, or `generated/original`.
- `source_visual`: the previous visual/caption text this shot must preserve.
- `story_beat`: the concise narrative information point this panel advances.
- `story_text`: the prior written line this panel must visualize, useful for simpler workflows.
- `subtitle`: exact subtitle line to add in editing.
- `voiceover`: exact voiceover or spoken line to record.
- `subtitle_voiceover`: combined subtitle/voiceover for simple workflows when the line is identical.
- `sound_design`: ambience, music, sound effect, or pause cue.
- `binding_status`: `source`, `derived`, `override`, or `generated/original`.

Rules:

- Build a text-to-shot map before inventing camera language.
- Do not treat `caption` as the source script; `caption` is a short visual summary for the board.
- Keep subtitles/voiceover as post-production instructions unless the user explicitly asks for text burned into the image.
- Split `subtitle` and `voiceover` when they differ; use `subtitle_voiceover` only when one line can serve both.
- Mark changed or newly written lines with `binding_status=derived`, `override`, or `generated/original` so the source does not get silently rewritten.
- If the source text has more beats than panels, merge adjacent beats intentionally and record the merged source range.
- If there is no source text but the user wants a complete shot storyboard, write short original lines and mark `text_source` as `generated/original`.
- Put text fields in exported prompt packs so image, video, editing, and dubbing steps all receive the same beat.
- Preserve `panels[].image` and export it beside text fields. A text-paired storyboard should never become text-only unless no visual has been generated yet.
- Keep copyable per-panel prompts compact, normally under 2000 Chinese characters. Move long explanations into Markdown notes instead of the actual image/video prompt.

## 9F. Continuous Single-Video Prompt

Use this when the user reports that a generated 10s video feels like separate stories, or when the target tool will generate one continuous 5-10s clip from a single prompt.

Rules:

- Do not paste a 10-panel shot list as ten one-second scenes.
- Do not start the copyable prompt with redundant tool settings when size/duration are already selected in the tool UI or written in the upload/settings note.
- Choose one continuous location and camera path. If the full board spans too much geography, start later or split into multiple clips.
- Compress 9-10 panels into 3-4 macro beats: setup, movement, incident, payoff.
- Reuse the same subject count, wardrobe, props, light direction, and environment throughout.
- Say explicitly: no hard cuts, no scene jumps, no slideshow, no separate vignettes.
- Use fewer references, not more. Prefer one start-frame reference and, only when the tool supports it, one end-frame reference. Do not upload a full contact sheet or 10 separate panel images for a single continuous generation.
- For Seedance/Doubao, write prompt structure as narrow role bindings followed by a few ordered beats. Good bindings look like: `图1只锁主体/视角`, `图2只锁动作参考`, `图3只锁终点画面`. If a board is human review only, write that outside the prompt or explicitly say it must not be inherited.
- Put the intended subject action at the start of the clip. If the desired result is "playing/swimming/interacting", the first 1-2 seconds must already show that action beginning; do not spend the first third of the clip only revealing the landscape.
- Keep the copyable generation prompt practical, preferably under 2000 Chinese characters unless the target tool reliably accepts longer prompts.
- If the user says the first generated video feels like "10 stories", treat that as a continuity failure: remove scene changes, remove one-second shot labels, and rewrite the whole request as one route through one space.
- If the board needs a large location change, recommend two 5s clips or per-shot generation and editing instead of one 10s generation.
- If the user wants actual visuals, create a clean start-frame image for the continuous clip. A no-text storyboard board may be included for human review, but the prompt handoff should tell the user to upload the start frame, not the board, for one continuous generation.
- If the user wants `图文`, include a visual+text card as a separate human-review artifact. The video handoff should still use clean no-text start/end frames.

Prompt structure:

```text
One continuous video, not ten separate shots.
Single spatial geography: [same room/corridor/bridge/temple path].
Same characters and locked props: [identity/costume/objects].
0-2s: [setup in same space].
2-5s: [continuous movement].
5-8s: [incident escalates without cutting away].
8-10s: [payoff/end hold in same geography].
Continuity constraints: [no jumps, no costume change, no new location].
Negative constraints: [no text, no watermarks, no IP, no hard cuts].
```

Reference handoff pattern:

```text
For one continuous 10s generation, upload only:
start frame: [one image path]
optional end frame: [one image path, only if supported]
optional character anchor: [one image path]
Do not upload the text-heavy storyboard board. Do not upload all 10 panels at once.
Put size/aspect/duration in the tool settings or upload note, not inside the prompt body.
```

Bad-output repair checklist:

1. Extract frames or inspect the result.
2. Identify whether the strongest motion is the camera, the environment, or the subject.
3. If the subject is passive, rewrite the first beat around concrete physical action: reach, grab, push, paddle, lift, turn, step, splash, collide, recoil, or settle.
4. Remove image references whose visual form is not supposed to appear in the final video, especially text boards, grids, contact sheets, UI screenshots, route maps, and title cards.
5. Generate or choose one clean reference whose composition already contains the desired action relationship.
6. Use 3-4 macro beats for one continuous 10s clip; use "镜头1/镜头2/镜头3" only when intentionally allowing shot boundaries.

If the user insists on feeding a visual-text storyboard to the video model:

- Create an `AI-facing visual-text action board`, not a decorative director board.
- Use 16-25 sampled action cells for a 5-10s clip. Each cell is an action sample, not a hard cut.
- Keep labels short and verb-led: time + action + camera/environment cue.
- Avoid long paragraphs, slogans, large titles, heavy tables, route maps, UI chrome, and dense captions.
- Pair the board with a copyable text prompt that says the model should read action order and ignore text/number/border/grid as visual elements.
- A/B test against clean references; if text/grid leaks into output, demote the visual-text board to human review only and keep its exact beats in the text prompt.

## 9G. Hierarchical Macro-Story Package

Use this when the user says the video should be longer than one clip, such as `10个大镜头`, `每镜10秒`, `100秒故事`, `一镜对应一个图文故事版`, or when the user complains that a dense board makes each image too small.

Output levels:

- `Macro overview`: one readable board with 10 big beats across the full story. Each macro beat has a timecode, title, large visual anchor, story purpose, and transition into the next beat.
- `Episode story cards`: one large card per macro beat. Each card expands that big beat into one continuous 10s clip with 0-2s setup, 2-5s movement, 5-8s incident, and 8-10s end hold.
- `Episode prompts`: one copyable prompt per clip. Do not combine all 10 prompts into one generation task, and keep video size/aspect/duration outside the fenced prompt body unless the user explicitly wants an all-in-one prompt.
- `Index/readme`: tells the user which board is for review, which prompt is for generation, and which references to upload.
- `Copy-ready Markdown`: one fenced `text` code block per episode. Put reference image paths before the block, not inside it, so users can copy the real prompt without cleanup.

Continuity rules:

- The 100s story should have one global objective, one protagonist group, and one world logic.
- Macro beats may change location, but only through explicit transitions: descend, enter, cross, trigger, retreat, reveal, choose, escape, or hold.
- Each 10s episode must be continuous inside itself. Do not make each episode a new 10-shot montage.
- The end state of episode N should be the start state of episode N+1.
- If a single board becomes unreadable, split into more boards rather than shrinking text or thumbnails.
- For ordinary or foreign-tested prompts, keep the prompt body structured with short labels such as `定位`, `人物锁定`, `承接上一集`, `时间节拍`, `镜头要求`, `视觉风格`, and `禁忌`. Put upload/settings metadata before the code block. For domestic Chinese video-model testing, use section 9H and replace this with `正向画面约束`.
- Keep clean episode prompts around 800-1200 Chinese characters when possible; if a raw machine TXT is kept, also provide a cleaner human-copy version.

Recommended sizes:

- Overview board: at least 3000px wide for 10 macro beats.
- Episode card: at least 1800px wide and 3000px tall for phone-friendly reading.
- Avoid putting 100 sub-beats on one image unless it is only a map, not a production board.

## 9H. Domestic Chinese Video-Model Safe Prompts

Use this only for domestic Chinese video-generation testing when the user mentions platform filtering, hidden sensitive words, or asks for a domestic-safe pack. Do not rewrite the original or foreign-tested prompts; create a separate `domestic-safe` package or clearly named domestic copy.

Domestic prompt bodies should be positive-only. Replace the negative section label `禁忌` with `正向画面约束`, and phrase constraints as what the model should keep: clean frame, stable identity, continuous camera path, safe publishable atmosphere, natural light/shadow, original exploration team, stone structure, water ripples, mechanism glow, and character reactions.

Use the bundled heuristic lexicon at `assets/domestic-video-safe-lexicon.json` for this project's current tomb/exploration examples. Typical rewrites include using `地下入口` or `深坑入口` instead of old-well wording, `荒原旧址` or `风化院落` instead of abandoned-village wording, `暗色水面` instead of dark-water wording, `古灯` instead of bone-lamp wording, and `原创兽纹/大幅光影` instead of dragon-shadow wording. Remove gore or body references entirely; replace them with traces, mineral marks, weathered cloth, mechanism light, or abstract shadow when a beat needs atmosphere.

Run the scanner before handoff:

```powershell
python skills/short-video-storyboard/scripts/storyboard_cli.py scan-domestic-safety --path D:\path\to\domestic-safe
```

## 9C. Prompt-Pack Export

Use `export-prompts` when the storyboard is ready to feed image or video generation.

Default outputs:

- `panel-prompts/panel-01.txt` through `panel-prompts/panel-25.txt`
- `group-prompts/group-01.txt` and later groups based on `--group-size`
- `panels.jsonl`
- `panels.csv`
- `groups.json`
- `video-handoff.json`

Expected use:

1. per-panel prompts for the most controlled generation path
2. grouped prompts for row-based or beat-based batch generation
3. JSONL/CSV for external scripts, spreadsheets, or automation tools
4. video handoff export for downstream image-to-video systems, including the combined reference scope for each panel
5. image paths plus text fields for visual continuity, subtitle/voiceover, sound design, and source-beat continuity

## 10. Choose A Video Tool Family

Use the dated notes in `references/research.md`, then re-check official docs when exact capabilities matter.

General guidance:

- `OpenAI Sora`: useful when you want storyboard-like sequencing inside one creation workflow.
- `Runway Gen-4`: useful when character, object, and location consistency across shots matters.
- `Luma Ray 2/3`: useful when you want keyframes, character reference, or camera-motion controls.
- `StoryDiffusion`: useful for still-image sequences, comic/storyboard consistency, and character locking in images.
- `ToonCrafter`: useful for local start/end interpolation between keyframes.
- `FramePack`: useful for local consumer-GPU video experiments.
- `Jellyfish`: useful as an architecture reference for modular storyboard-to-video pipelines.

## 11. Render And Review

Always check:

1. Does the first row communicate the hook?
2. Does the middle communicate the main motion or selling proof?
3. Does the last row give a usable payoff or CTA?
4. Is the protagonist still the same person?
5. Is the product still the same product?
6. Would a video model understand the motion path from the chosen key beats?
