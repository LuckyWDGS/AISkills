# niagara-vfx-artist

`niagara-vfx-artist` 用来做 Unreal Engine Niagara 特效的思考、设计、实现和优化。

## 什么时候用

- 用户要做火焰、能量、命中、盾、流体、拖尾、法阵、爆炸等 VFX
- 用户要看参考图后拆 Niagara 层级、材质、Flipbook 或 Flow Map 方案
- 用户要做 PC / Android / 低端设备上的性能权衡

## 它会帮你做什么

- 从艺术方向翻成 Niagara emitter / material / renderer 方案
- 讨论可实现性、成本、可读性和平台适配
- 需要概念图时，按技能里的图像桥接流程补视觉参考

## 重点

- 先判断效果是实时做、贴图做，还是烘焙做
- 不只看好不好看，也要看远景、节奏、预算和平台
- 最后要能回到可实施的 Niagara 结构

## 依赖与边界

- 连接编辑器依赖同级 `unreal-engine-mcp`；Flipbook builder 包装器依赖同级 `vfx-flipbook-generator`。
- 由本技能负责效果层次、时序、发射器、Renderer 和实际绑定；材质图、HLSL 和贴图细节交给 `unreal-material-artist`。
- 默认后台调用官方 MCP，确认缺口后才使用 Epic 公开 Python API，不自动开启窗口或安装自定义桥接。
- 检查真实系统结构、编译状态与 Stack 问题，再看运动、轮廓、密度和亮度；缩略图和编译成功不能代替动态效果验收。
- 交互特效还要验证激活、结束、对象池复用、拥有者销毁，以及包围盒和距离剔除。

```text
$niagara-vfx-artist 制作一个爆炸特效，拆成冲击、火焰、烟尘和火星层，
配合 $unreal-material-artist 完成材质，并接到已有投掷物爆炸事件。
```

中文模块说明、共享规则和组合方式见 [SKILL.md](../../skills/ue5.8/niagara-vfx-artist/SKILL.md)
及 [UE 技能总览](ue-skills-overview.md)。
