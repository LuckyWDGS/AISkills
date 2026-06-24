# Translucency Sorting Probe

## Use This When

- Additive, Translucent, AlphaComposite, Ribbon, Sprite, or Decal material evidence still has `sorting_unproven`.
- A material preview looked acceptable, but real depth sorting, DepthFade, SoftParticle, FixedBounds, or overdraw risk is not documented.
- A Niagara-side `niagara_material_integration_probe.py` or `niagara_audit.py` report exists and should be attached to the material delivery evidence.

## Purpose

`translucency_sorting_probe.py` is a read-only material-side risk probe. It gathers a delivery package, material contract, material audits, domain audits, previews, and optional Niagara probe/audit evidence, then reports whether translucency sorting is proven enough for material delivery review.

It does not own real Niagara renderer setup. If sorting remains unproven, the next action is to run the Niagara skill's integration probe on the production System/Emitter/Renderer.

## Typical Commands

```powershell
python D:/Skills/skills/unreal-material-artist/tools/translucency_sorting_probe.py --package D:/reports/material-delivery-package.json --markdown
```

Require real sorting/bounds proof before passing:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/translucency_sorting_probe.py --package D:/reports/material-delivery-package.json --material-integration-probe D:/reports/niagara-material-integration-probe.json --require-proven --markdown
```

## Checks

- Route applicability: Additive/Translucent/AlphaComposite/Modulate, sprite/ribbon/decal carrier, or deferred decal domain.
- Material-side mitigation: DepthFade, SceneDepth, PixelDepth, or SoftParticle-style graph evidence.
- Contract evidence: sorting/depth notes in the material contract or package.
- System evidence: SortMode, CustomSortingBinding, SortKey, or explicit `sorting` OK from Niagara probe/audit.
- Bounds evidence: FixedBounds or equivalent Niagara audit text.
- Overdraw risk: documented high overdraw without DepthFade/SoftParticle mitigation.

## Output

The report writes under:

```text
<project>/.codex/session/material-delivery/translucency-sorting/<effect>/translucency-sorting-probe.json
```

Important fields:

- `gate.sorting_proven`: true only when applicable routes have contract, sorting, and bounds proof.
- `gate.material_preview_is_system_proof`: always false.
- `findings[]`: specific missing or proven evidence.
- `next_actions[]`: where to gather the next proof.

## Boundary

Material preview evidence can show that the shader behaves on a lightweight carrier harness. It cannot prove production Niagara renderer sorting, custom sort bindings, bounds, culling, or emitter setup. Hand this report to `niagara-vfx-artist` when real system proof is needed.
