# Reference index

When to read each reference. [SKILL.md](../SKILL.md) lists them by group.

- [core.md](core.md)
  Use for the main interaction pattern, design principles, Niagara basics, and implementation framing.

- [niagara-fundamentals.md](niagara-fundamentals.md)
  Use for Systems, Emitters, renderer families, emitter count inference, and translating visual targets into Niagara layers.

- [niagara-operations-and-workflows.md](niagara-operations-and-workflows.md)
  Use for templates, user parameters, scratch pad usage, renderers, animation notifies, and practical Niagara workflows.

- [niagara-toolsets-vs-unrealbridge.md](niagara-toolsets-vs-unrealbridge.md)
  Use for official MCP coverage, supported references/topology, legacy script boundaries, and remaining fallback decisions.

- [common-effect-patterns.md](common-effect-patterns.md)
  Use for common effects such as explosions, shields, trails, hits, sigils, fire, smoke, projectiles, beams, and portals.

- [implementation-presets.md](implementation-presets.md)
  Use for practical starting presets, emitter breakdowns, module order, renderer choices, and first-pass ranges.

- [reference-analysis-output-spec.md](reference-analysis-output-spec.md)
  Use when the user provides a reference image, video, or design sheet and wants a full implementation package.

- [effect-layer-production-gate.md](effect-layer-production-gate.md)
  Use when a complex design sheet needs a stricter path from reference to UE-ready layer preview.

- [reference-deconstruction-patterns.md](reference-deconstruction-patterns.md)
  Use for deeper reference/video deconstruction and deciding whether a layer is Niagara-driven, material-driven, mesh-driven, flipbook-driven, or fluid-driven.

- [fluids-and-flowmaps.md](fluids-and-flowmaps.md)
  Use for fluid-like effects and deciding between Niagara Fluids, flow-map style material support, or baked flipbooks.

- [fluids-recipes.md](fluids-recipes.md)
  Use for concrete fluid-style effect recipes.

- [fluids-parameters.md](fluids-parameters.md)
  Use for Niagara Fluids parameter tuning.

- [fluids-troubleshooting.md](fluids-troubleshooting.md)
  Use when a fluid sim looks loose, blocky, blurry, weak, or too expensive.

- [fluids-production-pipeline.md](fluids-production-pipeline.md)
  Use for end-to-end fluid production decisions and baking workflows.

- [non-fluid-effects-playbook.md](non-fluid-effects-playbook.md)
  Use for hits, slashes, projectiles, beams, shields, sigils, portals, buffs, sparks, and related gameplay readability.

- [platform-optimization.md](platform-optimization.md)
  Use for Niagara scalability, particle budgets, bounds, culling, platform quality levels, and PC/Android tradeoffs. For material-specific cost, use `unreal-material-artist`.

- [debugging.md](debugging.md)
  Use for troubleshooting visibility, timing, sorting, renderer, integration, platform, and performance problems in Niagara effects.

- [ribbon-actor-trail-debugging.md](ribbon-actor-trail-debugging.md)
  Use when an Actor-attached Niagara Ribbon / Location Event trail shows white source orbs, folded cards, vertical sheets, wrinkles, hard seams, or large-motion discontinuity artifacts.

- [review-checklist.md](review-checklist.md)
  Use when the user wants to review or critique an existing Niagara effect.

- [asset-planning-checklist.md](asset-planning-checklist.md)
  Use when moving from design into production naming, systems, emitters, instances, textures, and low-end planning. Delegate material details to `unreal-material-artist`.

- [validation-and-qa.md](validation-and-qa.md)
  Use for final acceptance checks including distance, background, stress, hookup, platform readiness, and delivery criteria.

- [engine-integration-checklist.md](engine-integration-checklist.md)
  Use for animation notifies, Blueprints, GAS, Sequencer, user parameters, effect types, scalability, and platform switching.

- [tool-suite.md](tool-suite.md)
  Use when the request is about the closed-loop production tools and their CLI workflow.

