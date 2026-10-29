# Reference index

When to read each reference. [SKILL.md](../SKILL.md) lists them by group.

- [material-audit-workflow.md](material-audit-workflow.md)
  Use for review, cleanup, live-graph readback, stale override detection, and acceptance criteria.

- [material-contract-and-tooling.md](material-contract-and-tooling.md)
  Use for Niagara-to-material handoffs, delivery contracts, tool selection, and the material specialist capability roadmap.

- [niagara-ribbon-flame-trail.md](niagara-ribbon-flame-trail.md)
  Use for additive fire/flame/energy Niagara Ribbon trail material routes, packed R/G/B mask conventions, Chinese artist parameters, Android fallback assumptions, and MI handoff checklists.

- [reference-to-material-plan.md](reference-to-material-plan.md)
  Use when a reference image, tutorial screenshot, case study, or visual target needs to become a structured material route, texture plan, parameter table, preview plan, audit checklist, and optional material contract seed.

- [delivery-packager.md](delivery-packager.md)
  Use when material work needs one handoff bundle that gathers plan, contract, texture QA, preview, audit, risk notes, missing evidence, and next actions.

- [material-acceptance-gate.md](material-acceptance-gate.md)
  Use when a delivery package needs to become a hard approved material delivery report with `delivery_summary.approved_for_reuse=true` for downstream reuse or Niagara delivery gating.

- [material-acceptance-gate-v2.md](material-acceptance-gate-v2.md)
  Use when stronger stock-grade reuse approval should require parameter schema, provenance, preview matrix, readability, and translucent sorting evidence as hard gates.

- [material-delivery-smoke.md](material-delivery-smoke.md)
  Use when the existing material-side tools should be run as one end-to-end smoke chain instead of being orchestrated by hand.

- [material-parameter-schema.md](material-parameter-schema.md)
  Use when material parameters need explicit units, ranges, defaults, runtime owners, write owners, artist tunability, and regression participation before MI, Blueprint, Niagara, or delivery handoff.

- [material-regression.md](material-regression.md)
  Use after a material preview has been accepted and later edits need to be checked for visual drift, brightness changes, alpha/coverage changes, centroid shifts, or complexity preview changes.

- [regression-baseline-set.md](regression-baseline-set.md)
  Use when one regression baseline has turned into many and the right baseline now depends on tier, carrier, background, exposure, or quality context.

- [graph-diff-refactor.md](graph-diff-refactor.md)
  Use when regression fails or a graph/parameter refactor needs explanation from before/after material audits, domain audits, and optional regression evidence.

- [graph-refactor-apply.md](graph-refactor-apply.md)
  Use when a graph-diff refactor plan should become a duplicated candidate material with backup, transaction evidence, before/after audits, preview, regression, and rollback guidance.

- [texture-set-pipeline.md](texture-set-pipeline.md)
  Use when BaseColor, Normal, RMA/ORM/MRA, Opacity, and Emissive must be checked as one material texture set, when import-fix batch specs are needed, or when separate Roughness/Metallic/AO maps should be packed.

- [material-source-provenance.md](material-source-provenance.md)
  Use when texture source, generation prompt, original file, import settings, repair history, packed-channel inputs, license, or reuse eligibility must be preserved.

- [preview-matrix.md](preview-matrix.md)
  Use when one material preview is too narrow and evidence should cover background intent, exposure intent, distance, angle, time, parameter tier, quality, lighting, or carrier variations.

- [preview-readability-score.md](preview-readability-score.md)
  Use when a preview technically captured but may still be visually empty, low-contrast, off-center, or otherwise unreadable.

- [preview-scene-harness-upgrade.md](preview-scene-harness-upgrade.md)
  Use when preview-matrix axes such as background, exposure, or parameter tier need a concrete executable harness plan instead of remaining intent-only.

- [preview-environment-executor.md](preview-environment-executor.md)
  Use when those environment axes are ready to execute for real instead of only being planned.

