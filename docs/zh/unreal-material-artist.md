# unreal-material-artist

`unreal-material-artist` 是 Unreal 材质和 shader 专家技能，用来设计、生成、审查和优化 UE 材质图、材质函数、贴图策略和 HLSL。

## 什么时候用

- 你要做火焰、烟尘、能量、熔岩、热扭曲、UI、后处理或 decal 材质
- 你要检查材质 domain、blend mode、shading model、sampler 或指令预算
- 你要为 Niagara renderer 设计材质
- 你要审查贴图导入、材质实例、Substrate 或 shader 复杂度

## 重点

- 先保住目标视觉，再做性能和平台优化
- 和 `niagara-vfx-artist` 配合时，它负责材质/Shader 专项
- 交付时要包含可验证的节点、参数、预算和预览基线

## 依赖与边界

- 连接编辑器时依赖同级 `unreal-engine-mcp`，每步优先官方 MCP；纯本地贴图检查和通道打包不需要连接 UE。
- 完整特效与 `niagara-vfx-artist` 配合：本技能负责材质图、贴图和参数契约，Niagara 技能负责实际发射器、Renderer 分配和运行时参数绑定。
- 需要生成贴图时可使用单独配置的 `cm-imagegen`；它是可选工作流伙伴，不是本技能的 Python 代码依赖，本 UE 压缩包不携带账号或服务配置。
- 材质编译通过、贴图本地检查通过和最终效果可用分别验证；平台成本、动态材质生命周期等按实际任务补运行验收。

```text
$unreal-material-artist 制作一个螺旋漩涡材质，暴露旋转速度、颜色和边缘软化参数，
增加中文分组与说明，在实际承载网格上验证外观。
```

五个技能共用官方 MCP 优先、后台操作、中文模块注释和范围内保存规则。
见 [SKILL.md](../../skills/ue5.8/unreal-material-artist/SKILL.md) 和 [UE 技能总览](ue-skills-overview.md)。
