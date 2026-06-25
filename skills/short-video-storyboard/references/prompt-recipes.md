# Prompt Recipes

## 1. Master Prompt Blocks

Build prompts from reusable blocks instead of rewriting the whole style every time.

### Global Lock

```text
Same protagonist across all panels: [identity summary].
Same wardrobe or product truth across all panels: [garment / product summary].
Visual language: [editorial / livestream / dreamy / kinetic].
Lighting: [soft studio / rim-light / neon / ethereal haze].
Lens family: [24mm wide / 50mm natural / 85mm portrait].
Platform intent: [Douyin/TikTok vertical short-video storyboard].
```

### Sequence Lock

```text
Only change pose, camera distance, and motion beat from panel to panel.
Do not change face identity, hairstyle, body type, core outfit, product colorway, or room family.
Keep panel borders clean. No speech bubbles. No extra text inside panels.
```

### Text Lock

```text
Text-to-shot continuity:
source panel/beat: [V2#03 / 原文第几句 / timecode].
source visual text: [previous visual/caption text to preserve].
story beat this panel visualizes: [what the writing says or implies].
subtitle for editing only: [exact subtitle line].
voiceover for recording: [exact spoken line].
sound atmosphere: [ambience, music, SFX, silence].
binding status: [source / derived / override / generated-original].
Do not render subtitles or UI text inside the image unless explicitly requested.
```

### Reference Strategy

```text
Reference weight and crop strategy:
face anchors: P100, W1.0, crop=face close-up / 3:4 portrait crop, focus=identity and expression, lock=hard-identity.
product anchors: P90, W0.95, crop=product/detail macro crop, focus=truthful logo/seam/texture/shape, lock=hard-detail.
outfit anchors: P80, W0.85, crop=full-body or garment crop, focus=silhouette/material/accessories, lock=hard-outfit.
scene/style anchors stay soft and must not rewrite face, product, or outfit details.
Conflict policy: priority first, then weight.
```

### Panel Block

```text
Panel [number]: [shot size], [camera angle], [pose/action], [expression], [product emphasis], [motion cue].
```

### Negative Block

```text
Avoid character drift, extra limbs, duplicated props, wrong logos, unreadable text, deformed hands, inconsistent garment length, random background swaps.
```

### Domestic Positive Block

Use only for domestic Chinese video-generation model tests. Keep the original or foreign-tested prompt pack unchanged, then create a separate domestic-safe variant.

```text
正向画面约束：画面聚焦同一主角/队伍、同一空间路径、同一服装道具、稳定光线方向、干净画面、连续动作、自然转场、发布友好的氛围和清晰主体。
```

For domestic tomb/exploration prompts, scan and rewrite with `assets/domestic-video-safe-lexicon.json`. Prefer neutral positive scene words such as `地下入口`, `深坑入口`, `荒原旧址`, `风化院落`, `暗色水面`, `古灯`, `原创兽纹`, and `大幅光影`. Remove gore/body wording entirely and express tension through stone texture, dust, water ripples, mechanism glow, and character reactions.

## 2. One-Shot 25-Panel Concept Board Prompt

Use this only for fast ideation:

```text
Create one polished 5x5 storyboard contact sheet for a vertical short-video campaign.
Same female fashion host across all 25 panels, same face identity, same black wavy hair, same white cropped jacket and flowing silver skirt, same elegant high heels.
The board shows a Douyin-style apparel showcase with energetic host charisma, product truth, pose variation, dance-like motion, fabric movement, close detail shots, and a strong CTA ending.
Each panel is visually distinct but consistent, with clean borders, cinematic composition, and no interior text.
Premium editorial photography look, natural skin, realistic clothing folds, rich motion, bright luxury studio lighting.
```

## 3. Dance Board Prompt

### Full Board

```text
Generate a 25-panel dance storyboard sheet, 5 columns by 5 rows.
Same protagonist in every panel: athletic young woman, oval face, long ponytail, sharp jawline, expressive eyes, confident smile, same silver crop top, same black cargo pants, same white sneakers.
Sequence shows one continuous pop-dance routine from hook pose to landing pose.
Panels should cover front, side, low-angle, close-up, footwork insert, spin, landing, and loop reset.
Keep the same dance studio environment, same lighting family, same outfit, same body proportions.
No speech bubbles, no captions, no extra props, no character drift.
```

### Per-Panel

