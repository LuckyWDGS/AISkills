# Material Case Study Playbook

Use this when learning from an online UE material example, matching a reference material, or checking whether a generated material really follows a known recipe.

The goal is not to copy a graph blindly. The goal is to extract the material contract, rebuild a minimal UE version, audit it, preview it on the right carrier, and turn any mismatch into a reusable rule.

## Case Study Workflow

1. Capture the source.
   Record the URL, engine/version context, target domain, blend mode, shading model, required outputs, texture roles, carrier, and any project settings.

2. Extract the contract.
   Convert tutorial steps into a checklist:
   `domain`, `blend`, `shading`, `two_sided`, `outputs`, `texture channels`, `parameters`, `carrier`, `platform risk`.

3. Build a minimal UE reproduction.
   Use a temporary path such as `/Game/CodexTemp/MaterialCaseStudies/M_Case_*`. Keep it minimal first, then add texture/visual fidelity only after the contract is clean.

4. Resolve required texture and carrier gaps.
   If the source depends on diffuse/alpha, leaf cards, masks, normals, flow, packed channels, atlases, or a specific preview carrier, search the reusable asset library before calling the result a visual mismatch. If no approved asset fits, generate with `cm-imagegen`; use the user's reference image as image input when available. QA generated textures with `texture_asset_report.py`, import/audit/fix them when they enter UE, and regenerate rejected candidates instead of accepting placeholders.

5. Read back the asset.
   Do not trust the create call. Read `get_material_info`, `get_material_graph`, and raw editor properties for `MaterialDomain`, `BlendMode`, `ShadingModel`, `TwoSided`, and `UseMaterialAttributes`.

6. Audit and preview.
   Run `material_domain_audit.py` first, then `material_audit.py`, then preview on the closest available carrier. Use shader complexity where relevant.

7. Compare to the source.
   Check structural match first, then visual match:
   - Structural: same domain/blend/shading/outputs/texture roles.
   - Visual: same carrier, mesh/card shape, lighting, camera, textures, masks, and parameter values.

8. Fix mismatches by cause.
   Do not average your graph toward the screenshot. Identify the missing contract item.

9. Promote the lesson.
   Add a short rule to this skill only when it generalizes beyond the one case.

## Mismatch Categories

| Mismatch | Likely Cause | Fix |
|---|---|---|
| Source says `Masked`, audit says `Opaque` | create/write API did not persist the property or info readback is stale/wrong | Cross-check raw editor property and recompile/save; fix bridge readback if needed |
| Correct graph but wrong look | carrier, texture, mesh, lighting, or camera mismatch | Preview on the source carrier and use equivalent texture inputs |
| Foliage looks like a glowing plane | no leaf diffuse/alpha texture and no leaf card mesh/carrier | Search the `foliage` library category; if missing, generate a POT leaf diffuse/alpha card with `cm-imagegen`, QA with `--role foliage`, import as color+mask data correctly, then preview on a two-sided masked card or cluster |
| Clear coat lacks a second highlight | missing Clear Coat / Clear Coat Roughness or bottom-normal setup | Wire Clear Coat amount/roughness; enable and route bottom normal only when the project needs it |
| Light function changes color instead of intensity | treating light function as a surface emissive material | Use grayscale/intensity mask logic and verify actual light application |
| Post process compiles but ignores surface pins | wrong output route for PostProcess domain | Output final color through EmissiveColor and use SceneTexture/PostProcessInput where needed |
| Layered material matches still image but is too expensive | every layer samples full texture stacks per pixel | Collapse layers, bake masks, reduce samples, use quality switches, or split by material slot |

## Live UE Case Studies

These were built under `/Game/CodexTemp/MaterialCaseStudies/` and audited with `material_domain_audit.py`.

### Light Function Intensity Mask

Source: Epic Light Functions documentation.

Expected contract:

- `Material Domain`: `LightFunction`
- `Shading Model`: `Unlit`
- output route: grayscale/intensity into `EmissiveColor`
- purpose: modulate light intensity, not author a surface color

UE reproduction result:

