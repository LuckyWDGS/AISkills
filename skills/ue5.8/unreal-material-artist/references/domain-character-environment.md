# Character And Environment Material Domain

## Character

Character materials typically need:

- stable skin/cloth/armor pipelines
- layered detail normals
- packed masks
- dirt/wear/blood/wetness overlays
- gameplay tint hooks
- platform-aware quality control

Key runtime owners:

- MI defaults for authored look
- MID for actor-specific state
- MPC for global scene influence

## Environment

Environment prop materials usually need:

- broad reuse
- clear packed-mask conventions
- decal compatibility
- world-aligned helpers where UVs are inconsistent
- distance-aware detail

Key review questions:

- Is this a hero material or a wide-reuse prop material?
- Should this be one master plus instances, or multiple simpler masters?
- Is the runtime control plan too actor-specific for the intended reuse level?

## Difference In Philosophy

Character materials:

- more per-actor nuance
- often more MID interaction
- more hero shading complexity

Environment materials:

- more scale and reuse
- more emphasis on consistent import standards and sampler budgets
- more benefit from disciplined master/function structure