```text
Same protagonist as the locked dance anchor.
Panel 07. Tight insert on footwork, one foot sliding diagonally, sneaker sole visible, dynamic floor reflection, kinetic motion blur, same studio, same outfit.
```

## 4. Douyin/TikTok Fashion Commerce Prompt

### Full Board

```text
Generate a 25-panel fashion-commerce storyboard sheet for a Douyin vertical short video.
Same female host in every panel, same facial identity, same hairstyle, same cream knit dress, same belt, same boots.
The board must prove fit, texture, movement, front view, side view, back view, styling variations, and final CTA energy.
Make the product look truthful and wearable. Do not change garment length, neckline, sleeve length, or color.
Luxurious but social-friendly, like a premium short-video seller shoot.
```

### Detail Panel

```text
Same commerce protagonist and same cream knit dress.
Panel 09. Close shot of sleeve texture and stitch detail, hand lightly lifting the cuff, soft luxury lighting, product realism, sharp textile detail.
```

## 5. Dreamy Cinematic Prompt

```text
Create a 25-panel dreamy fantasy storyboard sheet.
Same protagonist throughout the sequence: ethereal young woman, pale gold dress, loose dark hair, translucent shawl.
One continuous emotional arc in a moonlit reflective hall with haze, particles, flowing fabric, mirrored highlights, and soft halo light.
Use gliding camera language and preserve the same visual world across all panels.
No random costume changes and no unrelated props.
```

## 6. Xianxia Fantasy Prompt

### Full Board

```text
Create a 25-panel xianxia / Chinese fantasy storyboard sheet for a vertical image-to-video short.
Same protagonist across all panels: an immortal robed figure with the same face, hairstyle, costume silhouette, weapon or magic prop, and body proportions.
Same world logic across all panels: monumental Chinese fantasy palace architecture, cloud sea, sacred tree or mountain gate, gold-blue god rays, mist, particles, and mythic scale.
The sequence moves from world reveal to mountain gate entry, protagonist silhouette, palace and sacred-tree spectacle, spell formation, emotional close-up, sword ascent, and stable end frame.
Preserve palace layout, light direction, magic color, costume, and scale continuity.
No random modern buildings, no sci-fi armor, no extra text, no costume drift, no inconsistent temple style.
```

### Chinese Full Board

```text
生成一张25格唯美玄幻仙侠分镜图，竖屏短视频预生产用途。
同一位仙侠主角贯穿所有格子：同一张脸、同一发型、同一套长袍服装、同一件法器或长剑、同一身形比例。
同一个国风玄幻世界贯穿所有格子：仙宫殿宇、云海群山、通天巨树或山门、金青色神光、雾气、花瓣/灵粒子、史诗尺度。
镜头顺序从仙域建立、山门入境、主角背影、宫阙仰拍、巨树天光、阵法启动、情绪近景、御剑升空，到稳定尾帧。
保持宫殿布局、光线方向、法术颜色、服装廓形和人物尺度连续一致。
不要现代建筑，不要科幻盔甲，不要画面内文字，不要换服装，不要随机改成别的神殿风格。
```

### Chinese Text-Paired Shot Board

```text
根据上一版文字生成镜头分镜，每一镜必须绑定原文/旁白/字幕/声音：
第[number]镜：来源格=[V2#03或原文第几句]；原始画面文字=[上一版画面栏/文案]；剧情节拍=[这一镜推进的信息点]；字幕=[后期叠加，不要生成在画面里]；旁白=[配音/口播准确句子]；声音氛围=[环境声/音乐/SFX]；绑定状态=[source/derived/override/generated-original]；镜头目标=[景别、角度、动作、情绪、道具、运镜]。
所有生图提示词必须继承同一全局视觉锁定，并把文字承接写成剧情提示，不要把字幕画进图片。
```

### Start/End Frame Pair

```text
首帧：极广角国风玄幻仙宫巨景，主角站在山门石阶下方，远处通天巨树与宫阙被云雾和金青色神光包围，人物很小但轮廓清楚，适合图生视频起始帧。
尾帧：同一主角御剑或踏光升至仙宫前方，巨树、宫阙、云海和神光保持同一世界逻辑，构图稳定留白，适合图生视频结束帧。
桥接说明：保持同一服装、同一法器、同一场景地理关系和同一光线方向；中间动作只推进登阶、结印、光阵启动和升空，不随机换场景。
```

## 7. Start/End Frame Bridge Prompt

Use this when the tool accepts text with start and end frames or when you are planning the bridge manually.

