# Niagara VFX Artist Skill 维护说明

## 当前定位

`niagara-vfx-artist` 只负责 Unreal Engine Niagara 特效侧工作：

- 参考图拆解到 Niagara 层级
- System / Emitter / Module / Renderer 设计
- Spawn、Lifetime、Velocity、Event、Bounds、Scalability
- Renderer 材质槽位绑定需求与 carrier 合同
- 预览、审查、集成和交付

材质图、材质实例、纹理生成、HLSL、材质性能审查和材质配方已经拆到：

`D:/Skills/skills/unreal-material-artist`

Niagara 可以描述“这一层需要什么材质合同”，但不再把材质实现细节作为本 skill 的内部职责。

## 目录说明

```text
D:/Skills/skills/niagara-vfx-artist/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── core.md
│   ├── niagara-fundamentals.md
│   ├── niagara-operations-and-workflows.md
│   ├── common-effect-patterns.md
│   ├── implementation-presets.md
│   ├── reference-analysis-output-spec.md
│   ├── reference-deconstruction-patterns.md
│   ├── fluids-*.md
│   ├── non-fluid-effects-playbook.md
│   ├── platform-optimization.md
│   ├── debugging.md
│   ├── review-checklist.md
│   ├── validation-and-qa.md
│   ├── engine-integration-checklist.md
│   └── tool-suite.md
├── scripts/
│   └── vfx_delivery/
└── tools/
```

## 材质相关迁移

以下内容已经不再属于 Niagara skill：

- `references/material-recipes.md`
- `references/master-material-architecture.md`
- `references/texture-strategy-and-ai-prompts.md`
- `references/texture-prompt-framework.md`
- `tools/material_audit.py`
- `scripts/vfx_delivery/material_audit.py`

它们已迁移到 `D:/Skills/skills/unreal-material-artist/`。如果 Niagara 工作中需要这些能力，应同时使用 `unreal-material-artist`，并把 Renderer 类型、UV、Particle Color、Dynamic Parameter、Alpha、Blend Mode、Sorting、平台预算等信息整理成材质合同。

## 维护约定

- 改触发条件、工作流和职责边界：改 `SKILL.md`。
- 改 Niagara 细节知识：改 `references/` 下对应文档。
- 改闭环工具：改 `scripts/vfx_delivery/` 和 `tools/`。
- 改材质图、纹理、HLSL、材质性能：改 `D:/Skills/skills/unreal-material-artist/`，不要把实现细节加回 Niagara。

## 常用验证

```powershell
python C:/Users/QY/.codex/skills/.system/skill-creator/scripts/quick_validate.py D:/Skills/skills/niagara-vfx-artist
```

材质审查工具现在从新 skill 调用：

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_audit.py <material-path> --project <project-name> --markdown
```
