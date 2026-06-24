# UE VFX 材质配方库

## 用途

这份文档现在只作为配方路由入口。按任务读取更窄的 reference，避免为了一个材质路线加载整本手册。

适合在这些场景读取：
- 需要快速选择该读哪份配方
- 用户想知道某类特效常用什么节点结构
- 需要从视觉目标反推材质实现
- 需要给出适合 PC / Android 的材质简化版本

如果任务需要把配方直接变成结构化施工包或可执行 MaterialTools spec，优先使用：

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_toolset_builder.py recipe <recipe> --effect <Effect> --layer <Layer> --markdown
```

详细规则见 `references/material-toolset-builder.md`。配方 references 负责解释视觉和节点经验，`material_toolset_builder.py recipe` 负责把常见路线固化成参数表、贴图需求、预览/审计计划和 builder spec。

---

## 目录

- [参数命名与移动端简化](material-recipes-naming-and-mobile.md)
- [护盾、爆炸、能量球、烟雾](material-recipes-vfx-shield-explosion-smoke.md)
- [拖尾、冲击波、消融、噪声、水、火](material-recipes-trails-shockwaves-dissolve-water-fire.md)
- [Niagara Ribbon 火焰拖尾专项](niagara-ribbon-flame-trail.md)
- [Fire / Energy 深度 playbook](fire-energy-material-playbook.md)
- [Water 深度 playbook](complex-water-material-playbook.md)
- [Recipe builder](material-toolset-builder.md)

---

## 使用建议

当用户说“帮我做某种效果”时，先从上面的窄 reference 里选一个接近的材质配方，再结合：
- `SKILL.md` 里的核心工作流和硬规则
- `references/texture-vs-compute.md` 里的贴图/计算取舍
- `references/platform-scalability-planner.md` 里的 PC / Android / low-end 假设与降级计划
- `references/material-node-map.md` 里的节点族和 HLSL 读图方式
- `references/niagara-ribbon-flame-trail.md` 里的 Ribbon 火焰拖尾专项配方

这样输出会更快、更稳，也更像生产方案。
