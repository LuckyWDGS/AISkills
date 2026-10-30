# Niagara VFX Artist Skill 维护说明

本文件面向维护者，执行任务时以 `SKILL.md` 为准。

## 当前定位

`niagara-vfx-artist` 负责 Unreal Engine Niagara 特效侧工作：

- 参考图拆解到 Niagara 层级
- System / Emitter / Module / Renderer 设计
- Spawn、Lifetime、Velocity、Event、Bounds、Scalability
- Renderer 材质槽位绑定需求与 carrier 合同
- 预览、审查、集成和交付

材质图、材质实例、纹理生成、HLSL、材质性能和材质配方属于 `../unreal-material-artist`。
Niagara 只描述“这一层需要什么材质合同”（Renderer 类型、UV、Particle Color、Dynamic
Parameter、Alpha、Blend Mode、Sorting、平台预算），Ribbon UV 约定以
`../unreal-material-artist/references/carrier-and-ribbon-rules.md` 为准。

## 编辑器通道

所有连接编辑器的工具都走 Epic 内置 MCP（经由 `../unreal-engine-mcp/scripts/ue_mcp`），
UnrealBridge 插件已退役。预览截图用 `../unreal-engine-mcp/scripts/capture.py`。
详见 `references/niagara-mcp-toolsets.md`。

## 目录

- `SKILL.md`：触发条件、工作流和职责边界
- `references/`：Niagara 知识与流程，`references/index.md` 说明每篇何时读
- `tools/`：命令行入口（薄封装）
- `scripts/vfx_delivery/`：工具实现；`mcp.py` 是共享 MCP 客户端的入口
- `scripts/test_*.py`：离线测试，由 `../unreal-engine-mcp/scripts/run_offline_tests.py` 统一运行

## 维护约定

- 改触发条件、工作流和职责边界：改 `SKILL.md`。
- 改 Niagara 细节知识：改 `references/` 下对应文档，并更新 `references/index.md`。
- 改闭环工具：改 `scripts/vfx_delivery/` 和 `tools/`，同时补离线测试。
- 改材质图、纹理、HLSL、材质性能：改 `../unreal-material-artist/`，不要把实现细节加回 Niagara。

## 常用验证

```powershell
python ../unreal-engine-mcp/scripts/run_offline_tests.py
python ../unreal-engine-mcp/scripts/live_smoke.py --project <ProjectName>
```