- [translucency-sorting-probe.md](translucency-sorting-probe.md)
  Use for Additive/Translucent/Ribbon/Decal material sorting, DepthFade, SoftParticle, bounds, custom sorting, and overdraw-risk evidence; real Niagara system proof remains Niagara-owned.

- [material-variant-runner.md](material-variant-runner.md)
  Use when a material parameter schema should generate default/low/high/extreme/gameplay-safe MI tiers and batch specs for preview/regression.

- [static-switch-variant-expander.md](static-switch-variant-expander.md)
  Use when static switches need to be crossed with dynamic tiers so preview and smoke coverage includes real permutation space.

- [permutation-budget-guard.md](permutation-budget-guard.md)
  Use when single-material static-switch pressure should be judged before it becomes a project-wide shader-permutation problem.

- [shader-cost-attribution.md](shader-cost-attribution.md)
  Use when optimization needs a heuristic breakdown of which graph feature buckets are likely driving shader cost.

- [platform-scalability-planner.md](platform-scalability-planner.md)
  Use when existing material evidence should become PC/Android/low-end downgrade guidance and fallback MI planning.

- [smoke-resume-cache.md](smoke-resume-cache.md)
  Use when repeated material-delivery smoke reruns should skip unchanged steps instead of recomputing the whole chain.

- [project-material-health.md](project-material-health.md)
  Use when accumulated evidence should become project-level heatlists for risky materials, texture sets, regressions, graph diffs, parameter names, permutations, or suspicious master-material candidates.

- [material-function-dependency-map.md](material-function-dependency-map.md)
  Use when Material Function dependencies, reuse hotspots, duplicate names, or oversized function governance need a project-level map.

- [material-toolset-builder.md](material-toolset-builder.md)
  Use when a known material route should become a repeatable recipe package and executable builder spec, or when graph-diff evidence should become a narrow guarded refactor plan.

- [tech-art-material-systems.md](tech-art-material-systems.md)
  Use when the task is really about technical-art material systems: master/function layering, runtime ownership, MPC vs MID vs Niagara, and project-wide material architecture.

- [material-domain-and-rendering-contracts.md](material-domain-and-rendering-contracts.md)
  Use when auditing `Material Domain`, `Blend Mode`, output pins, post process, UI, decal, light-function, volume, RVT, WPO/PDO, or whether a material is in the wrong render path.

- [material-case-study-playbook.md](material-case-study-playbook.md)
  Use when learning from online material examples, matching a reference material, creating UE reproductions, comparing audit/preview results to the source, and promoting reusable lessons.

- [substrate-and-material-layers.md](substrate-and-material-layers.md)
  Use for Substrate, Material Layers, Material Attributes, layered master materials, layer masks, BSDF layering, and layer-stack cost review.

- [specialized-shading-models.md](specialized-shading-models.md)
  Use for Hair, Cloth, Eye, Clear Coat, Subsurface, TwoSidedFoliage, Single Layer Water, Thin Translucent, FromMaterialExpression, or other non-DefaultLit shading decisions.

- [complex-water-material-playbook.md](complex-water-material-playbook.md)
  Use for concrete water material authoring: Single Layer Water, stylized water, glass/transparent liquid, depth color, foam, caustics, normals, flow maps, WPO waves, texture generation, preview gates, and water-specific audit.

- [fire-energy-material-playbook.md](fire-energy-material-playbook.md)
  Use for concrete fire-family material authoring: flame, torch, campfire, ember, smoke material, burning/dissolve edge, heat haze, lava, magma, plasma, energy flame, additive/unlit emissive routes, flipbook/SubUV texture strategy, generated fire masks, carrier preview gates, and overdraw/shader-complexity audit.

- [complex-master-material-playbook.md](complex-master-material-playbook.md)
  Use when designing or reviewing a large multi-feature master material for characters, environments, overlays, wetness, wear, detail systems, or heavy runtime control.

