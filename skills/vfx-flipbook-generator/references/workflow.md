# Flipbook Workflow

## 1. Goal

Use this workflow when the user wants a reusable flipbook atlas for VFX work and the source situation is not trivial.

Typical requests:

- `把这个视频做成 12x12 flipbook`
- `素材太短，帮我补成能用的 smoke atlas`
- `没有现成火焰素材，用 cm 生一套 flipbook`
- `帮我根据搜索参考做 dust / ember / fire 的 SubUV 图`

## 2. Route Decision

Think in terms of `source samples / requested cells`.

- `>= 1.05` and the effect is soft:
  - direct extraction is usually acceptable
- `0.75 - 1.05`:
  - hybrid is usually safer
- `< 0.75`:
  - full generation or a smaller atlas is usually better

Soft effects:

- dust
- powder
- mist
- soft smoke
- haze

Sensitive effects:

- hero fire
- flame tongues
- plasma
- energetic magic
- anything with strong internal turbulence or fast silhouette change

Sensitive effects expose frame starvation sooner.

## 3. Search Policy

Search when:

- the user explicitly asks for web/network search
- the source footage is too short and motion language is unclear
- the user wants a specific real-world phenomenon but only gave a vague description

Use search to gather:

- motion direction
- breakup pattern
- density curve
- timing
- lifespan
- silhouette family

Do not use search to rip a stock atlas verbatim.

Prefer:

- motion/reference images
- side-view or orthographic-looking examples
- effect breakdowns
- alpha/video reference previews

## 4. Hybrid Route

Use hybrid when there is real motion worth keeping but not enough usable frames.

Good hybrid patterns:

1. extract the best source clip
2. identify missing phases
3. generate only those phases or bridge states
4. mix source-derived and generated frames into one curated frame folder
5. pack the atlas

Common examples:

- dust source has nice initial breakup but weak tail:
  - keep the first half from source
  - generate softer late linger states
- smoke source has good mid plume but weak birth:
  - generate early seed states
  - keep the real rise and bloom
- fire source is sharp but too short:
  - generate additional internal turbulence states instead of just slowing the same clip

Local direct-extract tool:

- `python D:/Skills/skills/vfx-flipbook-generator/tools/flipbook_builder.py recommend D:/clip.mov`
- `python D:/Skills/skills/vfx-flipbook-generator/tools/flipbook_builder.py build D:/clip.mov --grid 12x12 --fit contain --atlas-size-mode pad-to-power-of-two`
- the tool looks for `ffmpeg.exe` and `ffprobe.exe` under `D:/Skills/skills/vfx-flipbook-generator/tools/ffmpeg` before checking system `PATH`
- `contain` preserves the entire frame and pads when aspect ratios differ; `cover` crops to fill the cell and should only be used intentionally

## 5. Full-Generated Route

Use full-generated when:

- there is no usable source
- the style is too custom for stock footage
- source timing is incompatible with the requested effect
- the user wants a stylized or game-specific look

Before committing to a strict ordered sequence, check `references/sequence-boundaries.md`.
Some requested effects are better as randomizable sprite sets or mixed hero/support layers than as one fully continuous 100-frame atlas.

Full-generated sequence advice:

1. define a canonical canvas
2. define fixed framing
3. define the state ladder
4. generate anchor states first
5. reject drift before scaling up
6. write a per-frame batch plan before firing the image provider at scale
7. fill the sequence
8. pack and QC

For one-shot generated atlas previews, still finish with a production snap:

- use a black luminance-style background when matching common smoke/dust flipbook textures
- remove checkerboard preview backgrounds before accepting the asset
- force the final atlas to a power-of-two square and prefer `2048x2048` or `4096x4096` as the source-delivery size when budget permits
- treat `1024x1024` as a chat/review/mobile-low-budget derivative unless the user explicitly accepts it as final
- keep a raw generated copy when resizing or snapping the preview output
- if an alpha material route is needed, derive a separate alpha PNG from the black-background luminance map or regenerate through a true alpha-capable path

