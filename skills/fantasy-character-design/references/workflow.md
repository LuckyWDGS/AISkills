# Fantasy Character Design Workflow

## 1. Classify The Request

Use this skill when the user asks for a fantasy character source asset:

| User asks for | Use this skill? | Output |
| --- | --- | --- |
| `角色设定图`, `人物设定板`, `神女设定`, `女帝设定图` | Yes | Character design sheet |
| `三视图`, `转面图`, `正侧背`, `服装设定` | Yes | Turnaround and costume sheet |
| `眼睛/法器/鞋履/布料细节` | Yes | Detail prompt pack |
| `先锁角色，再做首尾帧/分镜` | Yes first | Handoff pack for storyboard |
| `首尾帧`, `25格分镜`, `镜头拆解` | No, use `short-video-storyboard` | Video planning |

If the user says only `做类似这张图`, ask whether they want a character design sheet or video frames/storyboard, because the workflows diverge.

## 2. Minimum Input Contract

The minimum viable prompt is:

1. `character_name`: e.g. `牡丹仙子`
2. `archetype`: e.g. flower spirit, empress, star deity
3. `key visual elements`: colors, hair, costume, prop, materials, mood

Optional but strongly helpful:

- reference images for face, costume, pose, prop, or style
- whether Chinese labels are needed
- output ratio, usually tall portrait
- whether this must later drive first/last frames, storyboards, or video consistency

## 3. Build A Character Before A Board

Do not start with one giant image prompt. Build these locks first:

1. `Identity lock`: face, hair, expression, age impression, body proportion
2. `Costume lock`: silhouette, neckline, sleeves, skirt/train, transparency, armor/jewelry
3. `Material lock`: silk, gauze, crystal, jade, metal, petals, particles
4. `Prop lock`: weapon, magic circle, flower, orb, fan, deity emblem
5. `Palette lock`: main color, secondary color, light color, metal color, shadow color
6. `Avoid lock`: text artifacts, extra characters, modern objects, costume drift

## 4. Production Strategy

For fast concept approval:

1. Seed a template.
2. Apply the user brief.
3. Render a placeholder board.
4. Export full-board prompt.
5. Generate one complete character design sheet with `$cm-imagegen`.

For production reliability:

1. Generate the hero full-body art first.
2. Use the accepted hero as identity/costume/style anchor.
3. Generate turnarounds and details as separate images.
4. Assemble the final board with readable text in layout/post-processing.
5. Export handoff prompts for start/end frames and storyboard work.

## 5. Text Handling

Do not rely on image models for small Chinese labels. They often produce incorrect glyphs or decorative pseudo-text.

Preferred flow:

1. Generate no-text art panels.
2. Use the script or a design/layout tool to add Chinese labels, dimensions, palette names, and notes.
3. Keep the source spec as the copy source of truth.

## 6. Reference Roles

Label references by role:

- `face_anchors`: identity and face structure
- `costume_anchors`: clothing silhouette, fabric, accessories
- `prop_anchors`: weapon, magic circle, flower, orb, device
- `style_anchors`: board style, lighting, rendering finish
- `generic_references`: loose inspiration only

Do not treat a style reference as a fixed identity reference unless the user explicitly says so.

## 7. Reference Weight And Crop Priority

Every reference entry should carry this shared metadata:

- `weight`: influence strength from `0.0` to `1.0`
- `priority`: conflict order; higher wins before `weight` is considered
- `crop`: the intended crop or region to look at
- `focus`: what the model should extract from that crop
- `lock`: whether this is hard identity/costume/prop detail or soft style inspiration

Default priorities:

| Anchor | Weight | Priority | Crop | Lock |
| --- | ---: | ---: | --- | --- |
| `face_anchors` | `1.0` | `100` | face close-up / 3:4 portrait crop | `hard-identity` |
| `prop_anchors` | `0.95` | `90` | prop or magic-device detail crop | `hard-prop-detail` |
| `costume_anchors` | `0.88` | `82` | full-body costume or garment-detail crop | `hard-costume` |
| `style_anchors` | `0.45` | `35` | style/color/layout crop | `soft-style` |
| `generic_references` | `0.35` | `20` | loose reference crop | `soft-inspiration` |

Conflict policy: resolve by `priority` first, then by `weight`. Face anchors do not rewrite costume or prop design; costume anchors lock silhouette/material/accessories; prop anchors lock only the local object or magic motif; style anchors only affect finish, color, lighting, and board mood.

Use separate `attach-references` calls when different roles need different overrides. If a source image contains several useful regions, prepare or attach separate crops for face, costume, prop, and style instead of relying on one mixed reference.

## 8. Handoff To Storyboard

When the user wants video next:

1. Export prompts from this skill.
2. Generate or select hero/turnaround/detail images.
3. Feed accepted images into `short-video-storyboard` as face, outfit, product/prop, scene, or style anchors.
4. Let the storyboard skill handle shot order, start/end frame motion, duration, camera moves, and video handoff.