- [domain-landscape-foliage.md](domain-landscape-foliage.md)
  Use for landscape, foliage, RVT, masked overdraw, wind/WPO, and large-screen-coverage terrain/vegetation material decisions.

- [domain-character-environment.md](domain-character-environment.md)
  Use for character, armor, cloth, prop, and environment material domain decisions, especially runtime ownership and reuse strategy.

- [material-preview-presets.md](material-preview-presets.md)
  Use when the task depends on carrier-specific preview intent, especially Niagara sprite/ribbon presets, SubUV preview assumptions, decal preview, or post-process preview behavior.

- [material-asset-library.md](material-asset-library.md)
  Use when the task may reuse generic texture building blocks, when new generated assets should be categorized and promoted into a library, or when failed generated assets should be kept out of the approved reuse pool.

- [library-promotion-gate.md](library-promotion-gate.md)
  Use when a fully evidenced material candidate should be judged for promotion into approved reusable library stock.

- [texture-vs-compute.md](texture-vs-compute.md)
  Use when deciding whether to bake detail into textures, compute it procedurally, use flipbooks/atlases, or simplify for platform cost.

- [material-node-map.md](material-node-map.md)
  Use for a compact map of major UE material node families, HLSL guidance, and how to read graph intent.

- [material-recipes.md](material-recipes.md)
  Use as the compact router for reusable VFX/surface material recipes; then load one of the narrower recipe references below.

- [material-recipes-naming-and-mobile.md](material-recipes-naming-and-mobile.md)
  Use for material parameter naming, Niagara/MI binding-name readability, and PC/Android/low-end simplification rules.

- [material-recipes-vfx-shield-explosion-smoke.md](material-recipes-vfx-shield-explosion-smoke.md)
  Use for shield, explosion core, energy ball, smoke, and fog material recipe patterns.

- [material-recipes-trails-shockwaves-dissolve-water-fire.md](material-recipes-trails-shockwaves-dissolve-water-fire.md)
  Use for trails, flow materials, shockwaves, dissolve edges, procedural noise, water starter routes, and additive fire-mask recipes.

- [master-material-architecture.md](master-material-architecture.md)
  Use when designing a project-wide master material system, parameter boundaries, instances, and fallback variants.

- [texture-strategy-and-ai-prompts.md](texture-strategy-and-ai-prompts.md)
  Use as the compact router for texture strategy references.

- [texture-strategy-selection-and-rules.md](texture-strategy-selection-and-rules.md)
  Use when deciding whether a material needs a single texture, Flipbook/SubUV, sprite atlas, flow map, mask, generated texture plan, UE/Niagara hookup, or global generation rules.

- [texture-prompts-vfx.md](texture-prompts-vfx.md)
  Use for fire, ember, smoke, lightning, and related VFX texture prompt templates.

- [texture-domain-foliage-water.md](texture-domain-foliage-water.md)
  Use for leaf diffuse/alpha, foliage card, and custom water texture policy where the reference image or domain identity controls the texture strategy.

- [texture-prompt-framework.md](texture-prompt-framework.md)
  Use when generating texture prompts or deciding whether a texture is appropriate for `cm-imagegen`.

- [generated-texture-qa.md](generated-texture-qa.md)
  Use when generating, accepting, rejecting, or importing AI-created textures, masks, atlases, flipbooks, ramps, flow maps, normals, or packed data.

- [official-toolsets-vs-local.md](official-toolsets-vs-local.md)
  Use for direct Epic MCP material/texture/MI operations, legacy-tool boundaries, and demonstrated fallback gaps.

- [official-doc-notes.md](official-doc-notes.md)
  Use when you need the source-backed principles behind UE material inputs, expression nodes, Custom HLSL, and performance view modes.

- [ribbon-trail-seam-debugging.md](ribbon-trail-seam-debugging.md)
  Use when a Niagara ribbon/trail material shows split lines, repeated tile bands, hard width edges, or scene-intersection cuts after the ribbon geometry and source event chain are verified.
