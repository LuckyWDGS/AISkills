# Prompt Recipes

Use these as starting patterns for system `imagegen` by default, or for another image route when the user explicitly switches providers.

Keep the prompt family stable across the whole sequence:

- same camera
- same canvas
- same subject scale
- same background rule
- same effect family

Prefer black or transparent backgrounds for atlas work.

For Unreal/Niagara review atlases, prefer black-background luminance texture sheets unless the pipeline explicitly needs true alpha. A generated preview is not production-ready until the final atlas has been snapped or packed to a power-of-two texture size. Prefer `2048x2048` or `4096x4096` for final source delivery; use `1024x1024` only for previews, mobile-only outputs, or explicit low-budget variants.

## Shared Invariants

Append a version of these constraints to every frame or anchor-state prompt:

- isolated VFX element only
- no environment
- no characters
- no props
- no text
- no UI
- power-of-two final atlas target when delivering a complete sheet, preferably 2K or 4K for final source art
- black luma-mask background for smoke/dust texture sheets unless true alpha is required
- no transparent checkerboard preview background in production atlases
- centered composition
- same framing as the previous accepted frame
- preserve the same effect family and silhouette language
- suitable for flipbook / sprite atlas / SubUV use

## Dust / Powder

Base prompt:

```text
isolated falling dust plume, soft particulate breakup, subtle turbulence, grayscale or neutral dust value, clean alpha-friendly silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame
```

Search seeds:

- `falling dust alpha reference`
- `powder plume side view`
- `ceiling dust collapse reference`

State hints:

- early:
  - thin seed streak, sparse particles, narrow core
- mid:
  - denser falling column, soft breakup, widening body
- late:
  - diffuse tail, lighter opacity, softer edges, fading particulate residue

Roof / ceiling dust variant:

```text
isolated falling roof or ceiling dust, tiny dry particles dropping from above, slow gravity-driven downward motion, narrow bundled dust streams, granular breakup, light residual suspended dust, clean alpha-friendly silhouette, centered, fixed camera, consistent scale, transparent or black background, VFX flipbook frame
```

Useful suffix ideas:

- `overhead release from a roof edge, no environment visible`
- `particle fall first, faint residual dust second`
- `vertical falling motion, not a sideways ground sweep`
- `narrow bundled columns, mild lateral spread only`
- `avoid fog banks, smoke plumes, mushroom clouds, or heavy mist`
- `black background luma texture, white-to-grey dust values, no checkerboard`

Timing hints:

- early:
  - near-empty cells, a few grains or thin falling streaks
- mid:
  - slow build into several bundled vertical dust streams
- peak:
  - airy particulate density, still semi-transparent and narrow
- late:
  - falling grains reduce first, then only sparse suspended residue remains

## Smoke

Base prompt:

```text
isolated smoke plume, soft volumetric breakup, layered curl motion, readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame
```

Search seeds:

- `smoke plume side reference`
- `smoke column alpha`
- `soft smoke VFX reference`

State hints:

- early:
  - small ignition puff, narrow rise
- mid:
  - fuller curl body, richer internal breakup
- late:
  - diffuse edges, lower density, soft fade

## Fire / Flame

Base prompt:

```text
isolated flame tongue, bright core with torn outer edges, strong upward flow, readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame
```

Search seeds:

- `torch flame side reference`
- `fire plume alpha reference`
- `stylized flame VFX side view`

State hints:

- early:
  - small ignition tongue, tight core
- mid:
  - brighter core, split tongues, stronger upward motion
- late:
  - thinner torn edges, collapsing tip, fading tail

Fire-specific warning:

- do not let the model turn the flame into an explosion
- do not let the flame change camera angle or scale
- reject frames where the outer silhouette becomes a different effect family

## Embers / Sparks

Base prompt:

```text
isolated ember and spark burst, small bright particles with controlled scatter, clean black background, centered, fixed camera, consistent scale, VFX flipbook frame
```

Search seeds:

- `ember burst reference`
- `spark shower alpha`
- `embers side view VFX`

State hints:

- early:
  - tighter cluster, brighter particles
- mid:
  - wider scatter, varying point sizes
- late:
  - fewer particles, dimmer residual glow

## Randomizable Sprite Sheets

Use this pattern when the cells are meant to be independent variants, not one ordered time sequence.

Good candidates:

- star sparkles
- glints
- embers
- tiny support sparks
- chips
- dust motes

Base prompt pattern:

```text
randomizable particle sprite sheet, independent cells not a strict time-sequence flipbook, transparent background, centered shape in each cell, varied but stylistically consistent silhouettes, no text, no UI, suitable for Niagara or texture sheet random sprite selection
```

Useful add-ons:

- stars / glints:
  - `white to pale cyan sparkle shapes, four-point and six-point glints`
- embers:
  - `tiny orange-red glowing cinders, irregular but readable hot flecks`
- chips:
  - `small broken debris fragments, grayscale or tan, irregular hard-edged silhouettes`

## Prompting Sequence Strategy

Good default sequence strategy:

1. Generate 4-6 anchor states.
2. Review for drift.
3. Use accepted anchors as references for follow-up states.
4. Fill the family in order.
5. Reject outliers immediately instead of hoping atlas packing hides them.

Boundary reminder:

- if the effect still works when the cells are shuffled, it may not need a strict continuous flipbook
- if the motion reads incorrectly when the cells are shuffled, it probably does need ordered continuity
- use `references/sequence-boundaries.md` before overcommitting to a full sequence for sparks, embers, chips, or tiny support particles

## Additional UE VFX Families

These often use flipbooks even though they are not smoke, dust, or fire:

- portals:
  - `isolated magic portal core, circular emissive ring, swirling inner energy, fixed camera, consistent scale, black background, ordered flipbook atlas`
- holograms:
  - `isolated hologram scan effect, translucent projection breakup, scanline shimmer, fixed camera, consistent scale, black background, flipbook atlas`
- water / foam:
  - `isolated water splash and foam burst, translucent droplets, readable splash silhouette, fixed camera, consistent scale, transparent background, flipbook atlas`
- blood / toxic impacts:
  - `isolated stylized blood impact mist and droplets, readable burst silhouette, fixed camera, consistent scale, transparent background, flipbook atlas`
  - `isolated toxic gas puff, rolling poison cloud, soft alpha-friendly silhouette, fixed camera, consistent scale, black background, flipbook atlas`
- muzzle flash / slash:
  - `isolated muzzle flash and gun smoke burst, bright flash core, short smoke expansion, fixed camera, consistent scale, black background, flipbook atlas`
  - `isolated weapon slash impact, bright crescent stroke, fragmenting energy tail, fixed camera, consistent scale, black background, flipbook atlas`

For these families, still decide whether the sheet is continuous, randomizable, or mixed before generating. Portals, holograms, water splashes, blood/toxic puffs, and slash impacts usually need ordered motion for the hero layer. Muzzle sparks, droplets, shards, and support glints often work as random sprite sheets.