```text
We already have the first and last frame of the same protagonist in the same room.
Plan the motion bridge as 9 storyboard beats.
Keep the same identity, costume, and environment.
The action is a smooth half-turn, hand lift, smile reveal, and forward step.
Insert anticipation, midpoint, and settle beats so the movement feels complete.
```

## 8. Continuous 5-10s Video Prompt

Use this when a single video generation should feel like one event instead of a storyboard slideshow.

Upload/settings note, outside the copyable prompt:

```text
视频比例/尺寸/总时长：按目标工具设置或用户指定；不要把这类工具设置重复进下面的提示词正文。
参考图：上传一张首帧或主体锚点；工具支持首尾帧时再上传尾帧。
```

```text
一镜到底或最多一次自然遮挡转场。不要做多镜头混剪，不要每秒换场景，不要像 10 张图轮播。全片发生在同一个连续空间：[从哪里开始] -> [沿什么路线移动] -> [在哪里停住]。

同一主角/队伍始终一致：[身份、服装、道具、人数]。同一视觉系统：[光线、色彩、材质、世界观]。不要换脸、换衣服、换队伍、换道具。

0-2 秒：[同一空间中的起始动作，不重新讲大背景]。
2-5 秒：[沿同一路线连续移动，环境自然展开]。
5-8 秒：[一个事件升级，不能切到新地点]。
8-10 秒：[停在稳定尾帧，可接下一段]。

连续性要求：同一地点、同一镜头路径、同一光线方向、同一人物数量；只推进一个动作链。禁忌：硬切、跳场景、字幕文字、水印、logo、人物漂移、服装漂移、道具漂移、重复人物、畸形手脚。
```

Domestic-safe continuous-video variant:

```text
一镜到底或自然遮挡转场。全片发生在同一个连续空间：[从哪里开始] -> [沿什么路线移动] -> [在哪里停住]。

同一主角/队伍始终一致：[身份、服装、道具、人数]。同一视觉系统：[光线、色彩、材质、世界观]。画面保持稳定身份、稳定服装、稳定队伍和稳定道具。

0-2 秒：[同一空间中的起始动作]。
2-5 秒：[沿同一路线连续移动，环境自然展开]。
5-8 秒：[一个事件升级，仍在同一地点]。
8-10 秒：[停在稳定尾帧，可接下一段]。

正向画面约束：同一地点、同一镜头路径、同一光线方向、同一人物数量；只推进一个动作链；画面干净，主体清晰，动作连贯，发布友好。
```

Reference rule for continuous video:

```text
只上传一张首帧参考；工具支持首尾帧时再上传一张尾帧。不要上传图文同屏板，不要一次上传 10 张分镜图。
```

### Visual Start Frame Prompt

Use when the user says the package needs real images:

```text
Create a clean start-frame illustration for an original [style family] short video. Use the target aspect/size from the upload settings, not from this prompt body.
Same protagonist: [identity, hair, wardrobe, expression].
Scene: [one continuous location with key props].
Action state: [what the protagonist is doing at the first moment of the video].
Visual language: [lighting, palette, texture, lens mood].
This is a video start frame, not a poster and not a text card.
No text, no captions, no logo, no watermark, no brand packaging, no existing characters, no deformed hands.
```

### Safe Warm Hand-Drawn Heroine Substitute

Use when the user asks for a Miyazaki-like feeling. Do not name the artist or studio in the generation prompt.

```text
Original classic warm hand-drawn Japanese animated-film heroine, not based on any existing character or studio.
Rounded simple face, soft expressive eyes, small natural nose and mouth, gentle curious expression, modest practical rural clothing, slightly wind-tousled dark hair, wholesome everyday charm, natural posture rather than fashion-model posing.
Hand-painted watercolor background, warm natural light, cozy domestic detail, subtle paper grain, soft linework, quiet wonder, no glamour makeup, no glossy idol look, no 3D render look, no live-action realism.
```

### Protagonist Selection Board Prompt

Use before video frames when the user has not provided a protagonist and the heroine's style is important:

```text
Create a 4-option protagonist selection sheet for an original warm hand-drawn animated short.
Each option shows the same general role [role], but with different face/hair/personality silhouettes.
Style direction: [safe translated style traits].
Show bust portrait, full-body simple outfit, and one small cooking/holding-prop pose per option.
No text, no labels, no existing characters, no studio imitation, no logos, no watermark.
```

### No-Text Visual Storyboard Board Prompt

Use for human review, not as the primary reference for one continuous video:

```text
Create a polished [4/5/9]-panel vertical storyboard sheet with real illustrated panels.
No text anywhere, no captions, no labels.
Same protagonist across all panels: [identity lock].
Same location and visual system across all panels: [scene lock].
Panel 1: [setup].
Panel 2: [movement].
Panel 3: [incident].
Panel 4: [payoff / end hold].
Keep face, outfit, props, light direction, room layout, and color palette consistent.
No text, no logos, no watermark, no character drift, no random background swaps.
```

### Visual+Text Shot Card Layout

Use when the user asks for `图文镜头`, `图文故事版`, or wants each shot to include text:

```text
Layout artifact, not an image-generation prompt:
- Top or left: real generated visual panel or no-text storyboard crop.
- Beside or below each panel: real rendered text with timecode, shot title, action, camera, subtitle/voiceover, and sound cue.
- Use local fonts/PIL or the storyboard renderer for Chinese text; do not rely on image generation to write readable Chinese.
- Keep a clean no-text start frame separately for video generation.
```

## 9. Hierarchical 100s Story Prompt

Use this when the user wants 10 big shots and each big shot becomes one continuous 10-second clip.

```text
请把故事拆成两层分镜，不要塞成一张100格小图。
第一层：10个大镜头，总时长约100秒，每个大镜头负责一个清楚的剧情阶段，并写清楚它如何过渡到下一个大镜头。
第二层：每个大镜头单独扩写成一张图文故事版，作为一个连续10秒视频。每集只保留同一空间里的一个动作链，拆成0-2秒、2-5秒、5-8秒、8-10秒四个连续节拍。

全局锁定：[主角/队伍/服装/道具/世界观/色彩/光线]。
100秒主线：[一句话说明故事目标]。
每个大镜头输出：编号、时间码、标题、画面锚点、剧情目的、承接上一镜、引出下一镜、10秒连续视频提示词、禁忌。
不要把10个大镜头的提示词合并给一个视频任务；每个大镜头单独生成10秒，再剪辑成100秒。
```

Domestic-safe adjustment:

```text
如果用于国内生成视频模型测试，另存为 domestic-safe 包。每个大镜头输出字段改为：编号、时间码、标题、画面锚点、剧情目的、承接上一镜、引出下一镜、10秒连续视频提示词、正向画面约束。提示词正文只写模型应该保持和聚焦的内容，不写负面提示词。
```

Copy-ready episode format:

````markdown
## 第[number]集 [title]

上传参考图：
- 本集画面锚点：[path]
- 角色锚点：[path]

视频设置：
- 比例/尺寸/总时长在目标工具 UI 中选择；下面代码块只保留模型需要理解的画面与动作。

```text
定位：[belongs to which 100s segment].
人物锁定：[same characters].
承接上一集：[previous state].
本集目标：[story objective].
引出下一集：[next hook].
时间节拍：
0-2秒：[setup]
2-5秒：[movement]
5-8秒：[incident]
8-10秒：[end hold]
镜头要求：[continuous camera path].
视觉风格：[style lock].
禁忌：[negative constraints].
```
````

Domestic copy-ready episode format:

````markdown
## 第[number]集 [title]

上传参考图：
- 本集画面锚点：[path]
- 角色锚点：[path]

视频设置：
- 比例/尺寸/总时长在目标工具 UI 中选择；下面代码块只保留模型需要理解的画面与动作。

```text
定位：[belongs to which 100s segment].
人物锁定：[same characters].
承接上一集：[previous state].
本集目标：[story objective].
引出下一集：[next hook].
时间节拍：
0-2秒：[setup]
2-5秒：[movement]
5-8秒：[incident]
8-10秒：[end hold]
镜头要求：[continuous camera path].
视觉风格：[style lock].
平台适配：镜头语言温和克制，视觉元素以自然光影、人物行动、空间探索和机关微光为主，整体呈现安全、纯净、连贯、可发布的短视频质感。
正向画面约束：[positive visual constraints].
```
````

## 10. Prompt Assembly Pattern For User-Provided Protagonists

When the user supplies reference photos, add this block near the start:

```text
Use the provided reference images as the identity anchor for the same protagonist across all panels.
Preserve facial structure, eye distance, nose shape, lip shape, hairstyle silhouette, and body proportions.
```

For product-heavy use cases, add this block:

```text
Treat the garment as a truth-locked product. Preserve neckline, sleeve length, hemline, logo placement, seam placement, fabric category, and colorway across every panel.
```
