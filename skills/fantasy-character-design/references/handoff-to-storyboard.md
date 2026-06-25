# Handoff To Storyboard

## Purpose

This skill defines who the character is. `short-video-storyboard` defines what happens in time.

Use the exported handoff package when moving from character design to first/last frames, bridge boards, or 25-panel storyboards.

## Handoff Fields

Exported prompt packs should include:

- `character_name`
- `identity_lock`
- `costume_lock`
- `materials`
- `props`
- `palette`
- `world`
- `avoid`
- `reference_inputs`
- `reference_strategy`
- accepted hero image path, when available
- accepted face/costume/prop/detail paths, when available

## Mapping To Storyboard References

Map character-design outputs into storyboard anchors:

| Character design output | Storyboard role |
| --- | --- |
| hero full-body image | face + outfit anchor |
| face close-up | face anchor |
| turnaround front/side/back | outfit anchor |
| prop or magic device | product/prop anchor |
| palette/material panels | style or costume constraint |
| full character bible prompt | global lock |

Preserve `weight`, `priority`, `crop`, `focus`, and `lock` when mapping anchors. Use storyboard defaults only when a character-design export lacks a field.

Recommended mapping:

| Character anchor | Storyboard anchor | Notes |
| --- | --- | --- |
| `face_anchors` | `face_anchors` | Keep `hard-identity`, usually P100/W1.0 |
| `costume_anchors` | `outfit_anchors` | Keep silhouette/material focus |
| `prop_anchors` | `product_anchors` | Treat magic weapons or devices as hard local detail |
| `style_anchors` | `style_anchors` | Keep soft style; do not let it rewrite identity |
| `generic_references` | `generic_references` | Inspiration only |

## Recommended Chain

1. Create character design sheet spec.
2. Generate or approve hero full-body and detail panels.
3. Export handoff package.
4. Create storyboard spec in `short-video-storyboard`.
5. Attach accepted images as layered references.
6. Generate start/end frames or 25-panel storyboard prompts.

## Do Not Couple Internals

Do not import storyboard templates into this skill and do not force character sheets to contain shot duration, transitions, or camera moves. Those belong to video planning.