- [request-intake-template.md](request-intake-template.md)
  这份文档用于把模糊需求快速整理成可执行输入，减少因为关键条件缺失导致的返工。

- [idea-to-prompt-fastloop.md](idea-to-prompt-fastloop.md)
  这份文档用于把模糊的效果想法，快速转成： - 图片生成提示词 - 视频生成提示词

- [vfx-direction-bible-template.md](vfx-direction-bible-template.md)
  这份文档用于作为项目级 VFX 方向总纲模板。

- [art-direction-patterns.md](art-direction-patterns.md)
  这份文档用于沉淀常见 VFX 艺术方向的拆解方式。

- [aesthetics-and-readability-strategy.md](aesthetics-and-readability-strategy.md)
  这份文档用于沉淀 VFX 审美判断和游戏可读性策略。

- [style-consistency-guide.md](style-consistency-guide.md)
  这份文档用于解决“单个效果成立，但整套项目特效风格不统一”的问题。

- [feasibility-and-fidelity-guide.md](feasibility-and-fidelity-guide.md)
  这份文档用于判断一个参考图、视频或设计稿在实时特效里到底能还原到什么程度。

- [implementation-confidence-template.md](implementation-confidence-template.md)
  这份文档用于把“能做多少、像到什么程度”的表达标准化。

- [model-turnaround-and-asset-gen-guide.md](model-turnaround-and-asset-gen-guide.md)
  这份文档用于规范：什么时候该做模型、什么时候不该优先做模型，以及如果要用生成式模型辅助建模，应该怎么准备多视图输入。

- [advanced-techniques.md](advanced-techniques.md)
  1. [纹理生成与优化](#纹理生成与优化) 2. [Flipbook 工作流](#flipbook-工作流) 3. [HLSL 自定义模块](#hlsl-自定义模块) 4. [Flow Maps 流向图](#flow-maps-流向图) 5. [通道打包优化](#通道打包优化)

- [system-integration-patterns.md](system-integration-patterns.md)
  这份文档用于定义 Niagara 与 Unreal 其他系统之间的标准接法，减少“效果本身没问题，但接入方式混乱”的问题。

- [examples.md](examples.md)
  /niagara

- [case-studies.md](case-studies.md)
  这份文档用于把前面已经沉淀下来的能力真正串成“完整方案模板”。

- [quick-reference.md](quick-reference.md)
  /niagara

- [production-workflow-map.md](production-workflow-map.md)
  这份文档用于把需求输入、方案设计、资产规划、实现、Review、QA、交付串成一条标准工作流。

- [end-to-end-vfx-delivery-map.md](end-to-end-vfx-delivery-map.md)
  Use this reference when the goal is not just advice, but a complete usable UE effect from a text brief or reference image.

- [project-bootstrap-checklist.md](project-bootstrap-checklist.md)
  这份文档用于回答：一个新项目刚开始做 VFX 时，第一周应该先准备什么，避免后面代价很大的返工。

- [self-training-and-iteration-loop.md](self-training-and-iteration-loop.md)
  这份文档用于建立一种“自己训练自己”的工作方式，让特效设计不是只靠灵感，而是靠一套可以重复执行的迭代方法。

- [common-failure-cases.md](common-failure-cases.md)
  这份文档用于沉淀 Niagara 特效制作中最常见、最容易反复踩的失败案例，以及快速修复思路。

- [mobile-checklist.md](mobile-checklist.md)
  这份文档专门用于 Android 和低端硬件上的 Niagara 特效落地检查。

- [capability-gap-map.md](capability-gap-map.md)
  UE 5.8.4 routing update: this is a historical workflow/implementation map, not proof of current official MCP gaps. Use Epic MCP for covered Niagara and editor operations; custom overlay and upstream-sync entries below describe retired...

- [tooling-and-automation-ideas.md](tooling-and-automation-ideas.md)
  这份文档用于沉淀哪些 VFX 生产环节值得做成脚本、Editor Utility、Python 工具或自动检查。
