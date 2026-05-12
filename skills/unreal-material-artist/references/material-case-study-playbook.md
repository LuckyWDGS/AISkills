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

4. Read back the asset.
   Do not trust the create call. Read `get_material_info`, `get_material_graph`, and raw editor properties for `MaterialDomain`, `BlendMode`, `ShadingModel`, `TwoSided`, and `UseMaterialAttributes`.

5. Audit and preview.
   Run `material_domain_audit.py` first, then `material_audit.py`, then preview on the closest available carrier. Use shader complexity where relevant.

6. Compare to the source.
   Check structural match first, then visual match:
   - Structural: same domain/blend/shading/outputs/texture roles.
   - Visual: same carrier, mesh/card shape, lighting, camera, textures, masks, and parameter values.

7. Fix mismatches by cause.
   Do not average your graph toward the screenshot. Identify the missing contract item.

8. Promote the lesson.
   Add a short rule to this skill only when it generalizes beyond the one case.

## Mismatch Categories

| Mismatch | Likely Cause | Fix |
|---|---|---|
| Source says `Masked`, audit says `Opaque` | create/write API did not persist the property or info readback is stale/wrong | Cross-check raw editor property and recompile/save; fix bridge readback if needed |
| Correct graph but wrong look | carrier, texture, mesh, lighting, or camera mismatch | Preview on the source carrier and use equivalent texture inputs |
| Foliage looks like a glowing plane | no leaf diffuse/alpha texture and no leaf card mesh | Add leaf albedo/alpha, OpacityMask, SubsurfaceColor, two-sided card preview |
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

Lesson:

- For foliage, structural pass is not enough. Always verify alpha/mask texture, two-sided geometry, and lighting/transmission context before saying it matches the reference.

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

## Rules To Carry Forward

- For external examples, judge by contract first and screenshot second.
- Always verify material properties after creation; do not trust write APIs without readback.
- Keep a difference log: source expectation, UE readback, audit finding, visual mismatch, fix.
- If the source uses a texture, do not claim visual equivalence from a constant-color placeholder.
- If the source depends on a carrier, use that carrier or explicitly mark the preview as only a structural material check.
- Good lessons become skill references; one-off quirks stay in the case report.