Note: a `10x10` grid cannot divide `1024x1024`, `2048x2048`, or `4096x4096` into integer-pixel cells. Treat `10x10 @ power-of-two square` as a review/sample format, not default final UE/Niagara SubUV delivery. For direct UE SubUV production output, prefer `8x8`, `16x8`, `16x16`, or another grid whose rows and columns divide the atlas dimensions exactly.

Recommended planning step after `flipbook_job_scaffold.py`:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_batch_plan.py D:/path/to/job-spec.json --prompt-suffix "gravity-driven downward motion, no environment"
```

This writes:

- `frame-plan.json`
- `system-imagegen-guide.md`
- `generate-frames-cm.ps1`
- `run-phases.ps1`
- `batch-plan-summary.md`

Recommended execution step after `flipbook_batch_plan.py`:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_batch_runner.py status D:/path/to/frame-plan.json
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_batch_runner.py run D:/path/to/frame-plan.json
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_batch_runner.py approve-anchor D:/path/to/frame-plan.json --phase 1
```

Runner behavior:

- default provider mode is `system-imagegen`
- in default mode, `run` emits the next manual system-imagegen step or phase packet instead of calling a local CLI automatically
- import accepted outputs back into runner state with `import-frame`
- after anchor approval, the next `run` fills the rest of that phase
- fill frames prefer image-reference `edit` after an anchor is accepted
- if a local CLI automation route is explicitly needed, switch the runner to `--provider cm-imagegen`

Typical state ladders:

- dust:
  - seed
  - thin streak
  - denser column
  - bloom
  - disperse
  - faint tail
- smoke:
  - ignition
  - rise
  - curl
  - plume body
  - diffuse
  - thin fade
- fire:
  - ignition tip
  - rising tongue
  - split tongues
  - bright core
  - torn edge
  - collapse/fade

## 6. QC Checklist

- Same canvas on every frame
- Same background policy on every frame
- Final atlas dimensions are power-of-two when the asset is destined for Unreal/Niagara
- Final production source is preferably `2048x2048` or `4096x4096`; `1024x1024` is intentionally marked preview, mobile-only, or low-budget when used
- Atlas dimensions divide evenly by the requested columns and rows when it is destined for direct Unreal/Niagara SubUV playback
- Black-background luminance atlases should look like real alpha masks, not transparent checkerboard previews
- Same effect family across the sequence
- No random extra particles that appear in only one frame unless intentional
- No frame-to-frame scale popping
- No accidental cutoffs from `cover`
- No suspicious transparent bands unless `contain` padding was intentional
- Prefer padding to power-of-two atlas size instead of scaling the whole atlas when raw dimensions are close but not exact
- Final atlas dimensions reported
- Whether the delivered atlas is native high-resolution generation, repacked high-resolution frames, or an upscale derivative reported
- Raw pre-snap dimensions reported when snapped
- Exact cell size reported when the grid divides the atlas
- Blank/unused cells excluded from Niagara end-frame playback unless they are intentional fade or hold cells
- Edge contact checked so important alpha/luma is not clipped or bleeding into adjacent cells
- Run `scripts/ue_flipbook_readiness.py` for Unreal-bound atlases

## 7. Unreal Handoff

When the atlas is meant for Unreal:

- report `Columns`, `Rows`
- report frame count
- report final atlas size
- report exact cell size, or state that the grid does not evenly divide the atlas
- report suggested playback fps
- report frame order, start frame, and end frame
- report alpha policy: true alpha, black-luma opacity, additive black, or custom
- report recommended blend mode and whether SubUV blending should be enabled
- note whether the atlas was snapped to power-of-two
- attach or generate a `ue-readiness-report.md`
- if material hookup is needed, hand off to `unreal-material-artist`
- if Niagara/SubUV hookup is needed, hand off to `niagara-vfx-artist`