- Domain `LightFunction`
- Blend `Opaque`
- Shading `Unlit`
- Wired output `EmissiveColor`
- `material_domain_audit.py`: no first-pass findings

Lesson:

- A light-function material should be audited as a light mask. Keep it cheap and grayscale/intensity oriented unless the project has a very specific light-function reason.

### Two-Sided Foliage

Source: Epic Wiki Two-Sided Foliage tutorial.

Expected contract:

- `Material Domain`: `Surface`
- `Blend Mode`: `Masked`
- `Shading Model`: `TwoSidedFoliage`
- `Two Sided`: true
- important outputs: `BaseColor`, `SubsurfaceColor`, `OpacityMask`, `Roughness`, `Specular`, usually `Normal`
- texture roles: diffuse/albedo with alpha, normal, optional roughness/spec masks

UE reproduction result:

- Domain `Surface`
- Blend `Masked`
- Shading `TwoSidedFoliage`
- Two Sided `true`
- Wired outputs `BaseColor`, `SubsurfaceColor`, `OpacityMask`, `Roughness`, `Specular`, `Normal`
- `material_domain_audit.py`: no first-pass findings
- `material_audit.py`: no findings

Visual note:

- A minimal constant-color plane is structurally correct but not visually equivalent to the tutorial's bush result. Visual equivalence requires a leaf/bush mesh or card, a diffuse texture with alpha, and backlit foliage preview.
- If those textures are missing, the correct next action is to search the foliage asset library. If no approved asset matches the species/reference, generate a leaf diffuse/alpha card from the reference with `cm-imagegen`, require power-of-two output, clean cutout alpha, no background pollution, no shadow baked into alpha, and rerun `texture_asset_report.py --role foliage` on the stored library copy.

Lesson:

- For foliage, structural pass is not enough. Always verify alpha/mask texture, two-sided geometry, and lighting/transmission context before saying it matches the reference.
- A missing leaf texture or card carrier is not an excuse to stop at "visual mismatch"; it is a material asset-production step owned by this skill.

### Clear Coat Car Paint

Source: Epic clear coat shading model tech blog.

Expected contract:

- `Material Domain`: `Surface`
- `Blend Mode`: usually `Opaque`
- `Shading Model`: `ClearCoat`
- important outputs: `BaseColor`, `Metallic`, `Roughness`, `Normal`, Clear Coat amount, Clear Coat Roughness
- in bridge graph output names, Clear Coat amount and roughness appear as `CustomData0` and `CustomData1`

UE reproduction result:

- Domain `Surface`
- Blend `Opaque`
- Shading `ClearCoat`
- Wired outputs `BaseColor`, `Metallic`, `Roughness`, `Normal`, `CustomData0`, `CustomData1`
- `material_domain_audit.py`: no first-pass findings
- `material_audit.py`: no findings
- preview showed expected glossy coated highlights on a sphere

Lesson:

- Do not stop at setting the `ClearCoat` shading model. The material must also expose coat amount and coat roughness, and complex car paint may need second-normal/bottom-normal support at the project-setting level.

### Difficulty Ladder: Fresnel, Clear Coat, Chrome Snow

Source anchors:

- Epic Fresnel material guide.
- Epic Shading Models / Clear Coat documentation and clear-coat tech blog.
- Epic Layered Materials / Creating Layered Materials documentation.

UE reproductions were built under `/Game/CodexTemp/MaterialDifficultyCases/20260513_092331/`.

Simple case:

- Asset: `/Game/CodexTemp/MaterialDifficultyCases/20260513_092331/M_D01_Simple_FresnelRim`
- Contract: `Surface`, `Opaque`, `DefaultLit`; `BaseColor`, `Roughness`, flat `Normal`, Fresnel-driven `EmissiveColor`.
- Audit: `236` instructions, `0` samplers, no compile errors, no findings after adding an explicit flat normal.
- Lesson: even a simple lit material should wire `Normal` deliberately when the audit standard expects a complete PBR contract. Do not use VFX-sized instruction budgets for ordinary `DefaultLit` surface materials.

Medium case:

- Asset: `/Game/CodexTemp/MaterialDifficultyCases/20260513_092331/M_D02_Medium_ClearCoatCarPaint`
- Contract: `Surface`, `Opaque`, `ClearCoat`; `BaseColor`, `Metallic`, `Roughness`, flat `Normal`, `CustomData0` for clear-coat amount, `CustomData1` for clear-coat roughness.
- Audit: `247` instructions, `0` samplers, no compile errors, no findings.
- Lesson: clear coat is not complete just because the shading model is set. The material must expose and wire the coat amount and coat roughness pins; in bridge/audit output these appear as `CustomData0` and `CustomData1`.

Complex case:

- Final asset: `/Game/CodexTemp/MaterialDifficultyCases/20260513_092331/M_D03_Complex_ChromeSnowLayered`
- Contract: `Surface`, `Opaque`, `DefaultLit`; chrome layer and snow layer blended by `VertexNormalWS.Z` slope mask; outputs `BaseColor`, `Metallic`, `Roughness`, flat `Normal`.
- Audit: `231` instructions, `0` samplers, no compile errors, no findings.
- Lesson: a complex material does not need to be texture-heavy. A procedural slope mask can be cheaper and more inspectable than generating a mask texture when the effect is geometric and camera-stable.

Superseded complex experiment:

- Asset: `/Game/CodexTemp/MaterialDifficultyCases/20260513_092331/M_D03_Complex_LayeredWetProp`
- Initial audit caught a real sampler/import bug: `TextureSampleParameter2D` nodes used `SAMPLERTYPE_Masks` while their default texture was `/Engine/EngineResources/WhiteSquareTexture`, which is color/sRGB, causing a compile error.
- Fix applied: replace `ORMTex` and `OverlayORMTex` defaults with `/Game/BridgeTemplates/_System/T_White_Masks`, a `TC_Masks` + `sRGB=false` project-local system texture.
- A `QualitySwitch` was added to demonstrate cost-governance for sample-heavy masters. Its showcase MI also produced static-switch permutation info, which is acceptable but should be reported.
- Lesson: placeholder textures are still real shader inputs. Mask/packed default textures must have mask compression and sRGB off; otherwise a complex master can fail before any artist texture is assigned.

### Dissolve, Noise, Single Layer Water, Fire

Source anchors:

