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