- [Epic community dissolve/disintegration discussion](https://forums.unrealengine.com/t/disintegration-dissolve/16399): noise/mask drives opacity threshold, with separate color/emissive controls for the dissolve edge.
- [Epic/Ryan Brucks noise guidance](https://www.unrealengine.com/en-US/tech-blog/getting-the-most-out-of-noise-in-ue4): procedural Noise is powerful but can be expensive; use baked textures when a stable organic pattern is enough.
- [Epic Single Layer Water documentation](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/single-layer-water-shading-model-in-unreal-engine): water uses the `SingleLayerWater` shading model on the opaque or masked path with water-specific scattering/absorption outputs.
- [Epic material inputs documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/material-inputs-in-unreal-engine?application_version=5.6) and [material expression placement docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/placing-material-expression-and-functions?application_version=4.27): masked/additive opacity behavior and `Panner` UV motion are core to dissolve/fire prototypes.

Generated texture gap:

- The reusable library had no approved assets for these cases, so `cm-imagegen` was used by default.
- Generated assets were stored under `D:\UnrealBridge\.codex\session\material-delivery\case-studies\20260513_dissolve_noise_water_fire\generated-textures\`.
- All three generated textures were `1024x1024` power-of-two PNGs.
- `T_Case_TileableNoiseMask` passed first-pass texture report as a noise texture and was imported into UE as `TC_Masks` + `sRGB=false`.
- `T_Case_FireTongueMask` passed POT checks but had no alpha; it is valid only for black-background/luminance mask usage unless regenerated or alpha-extracted.
- `T_Case_WaterRippleHeight` passed first-pass size checks but remains draft technical data, not an approved final normal/flow asset.
- Library entries were registered as `candidates`, not `approved`, because first-pass reports do not prove tiling quality, alpha correctness, or vector-data semantics.

UE reproductions were built under `/Game/CodexTemp/MaterialCaseStudies/20260513_DissolveNoiseWaterFire/`.

Dissolve case:

- Asset: `/Game/CodexTemp/MaterialCaseStudies/20260513_DissolveNoiseWaterFire/M_Case_Dissolve_NoiseEdge`
- Contract: `Surface`, `Masked`, `Unlit`, `TwoSided=true`; generated noise mask routes to `OpacityMask`; Custom edge band routes to `EmissiveColor`.
- Audit: `140` instructions, `1` sampler, no compile errors. Finding: informational quality-gate warning because it uses a Custom node without a `QualitySwitch`.
- Lesson: dissolve shape belongs in a mask texture when the breakup is art-directed and reused. The threshold/edge math is cheap control logic around that texture.

Procedural noise case:

- Asset: `/Game/CodexTemp/MaterialCaseStudies/20260513_DissolveNoiseWaterFire/M_Case_Procedural_Noise_Surface`
- Contract: `Surface`, `Opaque`, `Unlit`; `Noise` node multiplied by tint into `EmissiveColor`.
- Audit: `155` instructions, `0` samplers, no compile errors, no findings.
- Lesson: 0 samplers does not mean free. Procedural noise trades texture bandwidth for ALU; keep it when live/world-space parameterization matters, but bake it when it is just a static breakup mask.

Single Layer Water case:

- Asset: `/Game/CodexTemp/MaterialCaseStudies/20260513_DissolveNoiseWaterFire/M_Case_SingleLayerWater_Ripple`
- Contract: `Surface`, `Opaque`, `SingleLayerWater`; ripple height draft feeds a Custom height-to-normal prototype; `SingleLayerWaterMaterialOutput` carries scattering, absorption, phase, and behind-water color.
- Audit with ordinary surface budget first reported `1028` instructions, `1` sampler, no compile errors, plus dead-node findings for the water output node because the graph scanner currently treats it as not connected to a main material output.
- Re-audit with a water-specific budget (`1200`) passed the instruction threshold but still showed conservative dead-node findings for `SingleLayerWaterMaterialOutput`.
- Lesson: Single Layer Water needs a specialized audit mental model. Do not compare it to simple DefaultLit or VFX budgets, and do not treat water-output dead-node findings as definitive until the scanner understands water material output semantics.

Fire case:

- Asset: `/Game/CodexTemp/MaterialCaseStudies/20260513_DissolveNoiseWaterFire/M_Case_Fire_AdditiveMask`
- Contract: `Surface`, `Additive`, `Unlit`, `TwoSided=true`; generated black-background fire mask is panned, tinted, multiplied by `ParticleColor`, and routed to `EmissiveColor` and `Opacity`.
- Audit: `305` instructions, `1` sampler, no compile errors. This exceeds a simple VFX budget but can be acceptable as a PC prototype if overdraw and particle count are controlled.
- Lesson: fire material cost is dominated by overdraw, coverage, and blend path as much as graph size. For hero fire, prefer flipbook/SubUV; for detail layers, a single mask plus panner is a reasonable prototype.

## Rules To Carry Forward

- For external examples, judge by contract first and screenshot second.
- Always verify material properties after creation; do not trust write APIs without readback.
- Keep a difference log: source expectation, UE readback, audit finding, visual mismatch, fix.
- If the source uses a texture, do not claim visual equivalence from a constant-color placeholder.
- If the source depends on a carrier, use that carrier or explicitly mark the preview as only a structural material check.
- If no approved library asset exists for a needed texture, default to `cm-imagegen`, run `texture_asset_report.py`, import/fix UE settings if used, and register the stored result as `candidates` or `rejected` before reuse.
- Candidate assets are not stock. Promote only after self-review, first-pass reports, and any role-specific visual/technical checks pass on the library-stored copy.
- Treat special shading models, especially `SingleLayerWater`, with domain-specific budgets and scanner exceptions instead of forcing ordinary surface-material thresholds.
- Good lessons become skill references; one-off quirks stay in the case report.
